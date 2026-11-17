"""Capa de efectos del compositor 2D (Cel Studio v2).

Todo es determinista y funcion cerrada del tiempo ``t``: se puede renderizar
cualquier frame en cualquier orden. Requiere skia-python y numpy.
"""
from __future__ import annotations

import math
import os
import zlib
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import skia
from PIL import Image, ImageChops, ImageFilter

__all__ = ["PostFX", "Particles", "Smoke", "LightRays",
           "draw_fade", "draw_iris", "draw_title"]

TAU = math.tau
_SAMPLING = skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear)


# ----------------------------------------------------------------- helpers
def _rgb(c):
    if isinstance(c, (tuple, list)):
        return tuple(c[:3])
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _hex(c, alpha=1.0):
    r, g, b = _rgb(c)
    return skia.Color4f(r, g, b, alpha)


def _rng(seed, *keys):
    return np.random.default_rng([int(seed) & 0xFFFFFFFF] + [int(k) & 0xFFFFFFFF for k in keys])


def _smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def _image_from_rgba(arr):
    # BGRA = formato nativo del raster de Skia en CPU (RGBA + SrcOver cae a ruta lenta)
    arr = np.ascontiguousarray(np.asarray(arr, dtype=np.uint8)[..., [2, 1, 0, 3]])
    return skia.Image.fromarray(arr, colorType=skia.kBGRA_8888_ColorType,
                                alphaType=skia.kPremul_AlphaType)


def _soft_sprite(size, color, core=0.0, falloff=2.2):
    """Disco suave premultiplicado de ``size`` px; core = radio relativo de un nucleo solido."""
    y, x = np.mgrid[0:size, 0:size].astype(np.float32)
    c = (size - 1) / 2.0
    r = np.hypot(x - c, y - c) / (size / 2.0)
    a = np.clip(1 - r, 0, 1) ** falloff
    if core > 0:
        a = np.maximum(a, np.clip((core + 0.12 - r) / 0.12, 0, 1))
    rgb = np.array(_rgb(color), dtype=np.float32)
    out = np.empty((size, size, 4), np.float32)
    out[..., :3] = rgb * a[..., None]
    out[..., 3] = a
    return _image_from_rgba(np.round(out * 255))


# ------------------------------------------------------------------ PostFX
# Nota de rendimiento: en este skia-python (raster CPU) cada pasada de pantalla completa
# con blend/colorfilter cuesta 100-150 ms a 1080p, mientras que Pillow (C, SIMD) hace la
# misma operacion en 10-17 ms. Por eso PostFX usa Pillow para las pasadas a resolucion
# completa y deja a Skia el I/O (readPixels) y los efectos geometricos.
_DEFAULT_POST = {
    "bloom": {"threshold": 0.72, "sigma": 0.012, "strength": 0.30},
    "grade": {"contrast": 1.06, "saturation": 1.10, "temperature": 0.02,
              "lift": [0, 0, 0], "gain": [1, 1, 1]},
    "vignette": {"strength": 0.22, "radius": 0.80},
    "grain": {"amount": 0.025},
}

_BGRA = skia.kBGRA_8888_ColorType
_POOL = None


def _pool():
    """Hilos para repartir bandas: Pillow libera el GIL en sus operaciones de imagen."""
    global _POOL
    if _POOL is None:
        _POOL = ThreadPoolExecutor(max_workers=max(1, min(8, os.cpu_count() or 2)))
    return _POOL


def _bgra_info(w, h):
    return skia.ImageInfo.Make(int(w), int(h), _BGRA, skia.kPremul_AlphaType)


def _grade_params(g, headroom=1.0):
    """3x4 para Image.convert('RGB', m): saturacion -> contraste -> temperatura -> gain/lift."""
    lum = np.array([0.2126, 0.7152, 0.0722])
    s = float(g.get("saturation", 1.0))
    S = np.eye(3) * s + (1 - s) * np.tile(lum, (3, 1))
    c = float(g.get("contrast", 1.0))
    t = float(g.get("temperature", 0.0))
    gain = np.array(g.get("gain", [1, 1, 1]), float) * headroom
    lift = np.array(g.get("lift", [0, 0, 0]), float)
    d = gain * np.array([1 + t, 1 + t * 0.15, 1 - t])
    A = np.diag(d) @ (c * S)
    b = (d * (0.5 - 0.5 * c) + lift) * 255.0
    out = []
    for i in range(3):
        out += [float(A[i, 0]), float(A[i, 1]), float(A[i, 2]), float(b[i])]
    return tuple(out)


def _image_to_pil(image, w, h):
    """skia.Image -> PIL RGB de tamano (w,h)."""
    iw, ih = image.width(), image.height()
    buf = np.empty((ih, iw, 4), np.uint8)
    if not image.readPixels(_bgra_info(iw, ih), buf, iw * 4, 0, 0):
        raise RuntimeError("readPixels failed")
    im = Image.frombuffer("RGB", (iw, ih), buf, "raw", "BGRX", 0, 1)
    if (iw, ih) != (w, h):
        im = im.resize((w, h), Image.BILINEAR)
    return im


def _pil_to_skia(im):
    """PIL RGB -> skia.Image RGBA8888 opaca."""
    w, h = im.size
    arr = np.frombuffer(im.convert("RGBA").tobytes(), np.uint8).reshape(h, w, 4)
    return skia.Image.fromarray(arr, colorType=skia.kRGBA_8888_ColorType,
                                alphaType=skia.kOpaque_AlphaType)  # fromarray copia


