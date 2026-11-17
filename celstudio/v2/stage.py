"""Multiplane compositor for schema v2 films: parallax sets, lit puppets, props, effects.

All drawing is CPU Skia and a pure function of (film, shot, t). No model inference.
"""
import json
import math
import shutil
import subprocess
from pathlib import Path
import numpy as np
import skia
from .anim import Track, noise1, hash01
from .puppet import Rig, Performer, rgba, rot
from .gfx import Tex, LINEAR
from . import fx


# Defaults of the in-between and integration effects; film['style'] / shot['style'] override them (0 turns one off).
# smear: strength of the drawing-switch in-between (smear_px blur reach and smear_stretch x-stretch at full speed).
# edge_soft: sigma in px at 1920 of the figure's edge softening; ink_lift: lighter ink at small scales (0..1).
STYLE_DEFAULTS = {'smear': 1.0, 'smear_px': 6.0, 'smear_stretch': .10, 'smear_mix': 0.0, 'edge_soft': .5, 'ink_lift': .22}
# light.ambient.shade_mix: how much shaded paint takes the ambient colour.
AMBIENT_DEFAULTS = {'shade_mix': .3}


class View:
    """World→screen mapping with parallax. depth 1 = character plane, <1 farther, >1 foreground."""

    def __init__(self, width, height, world_w=1280.0, world_h=720.0, cx=640.0, cy=360.0, zoom=1.0, roll=0.0):
        self.width, self.height, self.world_w, self.world_h = width, height, world_w, world_h
        self.cx, self.cy, self.zoom, self.roll = cx, cy, zoom, roll

    def scale(self, depth=1.0):
        return self.width/self.world_w*self.zoom**(.42+.58*depth)

    def to_screen(self, x, y, depth=1.0):
        s = self.scale(depth)
        ex = self.world_w/2+(self.cx-self.world_w/2)*depth
        ey = self.world_h/2+(self.cy-self.world_h/2)*depth
        return (x-ex)*s+self.width/2, (y-ey)*s+self.height/2


def load_film(path):
    path = Path(path)
    film = json.loads(path.read_text(encoding='utf-8'))
    if film.get('schema_version') != 2:
        raise ValueError('Se requiere un film schema_version 2')
    return film, (path.parent/film['root'] if film.get('root') else path.parent)   # episodes of a series name their asset root