class PostFX:
    """Bloom + vineta/grano + grade. Salida RGBA8888 opaca del mismo tamano.

    Orden: (src * [vineta*grano]) -> grade (1 matriz) -> screen(bloom). La vineta y el grano
    son un unico multiplicador precalculado (8 variantes de grano, elegidas por hash de
    frame_index), con margen de "headroom" que el grade devuelve, asi es neutral en luminancia.
    """

    GRAIN_VARIANTS = 8

    def __init__(self, width, height, params=None):
        self.w, self.h = int(width), int(height)
        user = params or {}
        p = {}
        for k, v in _DEFAULT_POST.items():
            if k in user:
                p[k] = None if user[k] is None else {**v, **user[k]}
            else:
                p[k] = dict(v)
        self.p = p
        nb = 8
        self._edges = [min(self.h, int(round(i * self.h / nb / 4.0)) * 4) for i in range(nb + 1)]
        self._edges[-1] = self.h
        self._build_mult()
        if self._mults:
            self._mult_bands = [[m.crop((0, a, self.w, b)) for a, b in zip(self._edges[:-1], self._edges[1:])]
                                for m in self._mults]
            self._mults = None
        else:
            self._mult_bands = None
        grade = p["grade"] if p["grade"] else {}
        self._grade = _grade_params(grade, self._headroom) if (p["grade"] or self._headroom != 1.0) else None
        self._build_bloom()

    # -- vineta + grano combinados en mapas multiplicadores RGB uint8
    def _build_mult(self):
        v, g = self.p["vignette"], self.p["grain"]
        have_v = bool(v) and v["strength"] > 0
        have_g = bool(g) and g["amount"] > 0
        self._mults = None
        self._headroom = 1.0
        if not (have_v or have_g):
            return
        w, h = self.w, self.h
        vig = np.ones((h, w, 3), np.float32)
        if have_v:
            s = float(v["strength"])
            ys = (np.arange(h, dtype=np.float32) - (h - 1) / 2)[:, None]
            xs = (np.arange(w, dtype=np.float32) - (w - 1) / 2)[None, :]
            R = math.hypot(w, h) / 2.0
            r = np.sqrt(xs * xs + ys * ys) / R
            start = 0.8125 * float(v["radius"]) * 0.65
            u = np.clip((r - start) / (1.0 - start), 0, 1)
            f = (u * u * (3 - 2 * u)) * u
            for ch, k in enumerate((0.85, 1.0, 1.25)):   # oscurece un poco mas el azul: calido
                vig[..., ch] = 1 - s * k * f
        if have_g:
            amt = float(g["amount"]) * 0.7
            self._headroom = 1.0 + 3.0 * amt
            rng = np.random.default_rng(90210)
            mults = []
            for _ in range(self.GRAIN_VARIANTS):
                n = rng.standard_normal((h, w)).astype(np.float32)
                n = 0.8 * n + 0.05 * (np.roll(n, 1, 0) + np.roll(n, -1, 0)
                                      + np.roll(n, 1, 1) + np.roll(n, -1, 1))
                n /= n.std()
                m = vig * (1 + n * amt)[..., None] / self._headroom
                mults.append(Image.fromarray(np.clip(np.round(m * 255), 0, 255).astype(np.uint8), "RGB"))
            self._mults = mults
        else:
            self._mults = [Image.fromarray(np.clip(np.round(vig * 255), 0, 255).astype(np.uint8), "RGB")]

    def _build_bloom(self):
        b = self.p["bloom"]
        self._bloom = None
        if not b or b["strength"] <= 0:
            return
        self._bw, self._bh = max(2, self.w // 4), max(2, self.h // 4)
        thr = float(b["threshold"])
        k = float(b["strength"]) / max(1e-3, 1.0 - thr)   # umbral + escala por fuerza
        o = -thr * k * 255.0
        self._thr_m = (k, 0, 0, o, 0, k, 0, o, 0, 0, k, o)
        self._sigma = max(0.5, float(b["sigma"]) * self.w / 4.0)
        self._bloom = b

    def apply(self, image, frame_index):
        """Reparte el cuadro en bandas horizontales que se procesan en hilos (resultado
        identico al de una sola pasada; no depende del numero de hilos)."""
        w, h = self.w, self.h
        iw, ih = image.width(), image.height()
        buf = np.empty((ih, iw, 4), np.uint8)
        if not image.readPixels(_bgra_info(iw, ih), buf, iw * 4, 0, 0):
            raise RuntimeError("readPixels failed")
        if (iw, ih) != (w, h):   # tamano distinto: reescala una vez
            im = Image.frombuffer("RGB", (iw, ih), buf, "raw", "BGRX", 0, 1).resize((w, h), Image.BILINEAR)
            buf = np.ascontiguousarray(np.frombuffer(im.convert("RGBA").tobytes("raw", "BGRA"),
                                                     np.uint8).reshape(h, w, 4))
        edges = self._edges
        bands = list(zip(edges[:-1], edges[1:]))
        ex = _pool()
        use_bloom = self._bloom is not None

        def phase1(i):
            y0, y1 = bands[i]
            src = Image.frombuffer("RGB", (w, y1 - y0), buf[y0:y1], "raw", "BGRX", 0, 1)
            return src, (src.reduce(4) if use_bloom else None)

        r1 = list(ex.map(phase1, range(len(bands))))
        bloom_small = None
        if use_bloom:
            sw, sh = r1[0][1].width, sum(r[1].height for r in r1)
            small = Image.new("RGB", (sw, sh))
            yy = 0
            for _, strip in r1:
                small.paste(strip, (0, yy))
                yy += strip.height
            small = small.convert("RGB", self._thr_m).filter(ImageFilter.GaussianBlur(self._sigma))
            bloom_small = small
        idx = zlib.crc32(b"grain%d" % int(frame_index)) % len(self._mult_bands) if self._mult_bands else 0
        out = np.empty((h, w, 4), np.uint8)

        def phase2(i):
            y0, y1 = bands[i]
            im = r1[i][0]
            if self._mult_bands:
                im = ImageChops.multiply(im, self._mult_bands[idx][i])
            if self._grade is not None:
                im = im.convert("RGB", self._grade)
            if bloom_small is not None:
                k = bloom_small.height / h
                bl = bloom_small.resize((w, y1 - y0), Image.BILINEAR,
                                        box=(0, y0 * k, bloom_small.width, y1 * k))
                im = ImageChops.screen(im, bl)
            out[y0:y1] = np.frombuffer(im.tobytes("raw", "RGBX"), np.uint8).reshape(y1 - y0, w, 4)
            out[y0:y1, :, 3] = 255   # el byte de relleno de Pillow puede quedar sin inicializar

        list(ex.map(phase2, range(len(bands))))
        return skia.Image.fromarray(out, colorType=skia.kRGBA_8888_ColorType,
                                    alphaType=skia.kOpaque_AlphaType)


# --------------------------------------------------------------- Particles
class Particles:
    """motes | leaves | fireflies. Posicion = funcion cerrada de t."""

    def __init__(self, spec, seed=0):
        self.spec = dict(spec)
        self.kind = spec.get("kind", "motes")
        self.count = int(spec.get("count", 40))
        self.area = [float(v) for v in spec.get("area", [0, 0, 1280, 720])]
        self.depth = float(spec.get("depth", 1.0))
        self.speed = float(spec.get("speed", 1.0))
        self.opacity = float(spec.get("opacity", 1.0))
        self.seed = int(seed)
        defaults = {"motes": ("#ffe2a8", 3.2), "leaves": ("#c9822b", 11.0),
                    "fireflies": ("#e6f27a", 3.0)}
        dc, ds = defaults.get(self.kind, defaults["motes"])
        self.color = spec.get("color", dc)
        self.size = float(spec.get("size", ds))
        rng = _rng(seed, {"motes": 1, "leaves": 2, "fireflies": 3}.get(self.kind, 1))
        self.u = rng.random((max(0, self.count), 10))
        if self.kind == "motes":
            self.sprite = _soft_sprite(64, self.color, falloff=1.6)
        elif self.kind == "fireflies":
            self.sprite = _soft_sprite(96, self.color, core=0.09, falloff=2.6)
        else:
            self._init_leaves()

    def _init_leaves(self):
        p = skia.Path()
        p.moveTo(0, -1.0)
        p.cubicTo(0.85, -0.45, 0.80, 0.50, 0, 0.78)
        p.cubicTo(-0.80, 0.50, -0.85, -0.45, 0, -1.0)
        p.close()
        self.leaf_path = p
        v = skia.Path()
        v.moveTo(0, -0.7)
        v.lineTo(0, 1.05)
        self.leaf_vein = v
        pal = ["#d98a2b", "#b9702a", "#7d9a3a", "#a8b13f", "#cf6f2d"]
        self.leaf_cols = [pal[int(x * len(pal)) % len(pal)] for x in self.u[:, 7]]

    def draw(self, canvas, t, view):
        if self.count <= 0:
            return
        {"motes": self._motes, "fireflies": self._fireflies,
         "leaves": self._leaves}.get(self.kind, self._motes)(canvas, float(t), view)

    def _motes(self, canvas, t, view):
        x0, y0, x1, y1 = self.area
        W, H = x1 - x0, y1 - y0
        sc = view.scale(self.depth)
        paint = skia.Paint(AntiAlias=True, BlendMode=skia.BlendMode.kPlus)
        srect = skia.Rect.MakeWH(64, 64)
        for u in self.u:
            sz = self.size * (0.35 + 1.5 * u[0] ** 2)
            vx = (4 + 9 * u[1]) * self.speed
            vy = (-3 + 4 * u[2]) * self.speed
            P1, P2 = 5 + 7 * u[3], 8 + 9 * u[4]
            x = x0 + (u[5] * W + vx * t + 14 * math.sin(TAU * t / P1 + u[6] * TAU)) % W
            y = y0 + (u[7] * H + vy * t + 10 * math.sin(TAU * t / P2 + u[8] * TAU)) % H
            tw = 0.55 + 0.45 * math.sin(TAU * t / (3 + 5 * u[9]) + u[0] * 40)
            edge = _smooth(min(min(x - x0, x1 - x) / (0.08 * W), min(y - y0, y1 - y) / (0.08 * H)))
            a = self.opacity * (0.22 + 0.5 * u[2]) * tw * edge
            if a <= 0.003:
                continue
            sx, sy = view.to_screen(x, y, self.depth)
            r = sz * sc
            paint.setAlphaf(min(1.0, a))
            canvas.drawImageRect(self.sprite, srect, skia.Rect(sx - r, sy - r, sx + r, sy + r),
                                 _SAMPLING, paint)

    def _fireflies(self, canvas, t, view):
        x0, y0, x1, y1 = self.area
        W, H = x1 - x0, y1 - y0
        sc = view.scale(self.depth)
        paint = skia.Paint(AntiAlias=True, BlendMode=skia.BlendMode.kPlus)
        srect = skia.Rect.MakeWH(96, 96)
        sp = self.speed
        for u in self.u:
            ax, ay = 0.10 * W * (0.4 + u[0]), 0.12 * H * (0.4 + u[1])
            fx1, fx2 = 1 / (9 + 10 * u[2]), 1 / (5 + 6 * u[3])
            fy1, fy2 = 1 / (8 + 9 * u[4]), 1 / (4 + 5 * u[5])
            cx = x0 + W * (0.1 + 0.8 * u[6])
            cy = y0 + H * (0.15 + 0.7 * u[7])
            x = cx + ax * (math.sin(TAU * fx1 * t * sp + u[8] * TAU)
                           + 0.4 * math.sin(TAU * fx2 * t * sp + u[9] * 9))
            y = cy + ay * (math.sin(TAU * fy1 * t * sp + u[9] * TAU)
                           + 0.4 * math.sin(TAU * fy2 * t * sp + u[8] * 9))
            ph = TAU * t / (3.2 + 3.5 * u[3]) + u[4] * TAU
            blink = _smooth(math.sin(ph) + 0.35)
            a = self.opacity * (0.12 + 0.88 * blink)
            sx, sy = view.to_screen(x, y, self.depth)
            r = self.size * 5.0 * sc * (0.85 + 0.15 * blink)
            paint.setAlphaf(min(1.0, a))
            canvas.drawImageRect(self.sprite, srect, skia.Rect(sx - r, sy - r, sx + r, sy + r),
                                 _SAMPLING, paint)

    def _leaves(self, canvas, t, view):
        x0, y0, x1, y1 = self.area
        W, H = x1 - x0, y1 - y0
        sc = view.scale(self.depth)
        fill = skia.Paint(AntiAlias=True)
        line = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style,
                          StrokeJoin=skia.Paint.kRound_Join, StrokeCap=skia.Paint.kRound_Cap)
        vein = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style,
                          StrokeCap=skia.Paint.kRound_Cap)
        dark = _hex("#3a2416")
        for i, u in enumerate(self.u):
            period = (7.0 + 7.0 * u[0]) / self.speed
            m = 20.0
            q = t / period + u[1]
            ph = q % 1.0
            cyc = int(math.floor(q))
            y = y0 - m + ph * (H + 2 * m)
            hx = ((cyc * 2654435761 + i * 40503 + self.seed * 97) & 0xFFFF) / 65535.0
            sway = math.sin(TAU * t / (3.0 + 2.5 * u[3]) + u[4] * TAU)
            x = x0 + (u[2] * 0.6 * W + hx * 0.4 * W + ph * (H + 2 * m) * 0.30 + 22 * sway) % W
            rot = 35 * math.sin(TAU * t / (3.0 + 2.5 * u[3]) + u[4] * TAU + 1.2) \
                + 90 * (t / (period * (2 + 3 * u[5]))) * (1 if u[6] > 0.5 else -1)
            flip = math.cos(TAU * t / (2.4 + 2 * u[8]) + u[9] * TAU)
            fade = _smooth(ph / 0.06) * _smooth((1 - ph) / 0.06) * self.opacity
            if fade <= 0.01:
                continue
            s = self.size * (0.75 + 0.5 * u[6]) * sc
            sx, sy = view.to_screen(x, y, self.depth)
            canvas.save()
            canvas.translate(sx, sy)
            canvas.rotate(rot)
            canvas.scale(s * 0.62 * (0.35 + 0.65 * abs(flip)), s)
            col = self.spec.get("color", self.leaf_cols[i])
            fill.setColor4f(_hex(col, fade))
            line.setColor4f(skia.Color4f(dark.fR, dark.fG, dark.fB, fade))
            vein.setColor4f(skia.Color4f(dark.fR, dark.fG, dark.fB, 0.5 * fade))
            line.setStrokeWidth(max(1.2, 1.5 * sc) / s)
            vein.setStrokeWidth(max(0.8, 0.9 * sc) / s)
            canvas.drawPath(self.leaf_path, fill)
            canvas.drawPath(self.leaf_vein, vein)
            canvas.drawPath(self.leaf_path, line)
            canvas.restore()


# ------------------------------------------------------------------- Smoke
class Smoke:
    def __init__(self, spec, seed=0):
        s = {"x": 0, "y": 0, "depth": 1.0, "rate": 0.9, "rise": 55.0, "life": 4.5,
             "size": 16.0, "drift": 14.0, "color": "#fff3dc", "outline": "#3a2416",
             "opacity": 0.85}
        s.update(spec)
        self.s = s
        self.seed = int(seed)
        self._cache = {}
        self._fill = skia.Paint(AntiAlias=True)
        self._fill.setColor4f(_hex(s["color"]))
        self._line = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style,
                                StrokeJoin=skia.Paint.kRound_Join)
        self._line.setColor4f(_hex(s["outline"]))

    def _puff(self, i):
        d = self._cache.get(i)
        if d is None:
            if len(self._cache) > 256:
                self._cache.clear()
            r = _rng(self.seed, i + (1 << 30))
            n = 2 + int(r.integers(0, 2))
            circles = [(0.0, 0.0, 1.0)]
            side = 1.0 if r.random() < 0.5 else -1.0
            for k in range(n - 1):   # bultos a los lados y arriba: silueta de nube
                ang = math.radians(-20 - 60 * k) if side > 0 else math.radians(200 + 60 * k)
                ang += (r.random() - 0.5) * 0.5
                circles.append((math.cos(ang) * 0.85, math.sin(ang) * 0.62, 0.62 + 0.22 * r.random()))
            d = {"c": circles, "ph": r.random() * TAU, "sz": 0.85 + 0.3 * r.random(),
                 "wind": 0.8 + 0.4 * r.random()}
            self._cache[i] = d
        return d

    def draw(self, canvas, t, view):
        s = self.s
        rate, life = float(s["rate"]), float(s["life"])
        sc = view.scale(s["depth"])
        for i in range(math.ceil((t - life) * rate), math.floor(t * rate) + 1):  # mas viejo primero
            age = t - i / rate
            if not (0.0 <= age < life):
                continue
            d = self._puff(i)
            u = age / life
            rise = s["rise"] * life * (1 - math.exp(-age / (life * 0.75))) * 0.75
            wx = s["drift"] * d["wind"] * (age + 0.18 * age * age)
            curl = 7.0 * math.sin(age * 1.5 + d["ph"]) * _smooth(age / 1.5)
            rad = s["size"] * d["sz"] * (0.6 + 1.0 * (1 - math.exp(-age * 1.3)) + 0.7 * u)
            rad *= 1.0 - 0.35 * _smooth((u - 0.7) / 0.3)
            alpha = s["opacity"] * _smooth(age / 0.35) * (1 - _smooth((u - 0.5) / 0.5))
            if alpha <= 0.01:
                continue
            sx, sy = view.to_screen(s["x"] + wx + curl, s["y"] - rise, s["depth"])
            R = rad * sc
            lw = max(1.4, 2.4 * sc)
            b = R * 2.4 + lw
            canvas.saveLayerAlpha(skia.Rect(sx - b, sy - b, sx + b, sy + b), int(round(alpha * 255)))
            self._line.setStrokeWidth(lw * 2)
            rot = 0.25 * math.sin(age * 0.8 + d["ph"])
            co, si = math.cos(rot), math.sin(rot)
            cs = [(sx + (ox * co - oy * si) * R, sy + (ox * si + oy * co) * R, R * k)
                  for ox, oy, k in d["c"]]
            for cx, cy, r in cs:
                canvas.drawCircle(cx, cy, r, self._line)
            for cx, cy, r in cs:
                canvas.drawCircle(cx, cy, r, self._fill)
            canvas.restore()