class Stage:
    def __init__(self, film, root, width=None):
        self.film, self.root = film, Path(root)
        self.fps = film['fps']
        self.width = width or film['width']
        self.height = max(2, round(film['height']*self.width/film['width']/2)*2)
        self.world_w, self.world_h = film.get('world', [1280, 720])
        self.k = self.width/1920
        self.rigs = {}
        for cid, source in film['characters'].items():
            data = json.loads((self.root/source).read_text(encoding='utf-8')) if isinstance(source, str) else source
            self.rigs[cid] = Rig(data, self.root)
        self._images, self._performers, self._setfx, self._props = {}, {}, {}, {}
        self._post = {}

    def image(self, filename):
        if filename not in self._images:
            self._images[filename] = Tex.open(self.root/filename)
        return self._images[filename]

    def performers(self, shot):
        if shot['id'] not in self._performers:
            self._performers[shot['id']] = {
                a.get('id', a['character']): Performer(self.rigs[a['character']], a, shot['duration'],
                                                       seed=hash01(shot['id'], a.get('id', a['character'])))
                for a in shot.get('actors', [])}
        return self._performers[shot['id']]

    # ---- camera ----
    def view(self, shot, t):
        cam = shot.get('camera', {})

        def value(name, default):
            keys = cam.get(name)
            return Track(keys).at(t) if keys else default
        x, y, zoom = value('x', self.world_w/2), value('y', self.world_h/2), value('zoom', 1.0)
        drift = value('drift', 1.0)
        seed = hash01(shot['id'], 'cam')*1000
        x += drift*1.6*noise1(t*.23+seed, 1)/zoom
        y += drift*1.1*noise1(t*.19+seed, 2)/zoom
        shake = value('shake', 0.0)
        if shake:
            x += shake*noise1(t*17+seed, 3)
            y += shake*noise1(t*19+seed, 4)
        return View(self.width, self.height, self.world_w, self.world_h, x, y, zoom, value('roll', 0.0))

    # ---- set ----
    def _layer(self, canvas, layer, t, view, dof):
        image = self.image(layer['image'])
        depth = layer.get('depth', 1.0)
        x, y = layer.get('x', self.world_w/2), layer.get('y', self.world_h/2)
        if layer.get('drift'):
            x0, x1 = layer['drift']['wrap']
            x = x0+((x-x0)+layer['drift']['vx']*(t+layer['drift'].get('offset', 0))) % (x1-x0)
        sx, sy = view.to_screen(x, y, depth)
        scale = view.scale(depth)*layer['w']/image.width()
        paint = skia.Paint(AntiAlias=True)
        if layer.get('opacity', 1) < 1:
            paint.setAlphaf(layer['opacity'])
        sigma = dof*layer.get('blur', 0)*self.k
        if sigma > .35:
            image = image.blurred(sigma/scale)
        canvas.save()
        canvas.translate(sx, sy)
        if layer.get('sway'):
            sway = layer['sway']
            ax, ay = sway.get('anchor', [0, 0])
            angle = sway.get('deg', 1.0)*(math.sin(2*math.pi*(t/sway.get('period', 4.0)+sway.get('phase', 0)))
                                           + .4*math.sin(2*math.pi*(t/(sway.get('period', 4.0)*.37)+.3)))
            canvas.translate(ax*view.scale(depth), ay*view.scale(depth))
            canvas.rotate(angle)
            canvas.translate(-ax*view.scale(depth), -ay*view.scale(depth))
        canvas.scale(scale, scale)
        image.draw(canvas, -image.width()/2, -image.height()/2, paint)
        canvas.restore()

    def _lights(self, canvas, lights, t, view, front):
        for light in lights:
            if bool(light.get('front')) != front:
                continue
            depth = light.get('depth', 1.0)
            sx, sy = view.to_screen(light['x'], light['y'], depth)
            radius = light['radius']*view.scale(depth)
            level = light.get('opacity', .4)
            if light.get('pulse'):
                level *= 1+light['pulse']*(.6*math.sin(2*math.pi*t/light.get('period', 4.0))
                                           + .4*noise1(t*light.get('flicker', 2.0), 7))
            color = rgba(light['color'], level)
            shader = skia.GradientShader.MakeRadial((sx, sy), radius, [color, rgba(light['color'], level*.35), rgba(light['color'], 0)], [0, .4, 1])
            paint = skia.Paint(AntiAlias=True, BlendMode=skia.BlendMode.kPlus)
            paint.setShader(shader)
            canvas.drawCircle(sx, sy, radius, paint)

    def _set_effects(self, name, stage_set):
        if name not in self._setfx:
            items = []
            for i, spec in enumerate(stage_set.get('particles', [])):
                items.append((spec.get('front', True), fx.Particles(spec, seed=101+i)))
            for i, spec in enumerate(stage_set.get('smoke', [])):
                items.append((spec.get('front', False), fx.Smoke(spec, seed=201+i)))
            for i, spec in enumerate(stage_set.get('rays', [])):
                items.append((spec.get('front', True), fx.LightRays(spec, seed=301+i)))
            self._setfx[name] = items
        return self._setfx[name]

    # ---- actors ----
    def _actor(self, canvas, performer, t, view, light, style=None):
        rig = performer.rig
        style = style or {}
        # The drawing may be held "on twos"; root motion and the camera stay on ones.
        v, wobble = performer.drawing(t, self.fps, style.get('hold', 1))
        if v['opacity'] <= 0:
            return
        pose = rig.pose(v, wobble)
        s = view.scale(1.0)*v['scale']
        # Drawing switch (head view or mirror side changes within +-2 frames): stretch + smear + dissolve to the other drawing.
        change = performer.transition(t, self.fps, style.get('hold', 1)) if style.get('smear', 0) > 0 and hasattr(performer, 'transition') else None
        smear = style.get('smear', 0)*change['power'] if change else 0.0
        ox, oy = view.to_screen(v['x'], v['y'], 1.0)
        lift = v.get('lift', 0.0)*view.scale(1.0)
        pad = 16+(math.ceil(style.get('smear_px', 4.5)*smear*s) if smear else 0)
        half_w, top, bottom = 230*s, 400*s+lift, 60*s
        left, up = math.floor(max(0, ox-half_w-pad)), math.floor(max(0, oy-top-pad))
        right, down = math.ceil(min(self.width, ox+half_w+pad)), math.ceil(min(self.height, oy+bottom+pad))
        ground = light.get('shadow', {})
        if ground and v.get('shadow', 1.0) > 0:
            self._contact(canvas, ox, oy, s, lift, ground, v.get('shadow', 1.0)*v['opacity'], pose, v)
        if right-left < 4 or down-up < 4:
            return
        stretch = 1+style.get('smear_stretch', .05)*smear

        def figure(vals, wob, pz):
            surface = skia.Surface(right-left, down-up)
            layer = surface.getCanvas()
            layer.save()
            layer.translate(ox-left, oy-up-lift)
            layer.rotate(vals['rot'])
            layer.scale(s*vals['sx']*stretch*(1 if vals['facing'] >= 0 else -1), s*vals['sy'])
            rig.draw(layer, pz, vals, wob)
            layer.restore()
            return surface.makeImageSnapshot()
        base = figure(v, wobble, pose)
        if smear:
            base = self._smear(base, change, figure, v, rig, style, smear, s)
        nearest = skia.SamplingOptions()
        if ground and v.get('shadow', 1.0) > 0 and ground.get('cast'):
            cast = ground['cast']
            # Silhouette at quarter resolution: cheap blur, then projected onto the ground.
            sw, sh = max(2, (right-left)//4), max(2, (down-up)//4)
            small = skia.Surface(sw, sh)
            sc = small.getCanvas()
            blur = max(.4, cast.get('blur', 5)*self.k*view.zoom/4)
            soft = skia.Paint()
            soft.setImageFilter(skia.ImageFilters.Blur(blur, blur))
            sc.drawImageRect(base, skia.Rect.MakeWH(right-left, down-up), skia.Rect.MakeWH(sw, sh), LINEAR, soft)
            sc.drawColor(rgba(cast.get('color', '#3b2a22'), 1), skia.BlendMode.kSrcIn)
            paint = skia.Paint(AntiAlias=True)
            paint.setAlphaf(cast.get('opacity', .22)*v.get('shadow', 1.0)*v['opacity'])
            canvas.save()
            canvas.translate(ox, oy)
            canvas.concat(skia.Matrix().setAll(1, cast.get('shear', .55), 0, 0, -cast.get('squash', .30), 0, 0, 0, 1))
            canvas.translate(-ox, -oy+lift*.4)
            canvas.drawImageRect(small.makeImageSnapshot(), skia.Rect.MakeWH(sw, sh), skia.Rect.MakeLTRB(left, up, right, down), LINEAR, paint)
            canvas.restore()
        # Lighting in numpy on the sparse edge bands (Skia's non-SrcOver raster blends are slow).
        # Lighting and contour growth below operate on coverage-weighted RGB.
        # Straight RGB would expose almost-transparent source colours as opaque
        # speckles when the contour increases their alpha.
        array = base.toarray(colorType=skia.kRGBA_8888_ColorType,
                             alphaType=skia.kPremul_AlphaType)
        alpha = array[..., 3]
        ambient = light.get('ambient')
        if ambient:
            a = ambient.get('amount', .1)
            tint = skia.Color4f(rgba(ambient['color']))
            ramp = np.arange(256, dtype=np.float32)
            for channel, value in enumerate((tint.fR, tint.fG, tint.fB)):
                array[..., channel] = np.take((ramp*(1-a+a*value)+.5).astype(np.uint8), array[..., channel])
        shade_mix = (ambient or {}).get('shade_mix', 0)
        warm = np.zeros(3, dtype=np.float32)
        if ambient:
            tone_c = skia.Color4f(rgba(ambient['color']))
            warm = np.array([tone_c.fR, tone_c.fG, tone_c.fB], dtype=np.float32)*.78
        for key in ('shade', 'rim'):
            spec = light.get(key)
            if not spec:
                continue
            dx, dy = spec['dir']
            norm = math.hypot(dx, dy) or 1
            reach = spec.get('width', 4)*self.k*view.zoom**.5*max(.6, v['scale']*1.6)
            # The band sits just inside the drawn outline: light painted on the ink line itself reads as a dotted fringe.
            inset = rig.d.get('outline', 2.5)*s*1.15
            h, w = alpha.shape

            def shifted(distance):
                # alpha(p + L*distance): opaque when the neighbour toward the light is still inside the figure.
                ox_, oy_ = round(dx/norm*distance), round(dy/norm*distance)
                out = np.zeros_like(alpha)
                out[max(0, -oy_):h-max(0, oy_), max(0, -ox_):w-max(0, ox_)] = alpha[max(0, oy_):h-max(0, -oy_), max(0, ox_):w-max(0, -ox_)]
                return out
            if round(reach) < 1:
                continue
            mask = (shifted(inset).astype(np.uint16)*(255-shifted(inset+reach)))//255
            mask = (mask*alpha.astype(np.uint16))//255
            ys, xs = np.nonzero(mask > 6)
            if not len(ys):
                continue
            weight = (mask[ys, xs].astype(np.float32)/255*spec.get('opacity', .4))[:, None]
            color = skia.Color4f(rgba(spec['color']))
            rgb = np.array([color.fR, color.fG, color.fB], dtype=np.float32)
            pixels = array[ys, xs, :3].astype(np.float32)
            if key == 'shade':
                pixels *= 1-weight*(1-rgb)
                if shade_mix > 0:
                    # Reflected sunset: shaded paint takes a touch of the ambient colour instead of going cold.
                    cover = alpha[ys, xs].astype(np.float32)[:, None]
                    pixels += (warm*cover-pixels)*np.minimum(1, weight*shade_mix)
            else:
                cover = alpha[ys, xs].astype(np.float32)[:, None]
                # Light lands on painted surfaces, not on ink: where an edge runs along the light direction the band
                # falls on the outline itself, and lighting it would split the line in two.
                tone = pixels.max(axis=1, keepdims=True)/np.maximum(cover, 1)
                weight = weight*np.clip((tone-.24)/.16, 0, 1)
                pixels += rgb*weight*(cover-pixels)
            array[ys, xs, :3] = np.clip(pixels+.5, 0, 255).astype(np.uint8)
        weight = max(.6, v['scale']*1.6)*self.k*view.zoom**.5
        contour = style.get('contour', 0)
        if contour > 0:
            # One heavier outer line around the whole figure, so it reads as a single drawing.
            reach = max(1, round(contour*weight))
            grown = alpha.copy()
            for axis in (0, 1):
                best = grown.copy()
                for shift in range(1, reach+1):
                    for sign in (1, -1):
                        moved = np.roll(grown, sign*shift, axis=axis)
                        edge = [slice(None), slice(None)]
                        edge[axis] = slice(0, shift) if sign > 0 else slice(-shift, None)
                        moved[tuple(edge)] = 0
                        np.maximum(best, moved, out=best)
                grown = best
            ys, xs = np.nonzero(grown > alpha)
            if len(ys):
                extra = (grown[ys, xs].astype(np.float32)-alpha[ys, xs])[:, None]
                ink = skia.Color4f(rgba(rig.colors['outline']))
                pixels = array[ys, xs, :3].astype(np.float32)+np.array([ink.fR, ink.fG, ink.fB], dtype=np.float32)*extra
                array[ys, xs, :3] = np.clip(pixels+.5, 0, 255).astype(np.uint8)
                array[ys, xs, 3] = grown[ys, xs]
        # Sit in the painting: lighter ink at small on-screen scales, then a hair of softness like the background's depth blur.
        lift = style.get('ink_lift', 0)*float(np.clip(1.6-.6*max(.6, v['scale']*1.6)*view.zoom**.5, .35, 1.0))
        if lift > 0:
            cover = array[..., 3].astype(np.float32)
            tone = array[..., :3].max(axis=2).astype(np.float32)/np.maximum(cover, 1)
            ys, xs = np.nonzero((cover > 0) & (tone < .34))
            if len(ys):
                w_ink = (np.clip((.34-tone[ys, xs])/.16, 0, 1)*lift)[:, None]
                target = np.array([.36, .22, .17], dtype=np.float32)*cover[ys, xs][:, None]
                pixels = array[ys, xs, :3].astype(np.float32)
                array[ys, xs, :3] = np.clip(pixels+(target-pixels)*w_ink+.5, 0, 255).astype(np.uint8)
        sigma = style.get('edge_soft', 0)*self.k*view.zoom**.5
        if sigma >= .3:
            from PIL import Image as _PIL, ImageFilter as _PF
            # Per channel: the data is premultiplied already, and Pillow would premultiply RGBA again.
            blur = _PF.GaussianBlur(sigma)
            array = np.stack([np.asarray(_PIL.fromarray(np.ascontiguousarray(array[..., c]), 'L').filter(blur))
                              for c in range(4)], axis=-1)
        image = skia.Image.fromarray(array, colorType=skia.kRGBA_8888_ColorType,
                                    alphaType=skia.kPremul_AlphaType)
        paint = skia.Paint(AntiAlias=True)
        if v['opacity'] < 1:
            paint.setAlphaf(v['opacity'])
        boil = style.get('boil', 0)*weight
        if boil <= 0:
            canvas.drawImage(image, left, up, nearest, paint)
            return
        # Line boil: the whole drawing is redrawn with a tiny wobble every few frames.
        w, h = right-left, down-up
        cell = max(18.0, 34*weight)
        nx, ny = max(2, int(w/cell)+2), max(2, int(h/cell)+2)
        gx, gy = np.meshgrid(np.linspace(0, w, nx), np.linspace(0, h, ny))
        index = int(t*self.fps+1e-6)//max(1, style.get('boil_hold', 3))
        rng = np.random.default_rng(int(hash01(performer.seed, 'boil', index)*4294967295))
        px = gx+rng.normal(0, boil, gx.shape).clip(-2*boil, 2*boil)
        py = gy+rng.normal(0, boil, gy.shape).clip(-2*boil, 2*boil)
        positions = [skia.Point(float(x)+left, float(y)+up) for x, y in zip(px.ravel(), py.ravel())]
        texs = [skia.Point(float(x), float(y)) for x, y in zip(gx.ravel(), gy.ravel())]
        indices = []
        for j in range(ny-1):
            for i in range(nx-1):
                k = j*nx+i
                indices += [k, k+1, k+nx, k+1, k+nx+1, k+nx]
        paint.setShader(image.makeShader(skia.TileMode.kDecal, skia.TileMode.kDecal, LINEAR))
        canvas.drawVertices(skia.Vertices(skia.Vertices.kTriangles_VertexMode, positions, texs, None, indices), paint)

    def _smear(self, base, change, figure, v, rig, style, smear, s):
        """Hide a drawing switch: dissolve toward the neighbouring drawing, then blur along x (the turn's motion)."""
        premul = skia.kPremul_AlphaType
        array = base.toarray(colorType=skia.kRGBA_8888_ColorType, alphaType=premul).astype(np.float32)
        mix = change['mix']*style.get('smear_mix', 0.0)    # >0 dissolves toward the other drawing (reads as a double image)
        if change['ghost'] and mix > 0:
            gv, gw = change['ghost']
            gv = dict(gv)
            for name in ('x', 'y', 'lift', 'scale', 'opacity', 'rot', 'shadow'):
                gv[name] = v[name]
            other = figure(gv, gw, rig.pose(gv, gw)).toarray(colorType=skia.kRGBA_8888_ColorType, alphaType=premul)
            array = array*(1-mix)+other.astype(np.float32)*mix
        reach = style.get('smear_px', 2.5)*smear*s
        taps = int(min(12, max(0, round(reach)))) 
        if taps:
            width = array.shape[1]
            total = array.copy()
            for shift in range(1, taps+1):
                weight = 1-shift/(taps+1)
                for sign in (1, -1):
                    total[:, max(0, sign*shift):width+min(0, sign*shift)] += weight*array[:, max(0, -sign*shift):width-max(0, sign*shift)]
            array = total/(1+2*sum(1-k/(taps+1) for k in range(1, taps+1)))
        array = np.clip(array+.5, 0, 255).astype(np.uint8)
        return skia.Image.fromarray(array, colorType=skia.kRGBA_8888_ColorType, alphaType=premul)

    def _contact(self, canvas, ox, oy, s, lift, ground, amount, pose=None, v=None):
        contact = ground.get('contact', {})
        if not contact:
            return
        fade = 1/(1+lift/(60*s+1e-6))
        w, h = contact.get('width', 120)*s*(.6+.4*fade), contact.get('height', 20)*s*(.6+.4*fade)
        color, opacity = contact.get('color', '#3b2a22'), contact.get('opacity', .30)*amount
        feet = [pose[key] for key in ('sole_l', 'sole_r') if pose and key in pose]
        paint = skia.Paint(AntiAlias=True, Color=rgba(color, opacity*fade*(.62 if feet else 1)))
        blur = max(1.0, h*.35)
        paint.setImageFilter(skia.ImageFilters.Blur(blur, blur*.6))
        canvas.drawOval(skia.Rect.MakeLTRB(ox-w/2, oy-h/2, ox+w/2, oy+h/2), paint)
        # Each sole darkens the ground where it touches and lets go as the foot lifts: this is what plants the feet.
        side = (1 if v['facing'] >= 0 else -1)*v['sx'] if v else 1
        for x, y, height in feet:
            touch = 1/(1+(height+lift/max(s, 1e-6))/7)
            fw, fh = contact.get('foot_width', 44)*s*(.7+.3*touch), contact.get('foot_height', 8.5)*s*(.7+.3*touch)
            fx, fy = ox+x*s*side, oy+(y+1.5)*s
            paint = skia.Paint(AntiAlias=True, Color=rgba(color, min(1.0, opacity*1.45)*touch))
            blur = max(.8, fh*.3)
            paint.setImageFilter(skia.ImageFilters.Blur(blur, blur*.7))
            canvas.drawOval(skia.Rect.MakeLTRB(fx-fw/2, fy-fh/2, fx+fw/2, fy+fh/2), paint)

    # ---- props ----
    def _prop(self, canvas, shot, prop, t, view, performers):
        channels = prop.get('channels', {})

        def value(name, default):
            keys = channels.get(name)
            return Track(keys).at(t) if keys else default
        opacity = value('opacity', 1.0)
        if opacity <= 0:
            return
        x, y = value('x', 0.0), value('y', 0.0)
        attach = value('attach', 0.0)
        if attach > 0 and prop.get('anchor'):
            anchor = prop['anchor']
            ax, ay = performers[anchor['actor']].anchor(anchor['point'], t)
            ax, ay = ax+anchor.get('dx', 0), ay+anchor.get('dy', 0)
            x, y = x+(ax-x)*attach, y+(ay-y)*attach
        depth = prop.get('depth', 1.0)
        sx, sy = view.to_screen(x, y, depth)
        image = self.image(prop['sheet'])
        cells = prop['cells']
        frame = value('frame', 0.0)
        index = max(0, min(len(cells)-1, int(round(frame))))
        x0, y0, x1, y1 = cells[index]
        scale = view.scale(depth)*value('scale', 1.0)*prop['upp']
        facing = -1 if value('facing', 1.0) < 0 else 1
        px, py = prop.get('pivot') or ((x1-x0)/2, (y1-y0)/2)
        if prop.get('shadow') and value('shadow', 1.0) > 0:
            gy = view.to_screen(x, prop['shadow'].get('ground', 650), depth)[1]
            height = max(0.0, gy-sy)
            fade = 1/(1+height/(140*view.scale(depth)))
            w = prop['shadow'].get('width', 26)*view.scale(depth)*value('scale', 1.0)*(.5+.5*fade)
            paint = skia.Paint(AntiAlias=True, Color=rgba('#3b2a22', .22*fade*opacity*value('shadow', 1.0)))
            paint.setImageFilter(skia.ImageFilters.Blur(w*.12, w*.06))
            canvas.drawOval(skia.Rect.MakeLTRB(sx-w/2, gy-w*.12, sx+w/2, gy+w*.12), paint)
        paint = skia.Paint(AntiAlias=True)
        if opacity < 1:
            paint.setAlphaf(opacity)
        canvas.save()
        canvas.translate(sx, sy)
        canvas.rotate(value('rot', 0.0))
        canvas.scale(scale*facing*value('sx', 1.0), scale*value('sy', 1.0))
        image.draw_rect(canvas, (x0, y0, x1, y1), skia.Rect.MakeXYWH(-px, -py, x1-x0, y1-y0), paint)
        canvas.restore()

    # ---- frame ----
    def compose(self, shot, t):
        stage_set = self.film['sets'][shot['set']]
        view = self.view(shot, t)
        surface = skia.Surface(self.width, self.height)
        canvas = surface.getCanvas()
        canvas.clear(rgba(stage_set.get('color', '#f1c98e')))
        if view.roll:
            canvas.rotate(view.roll, self.width/2, self.height/2)
        dof = Track(shot['dof']).at(t) if isinstance(shot.get('dof'), list) else shot.get('dof', 0.0)
        effects = self._set_effects(shot['set'], stage_set)
        clock = t+shot.get('clock', 0.0)
        for layer in stage_set['layers']:
            if not layer.get('front'):
                self._layer(canvas, layer, clock, view, dof)
        self._lights(canvas, stage_set.get('lights', []), clock, view, False)
        for front, effect in effects:
            if not front:
                effect.draw(canvas, clock, view)
        performers = self.performers(shot)
        light = dict(stage_set.get('light', {}))
        light.update(shot.get('light', {}))
        if light.get('ambient'):
            light['ambient'] = {**AMBIENT_DEFAULTS, **light['ambient']}
        style = dict(STYLE_DEFAULTS)
        style.update(self.film.get('style', {}))
        style.update(shot.get('style', {}))
        for prop in shot.get('props', []):
            if prop.get('layer') == 'back':
                self._prop(canvas, shot, prop, t, view, performers)
        # A front layer with an `order` goes between the actors: after those with a lower order, before the rest
        # (a blanket over the sleeper only, a door jamb over whoever walks through it). Without one it covers everyone.
        overrides = shot.get('layer_order', {})
        ranked = [(layer, overrides.get(layer.get('id'), layer.get('order'))) for layer in stage_set['layers'] if layer.get('front')]
        between = sorted([(order, i, layer) for i, (layer, order) in enumerate(ranked) if order is not None], key=lambda e: (e[0], e[1]))
        def order(actor):
            # An `order` channel (keys) wins over the static field: an actor can pass behind a door jamb mid-shot.
            keys = actor.get('channels', {}).get('order')
            return Track(keys).at(t) if keys else actor.get('order', 0)
        for actor in sorted(shot.get('actors', []), key=order):
            while between and between[0][0] <= order(actor):
                self._layer(canvas, between.pop(0)[2], clock, view, dof)
            self._actor(canvas, performers[actor.get('id', actor['character'])], t, view, light, style)
        for _, _, layer in between:
            self._layer(canvas, layer, clock, view, dof)
        for prop in shot.get('props', []):
            if prop.get('layer', 'front') == 'front':
                self._prop(canvas, shot, prop, t, view, performers)
        for layer, order in ranked:
            if order is None:
                self._layer(canvas, layer, clock, view, dof)
        for front, effect in effects:
            if front:
                effect.draw(canvas, clock, view)
        self._lights(canvas, stage_set.get('lights', []), clock, view, True)
        return surface.makeImageSnapshot()

    def finish(self, image, shot, t, frame_index):
        stage_set = self.film['sets'][shot['set']]
        params = shot.get('post', stage_set.get('post', self.film.get('post')))
        if params is not False:
            key = json.dumps(params, sort_keys=True)
            if key not in self._post:
                self._post[key] = fx.PostFX(self.width, self.height, params)
            image = self._post[key].apply(image, frame_index)
        overlays = shot.get('overlays', [])
        if not overlays:
            return image
        surface = skia.Surface(self.width, self.height)
        canvas = surface.getCanvas()
        canvas.drawImage(image, 0, 0)
        for item in overlays:
            kind = item['kind']
            if kind == 'fade':
                amount = Track(item['keys']).at(t)
                if amount > 0:
                    fx.draw_fade(canvas, amount, item.get('color', '#000000'))
            elif kind == 'iris':
                progress = Track(item['keys']).at(t)
                if progress < 1:
                    view = self.view(shot, t)
                    cx, cy = view.to_screen(item['x'], item['y'], 1.0)
                    fx.draw_iris(canvas, progress, cx, cy, self.width, self.height, item.get('color', '#1a120c'))
            elif kind == 'title':
                progress = Track(item['keys']).at(t)
                if progress > 0:
                    fx.draw_title(canvas, item['title'], item.get('subtitle', ''), progress, self.width, self.height)
        return surface.makeImageSnapshot()

    def frame(self, shot, t, frame_index=0, motion_blur=None):
        samples = shot.get('motion_blur', 1) if motion_blur is None else motion_blur
        if samples <= 1:
            return self.finish(self.compose(shot, t), shot, t, frame_index)
        total = None
        shutter = shot.get('shutter', .5)/self.fps
        for i in range(samples):
            ts = min(shot['duration'], max(0.0, t+((i+.5)/samples-.5)*shutter))
            array = self.compose(shot, ts).toarray(colorType=skia.kRGBA_8888_ColorType).astype(np.uint16)
            total = array if total is None else total+array
        array = ((total+samples//2)//samples).astype(np.uint8)
        array[..., 3] = 255
        return self.finish(skia.Image.fromarray(array, colorType=skia.kRGBA_8888_ColorType), shot, t, frame_index)

    def frame_array(self, shot, t, frame_index=0, motion_blur=None):
        return self.frame(shot, t, frame_index, motion_blur).toarray(colorType=skia.kRGBA_8888_ColorType)


def frame_count(shot, fps):
    return max(1, round(shot['duration']*fps))


def _encoder(path, width, height, fps, crf=20, preset='medium'):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('FFmpeg no está en PATH')
    command = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgba',
               '-s', f'{width}x{height}', '-r', str(fps), '-i', 'pipe:0', '-an', '-c:v', 'libx264', '-preset', preset,
               '-crf', str(crf), '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(path)]
    return subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def render_shot(film_path, shot_id, destination, width=None, first_frame=0, motion_blur=None, crf=20):
    film, root = load_film(film_path)
    stage = Stage(film, root, width)
    shot = next(s for s in film['shots'] if s['id'] == shot_id)
    process = _encoder(destination, stage.width, stage.height, stage.fps, crf)
    count = frame_count(shot, stage.fps)
    try:
        for index in range(count):
            process.stdin.write(stage.frame_array(shot, index/stage.fps, first_frame+index, motion_blur).tobytes())
        process.stdin.close()
        error = process.stderr.read().decode(errors='replace')
        if process.wait(timeout=120) != 0:
            raise RuntimeError('FFmpeg falló: '+error[-1500:])
    except BaseException:
        process.kill()
        raise
    return count


def render_film(film_path, destination, width=None, shots=None, workers=None, motion_blur=None, crf=20, progress=None, cancelled=None):
    """Render shots in parallel processes, then join the identical-codec segments without re-encoding.

    `progress(done, total, message)` is called as shots complete; `cancelled()` is polled between shots (best effort:
    shots already running in a worker are terminated) and a cancel raises RuntimeError. Output is unchanged without them."""
    from concurrent.futures import ProcessPoolExecutor
    import os
    film, root = load_film(film_path)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    selected = [s for s in film['shots'] if not shots or s['id'] in shots]
    parts = destination.parent/(destination.stem+'.parts')
    parts.mkdir(exist_ok=True)
    jobs, first = [], 0
    for shot in selected:
        jobs.append((str(film_path), shot['id'], str(parts/(shot['id']+'.mp4')), width, first, motion_blur, crf))
        first += frame_count(shot, film['fps'])
    workers = workers or max(1, min(len(jobs), (os.cpu_count() or 2)-2, 6))
    if workers == 1:
        counts = []
        for job in jobs:
            if cancelled and cancelled():
                raise RuntimeError('Render cancelado')
            counts.append(render_shot(*job))
            if progress:
                progress(len(counts), len(jobs), f'Plano {job[1]} listo')
    elif not (progress or cancelled):
        with ProcessPoolExecutor(workers) as pool:
            counts = list(pool.map(render_shot, *zip(*jobs)))
    else:
        from concurrent.futures import wait, FIRST_COMPLETED
        counts = [None]*len(jobs)
        with ProcessPoolExecutor(workers) as pool:
            pending = {pool.submit(render_shot, *job): n for n, job in enumerate(jobs)}
            try:
                while pending:
                    finished, _ = wait(list(pending), timeout=.5, return_when=FIRST_COMPLETED)
                    if cancelled and cancelled():
                        raise RuntimeError('Render cancelado')
                    for future in finished:
                        n = pending.pop(future)
                        counts[n] = future.result()
                        if progress:
                            progress(sum(c is not None for c in counts), len(jobs), f'Plano {jobs[n][1]} listo')
            except BaseException:
                for future in pending:
                    future.cancel()
                for process in list(getattr(pool, '_processes', {}).values()):   # best effort: stop running shots
                    process.terminate()
                raise
    listing = parts/'concat.txt'
    # Entries are resolved relative to the list file itself.
    listing.write_text(''.join(f"file '{Path(job[2]).name}'\n" for job in jobs), encoding='utf-8')
    command = [shutil.which('ffmpeg'), '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0',
               '-i', str(listing), '-c', 'copy', '-movflags', '+faststart', str(destination)]
    subprocess.run(command, check=True)
    return {'file': str(destination), 'frames': sum(counts), 'seconds': sum(counts)/film['fps'], 'shots': len(jobs)}


def contact_sheet(film, root, shots=None, columns=6, width=480, step=0.0, per_shot=None):
    """Contact sheet as a Skia image laid out in `columns` columns: `per_shot` (default `columns`) evenly spaced frames per shot,
    or one every `step` seconds."""
    import skia
    stage = Stage(film, root, width)
    tiles = []
    for shot in film['shots']:
        if shots and shot['id'] not in shots:
            continue
        count = max(1, int(shot['duration']/step)) if step else (per_shot or columns)
        for i in range(count):
            t = (i+.5)*shot['duration']/count
            tiles.append((f"{shot['id']} {t:.2f}s", stage.frame(shot, t)))
    rows = max(1, (len(tiles)+columns-1)//columns)
    surface = skia.Surface(columns*stage.width, rows*stage.height)
    canvas = surface.getCanvas()
    font = skia.Font(skia.Typeface('Arial'), 18)
    for i, (label, image) in enumerate(tiles):
        x, y = (i % columns)*stage.width, (i//columns)*stage.height
        canvas.drawImage(image, x, y)
        canvas.drawString(label, x+7, y+21, font, skia.Paint(Color=skia.ColorBLACK))
        canvas.drawString(label, x+6, y+20, font, skia.Paint(Color=skia.ColorWHITE))
    return surface.makeImageSnapshot()