# --------------------------------------------------------------- LightRays
def _readback(canvas, x, y, w, h):
    """Lee pixeles del canvas base (BGRA premul) o None si no es posible."""
    arr = np.empty((h, w, 4), np.uint8)
    try:
        ok = canvas.readPixels(_bgra_info(w, h), arr, w * 4, int(x), int(y))
    except Exception:
        ok = False
    return arr if ok else None


def _writeback(canvas, im, x, y):
    arr = np.frombuffer(im.convert("RGBA").tobytes("raw", "BGRA"), np.uint8).reshape(im.height, im.width, 4)
    return bool(canvas.writePixels(_bgra_info(im.width, im.height), arr, im.width * 4, int(x), int(y)))


def _add_layer(canvas, layer, x, y):
    """Suma una capa PIL RGB sobre el canvas en (x,y) via Pillow (rapido);
    si el canvas no permite readPixels, cae a drawImage con kPlus."""
    w, h = layer.size
    buf = _readback(canvas, x, y, w, h)
    if buf is not None:
        base = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
        res = ImageChops.add(base, layer)
        res = Image.merge("RGBA", (*res.split(), Image.new("L", (w, h), 255)))
        if _writeback(canvas, res, x, y):
            return
    canvas.drawImage(_pil_to_skia(layer), x, y, skia.SamplingOptions(),
                     skia.Paint(BlendMode=skia.BlendMode.kPlus))


def _add_small_layer(canvas, lay, x0, y0, bw, bh, D):
    """Suma (aditivo) una capa de baja resolucion, escalada x D, sobre el canvas en (x0,y0)
    tamano (bw,bh). ``lay`` es PIL 'RGBA' cuya memoria esta en orden BGRA (igual que el canvas),
    asi no hay que intercambiar canales. Bandas en hilos; si no hay readPixels, cae a kPlus."""
    base_buf = _readback(canvas, x0, y0, bw, bh)
    sw, sh = lay.size
    if base_buf is None:
        info = _bgra_info(sw, sh)
        small = skia.Image.fromarray(np.asarray(lay), colorType=skia.kBGRA_8888_ColorType,
                                     alphaType=skia.kPremul_AlphaType)
        canvas.drawImageRect(small, skia.Rect.MakeWH(sw, sh), skia.Rect.MakeXYWH(x0, y0, bw, bh),
                             _SAMPLING, skia.Paint(BlendMode=skia.BlendMode.kPlus))
        return
    nb = min(8, max(1, sh // 4))
    rows = [min(sh, int(round(i * sh / nb))) for i in range(nb + 1)]
    out = np.empty((bh, bw, 4), np.uint8)

    def band(i):
        r0, r1 = rows[i], rows[i + 1]
        y0b, y1b = min(bh, r0 * D), (bh if i == nb - 1 else min(bh, r1 * D))   # last band absorbs the remainder rows
        base = Image.frombuffer("RGBA", (bw, y1b - y0b), base_buf[y0b:y1b], "raw", "RGBA", 0, 1)
        up = lay.resize((bw, y1b - y0b), Image.BILINEAR, box=(0, r0, sw, r1))
        out[y0b:y1b] = np.asarray(ImageChops.add(base, up))

    list(_pool().map(band, range(nb)))
    out[..., 3] = 255
    canvas.writePixels(_bgra_info(bw, bh), out, bw * 4, int(x0), int(y0))


class LightRays:
    """Rayos de luz suaves y aditivos. Se componen a 1/8 de resolucion y se suman con Pillow."""
    _sprites = {}
    DOWN = 8

    @classmethod
    def _get_sprite(cls, color):
        key = tuple(round(c, 3) for c in _rgb(color))
        if key not in cls._sprites:
            W, H = 512, 128
            u = np.linspace(0, 1, W, dtype=np.float32)[None, :]
            v = np.linspace(-1, 1, H, dtype=np.float32)[:, None]
            q = np.abs(v) / (0.04 + 0.96 * u)
            a = np.exp(-(q ** 2) * 2.6) * (1 - u) ** 1.5 * np.clip(u / 0.05, 0, 1)
            a = np.clip(a, 0, 1)
            arr = np.zeros((H, W, 4), np.float32)
            for i in range(3):
                arr[..., i] = a * key[i] * 255
            arr[..., 3] = a * 255
            cls._sprites[key] = _image_from_rgba(np.round(arr))
        return cls._sprites[key]

    def __init__(self, spec, seed=0):
        s = {"x": 925, "y": 115, "depth": 0.1, "count": 7, "length": 900, "spread_deg": 70,
             "direction_deg": 115, "color": "#ffe9b0", "opacity": 0.10}
        s.update(spec)
        self.s = s
        self.r = _rng(seed, 77).random((int(s["count"]), 6))
        self.sprite = self._get_sprite(s["color"])
        self._srect = skia.Rect.MakeWH(512, 128)

    def _rays(self, t, view):
        s = self.s
        n = len(self.r)
        sc = view.scale(s["depth"])
        sx, sy = view.to_screen(s["x"], s["y"], s["depth"])
        spread = float(s["spread_deg"])
        step = spread / n
        out = []
        for i, r in enumerate(self.r):
            base = s["direction_deg"] - spread / 2 + (i + 0.5) * step + (r[0] - 0.5) * step * 0.6
            ang = base + 1.6 * math.sin(TAU * t / (6 + 9 * r[1]) + r[3] * TAU)
            shim = 0.55 + 0.45 * math.sin(TAU * t / (6 + 9 * r[2]) + r[4] * TAU)
            op = min(1.0, s["opacity"] * (0.55 + 0.9 * r[5]) * shim)
            L = s["length"] * sc * (0.8 + 0.4 * r[2])
            hw = L * math.tan(math.radians(step * (1.1 + 0.9 * r[5])) / 2)
            out.append((ang, op, L, hw))
        return sx, sy, out

    def draw(self, canvas, t, view):
        if len(self.r) == 0:
            return
        sx, sy, rays = self._rays(t, view)
        size = canvas.getBaseLayerSize()
        cw, ch = size.width(), size.height()
        xs, ys = [sx], [sy]
        for ang, op, L, hw in rays:
            a = math.radians(ang)
            ca, sa = math.cos(a), math.sin(a)
            for (px, py) in ((0, -hw), (0, hw), (L, -hw), (L, hw)):
                xs.append(sx + px * ca - py * sa)
                ys.append(sy + px * sa + py * ca)
        D = self.DOWN
        x0 = max(0, int(math.floor(min(xs) / D)) * D)
        y0 = max(0, int(math.floor(min(ys) / D)) * D)
        x1 = min(cw, int(math.ceil(max(xs) / D)) * D)
        y1 = min(ch, int(math.ceil(max(ys) / D)) * D)
        if x1 - x0 < D or y1 - y0 < D:
            return
        bw, bh = x1 - x0, y1 - y0
        sw, sh = bw // D, bh // D
        small = skia.Surface.MakeRaster(_bgra_info(sw, sh))
        sc_ = small.getCanvas()
        sc_.clear(skia.ColorBLACK)
        paint = skia.Paint(AntiAlias=True, BlendMode=skia.BlendMode.kPlus)
        for ang, op, L, hw in rays:
            paint.setAlphaf(op)
            sc_.save()
            sc_.scale(1.0 / D, 1.0 / D)
            sc_.translate(sx - x0, sy - y0)
            sc_.rotate(ang)
            sc_.drawImageRect(self.sprite, self._srect, skia.Rect(0, -hw, L, hw), _SAMPLING, paint)
            sc_.restore()
        buf = np.empty((sh, sw, 4), np.uint8)
        small.makeImageSnapshot().readPixels(_bgra_info(sw, sh), buf, sw * 4, 0, 0)
        buf[..., 3] = 255
        lay = Image.frombuffer("RGBA", (sw, sh), buf, "raw", "RGBA", 0, 1)
        _add_small_layer(canvas, lay, x0, y0, bw, bh, D)


# ------------------------------------------------------------- transitions
def draw_fade(canvas, amount, color="#000000"):
    """Fundido a color sobre todo el canvas (LUT por canal con Pillow; el canvas se asume opaco)."""
    a = min(1.0, max(0.0, float(amount)))
    if a <= 0:
        return
    size = canvas.getBaseLayerSize()
    cw, ch = size.width(), size.height()
    buf = _readback(canvas, 0, 0, cw, ch)
    if buf is not None:
        im = Image.frombuffer("RGBA", (cw, ch), buf, "raw", "RGBA", 0, 1)   # memoria BGRA
        r, g, b = _rgb(color)
        lut = []
        for c in (b, g, r):
            lut += [int(round(v * (1 - a) + c * 255 * a)) for v in range(256)]
        lut += list(range(256))
        out = np.empty((ch, cw, 4), np.uint8)
        nb = 8
        ed = [int(round(i * ch / nb)) for i in range(nb + 1)]

        def band(i):
            out[ed[i]:ed[i + 1]] = np.asarray(im.crop((0, ed[i], cw, ed[i + 1])).point(lut))

        list(_pool().map(band, range(nb)))
        out[..., 3] = 255
        if canvas.writePixels(_bgra_info(cw, ch), out, cw * 4, 0, 0):
            return
    canvas.drawPaint(skia.Paint(Color4f=_hex(color, a)))


def _smooth_np(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def draw_iris(canvas, progress, cx, cy, width, height, color="#1a120c"):
    """progress 0 = cerrado (todo color), 1 = abierto (nada). Borde ligeramente suave."""
    p = min(1.0, max(0.0, float(progress)))
    if p >= 1.0:
        return
    rect = skia.Rect.MakeWH(width, height)
    solid = skia.Paint(AntiAlias=True, Color4f=_hex(color))
    if p <= 0.0:
        canvas.drawRect(rect, solid)
        return
    rmax = max(math.hypot(cx - x, cy - y) for x in (0, width) for y in (0, height))
    soft = max(2.0, 0.006 * width)
    r = (rmax + soft * 2) * p            # centro del borde suave
    r_out = r + soft
    r_in = max(0.0, r - soft)
    path = skia.Path()
    path.addRect(rect)
    path.addCircle(cx, cy, max(0.0, r_out - 0.75))
    path.setFillType(skia.PathFillType.kEvenOdd)
    canvas.drawPath(path, solid)
    n = 10
    pos, cols = [], []
    for i in range(n + 1):
        d = r_out * i / n
        pos.append(i / n)
        cols.append(_hex(color, _smooth_np((d - (r - soft)) / (2 * soft))))
    shader = skia.GradientShader.MakeRadial((cx, cy), r_out, cols, pos, skia.TileMode.kClamp)
    ring = skia.Path()
    ring.addCircle(cx, cy, r_out)
    if r_in > 0:
        ring.addCircle(cx, cy, r_in)
        ring.setFillType(skia.PathFillType.kEvenOdd)
    canvas.save()
    canvas.clipPath(ring, skia.ClipOp.kIntersect, True)
    canvas.drawCircle(cx, cy, r_out, skia.Paint(AntiAlias=True, Shader=shader))
    canvas.restore()


_FONT_CACHE = {}


def _typeface(italic=False):
    if italic in _FONT_CACHE:
        return _FONT_CACHE[italic]
    mgr = skia.FontMgr.RefDefault()
    style = skia.FontStyle.Italic() if italic else skia.FontStyle.Normal()
    names = (["Georgia"] if italic else ["Cooper Black", "Georgia"]) + \
        ["Palatino Linotype", "Segoe UI"]
    found = None
    for name in names:
        tf = mgr.matchFamilyStyle(name, style)
        if tf is not None and tf.getFamilyName().lower() == name.lower():
            found = tf
            break
    if found is None:
        found = skia.Typeface.MakeFromName("", style) or skia.Typeface.MakeDefault()
    _FONT_CACHE[italic] = found
    return found


def _layout(text, font, spacing):
    glyphs = font.textToGlyphs(text)
    widths = font.getWidths(glyphs)
    return glyphs, widths, sum(widths) + spacing * (len(glyphs) - 1)


_TITLE_CACHE = {}


TITLE_BASELINE = 0.27   # fraction of frame height for the title baseline


def _title_layer(title, subtitle, width, height, color, shadow, q):
    """Renderiza la tarjeta (sin animar) en una capa transparente ajustada al texto.
    q = 0..16 fija el espaciado de letras (16 = asentado). Devuelve (PIL RGBA, x0, y0)."""
    key = (title, subtitle, width, height, color, shadow, q)
    hit = _TITLE_CACHE.get(key)
    if hit is not None:
        return hit
    if len(_TITLE_CACHE) > 40:
        _TITLE_CACHE.clear()
    e = q / 16.0
    tsize, ssize = height * 0.092, height * 0.040
    cx = width / 2.0
    ybase = height * TITLE_BASELINE
    tf = skia.Font(_typeface(), tsize)
    sf = skia.Font(_typeface(True), ssize)
    for f in (tf, sf):
        f.setSubpixel(True)
        f.setEdging(skia.Font.Edging.kAntiAlias)
    tspace = tsize * (0.16 * (1 - e) + 0.015)
    sspace = ssize * (0.30 * (1 - e) + 0.10)
    ys = ybase + ssize * 1.9
    tw = _layout(title, tf, tspace)[2]
    sw = _layout(subtitle, sf, sspace)[2]
    pad = tsize * 0.45
    x0 = int(max(0, cx - max(tw, sw) / 2 - pad))
    x1 = int(min(width, cx + max(tw, sw) / 2 + pad))
    y0 = int(max(0, ybase - tsize * 1.1 - pad * 0.5))
    y1 = int(min(height, ys + ssize * 0.7 + pad * 0.5))
    lw, lh = x1 - x0, y1 - y0
    surf = skia.Surface.MakeRaster(_bgra_info(lw, lh))
    canvas = surf.getCanvas()
    canvas.clear(skia.ColorTRANSPARENT)
    canvas.translate(-x0, -y0)

    def run(text, font, y, spacing, col, strokew=0.0, blur=0.0, dy=0.0, alpha=1.0):
        glyphs, widths, total = _layout(text, font, spacing)
        x = cx - total / 2.0
        pts = []
        for wd in widths:
            pts.append(skia.Point(x, y + dy))
            x += wd + spacing
        paint = skia.Paint(AntiAlias=True)
        paint.setColor4f(_hex(col, alpha))
        if blur:
            paint.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
        if strokew:
            paint.setStyle(skia.Paint.kStroke_Style)
            paint.setStrokeWidth(strokew)
            paint.setStrokeJoin(skia.Paint.kRound_Join)
        b = skia.TextBlobBuilder()
        b.allocRunPos(font, glyphs, pts)
        canvas.drawTextBlob(b.make(), 0, 0, paint)

    run(title, tf, ybase, tspace, shadow, blur=tsize * 0.06, dy=tsize * 0.07, alpha=0.55)
    run(subtitle, sf, ys, sspace, shadow, blur=ssize * 0.10, dy=ssize * 0.08, alpha=0.55)
    run(title, tf, ybase, tspace, shadow, strokew=tsize * 0.11)
    run(title, tf, ybase, tspace, color)
    run(subtitle, sf, ys, sspace, shadow, strokew=ssize * 0.16)
    run(subtitle, sf, ys, sspace, color)
    buf = np.empty((lh, lw, 4), np.uint8)
    surf.makeImageSnapshot().readPixels(_bgra_info(lw, lh), buf, lw * 4, 0, 0)
    # BGRA premultiplicado -> PIL RGBA directo (convert desmultiplica)
    layer = Image.frombuffer("RGBa", (lw, lh), buf, "raw", "BGRa", 0, 1).convert("RGBA")
    out = (layer, x0, y0)
    _TITLE_CACHE[key] = out
    return out


def draw_title(canvas, title, subtitle, progress, width, height,
               color="#fff3dc", shadow="#3a2416"):
    """Tarjeta de titulo. progress 0..1: fade + deslizamiento + espaciado que se asienta.
    La capa se cachea (17 pasos de espaciado) y se compone con Pillow sobre el canvas."""
    p = min(1.0, max(0.0, float(progress)))
    if p <= 0:
        return
    e = 1 - (1 - p) ** 3
    a = _smooth(p / 0.7)
    layer, x0, y0 = _title_layer(title, subtitle, int(width), int(height), color, shadow,
                                 int(round(e * 16)))
    dy = int(round((1 - e) * height * 0.025))
    ty0 = y0 + dy
    lw, lh = layer.size
    cw, chh = canvas.getBaseLayerSize().width(), canvas.getBaseLayerSize().height()
    ty0c = max(0, min(ty0, chh - lh))
    if a < 1.0:
        alpha = layer.getchannel("A").point([int(round(v * a)) for v in range(256)])
        layer = layer.copy()
        layer.putalpha(alpha)
    if lw <= cw and lh <= chh:
        buf = _readback(canvas, x0, ty0c, lw, lh)
        if buf is not None:
            base = Image.frombuffer("RGB", (lw, lh), buf, "raw", "BGRX", 0, 1).copy()
            base.paste(layer.convert("RGB"), (0, 0), layer.getchannel("A"))
            res = np.empty((lh, lw, 4), np.uint8)
            res[...] = np.frombuffer(base.tobytes("raw", "BGRX"), np.uint8).reshape(lh, lw, 4)
            res[..., 3] = 255
            if canvas.writePixels(_bgra_info(lw, lh), res, lw * 4, int(x0), int(ty0c)):
                return
    # alternativa: dibujar la capa con Skia
    arr = np.frombuffer(layer.tobytes("raw", "RGBA"), np.uint8).reshape(lh, lw, 4)
    img = skia.Image.fromarray(arr, colorType=skia.kRGBA_8888_ColorType,
                               alphaType=skia.kUnpremul_AlphaType)
    canvas.drawImage(img, x0, ty0)
