import sys, time, pathlib
import numpy as np
import skia
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from celstudio.v2.fx import PostFX, Particles, Smoke, LightRays, draw_fade, draw_iris, draw_title

OUT = ROOT / "work" / "v3" / "fx-check"
OUT.mkdir(parents=True, exist_ok=True)
W, H = 1920, 1080


class View:
    def __init__(self, width, height, world_w=1280.0, world_h=720.0, cx=640.0, cy=360.0, zoom=1.0):
        self.width, self.height, self.world_w, self.world_h, self.cx, self.cy, self.zoom = width, height, world_w, world_h, cx, cy, zoom

    def scale(self, depth=1.0):
        return self.width / self.world_w * self.zoom ** depth

    def to_screen(self, x, y, depth=1.0):
        s = self.scale(depth)
        ex = self.world_w / 2 + (self.cx - self.world_w / 2) * depth
        ey = self.world_h / 2 + (self.cy - self.world_h / 2) * depth
        return (x - ex) * s + self.width / 2, (y - ey) * s + self.height / 2


def load_backdrop():
    im = Image.open(ROOT / "projects/taller-v3/source/valley-studio.png").convert("RGBA").resize((W, H), Image.LANCZOS)
    raw = skia.Image.fromarray(np.array(im), colorType=skia.kRGBA_8888_ColorType)
    s = skia.Surface(W, H)
    s.getCanvas().drawImage(raw, 0, 0)
    return s.makeImageSnapshot()  # premul raster, como lo entrega el compositor


def save(img, name):
    arr = img.toarray(colorType=skia.kRGBA_8888_ColorType)
    Image.fromarray(arr[..., :3]).save(OUT / name)


def new_canvas(bg):
    s = skia.Surface(W, H)
    c = s.getCanvas()
    c.drawImage(bg, 0, 0)
    return s, c


def ms(f, n=5):
    f()
    t0 = time.perf_counter()
    for _ in range(n):
        f()
    return (time.perf_counter() - t0) / n * 1000


bg = load_backdrop()
post = PostFX(W, H)

# 1
on = post.apply(bg, 3)
a, b = bg.toarray(colorType=skia.kRGBA_8888_ColorType)[..., :3], on.toarray(colorType=skia.kRGBA_8888_ColorType)[..., :3]
Image.fromarray(np.concatenate([a, b], 1)).resize((W, H // 2 + 0)).save(OUT / "1_postfx_side_by_side.png")
save(on, "1_postfx_on.png")

# 2
motes = Particles({"kind": "motes", "count": 70, "area": [0, 0, 1280, 720], "depth": 1.0, "opacity": 0.9}, 1)
leaves = Particles({"kind": "leaves", "count": 6, "area": [0, 0, 1280, 720], "depth": 1.0}, 2)
flies = Particles({"kind": "fireflies", "count": 8, "area": [60, 380, 1000, 640], "depth": 1.0, "opacity": 0.9}, 3)
smoke = Smoke({"x": 1128, "y": 125}, 4)
rays = LightRays({"x": 925, "y": 115}, 5)


def scene(t, view, base=bg):
    s = skia.Surface(W, H)
    c = s.getCanvas()
    c.clear(skia.ColorBLACK)
    ox, oy = view.to_screen(0, 0)
    c.save()
    c.translate(ox, oy)
    c.scale(view.scale() / (W / 1280.0), view.scale() / (W / 1280.0))
    c.drawImage(base, 0, 0, skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear))
    c.restore()
    rays.draw(c, t, view)
    motes.draw(c, t, view)
    flies.draw(c, t, view)
    smoke.draw(c, t, view)
    leaves.draw(c, t, view)
    return s.makeImageSnapshot()


v1 = View(W, H)
for t in (0.0, 1.0, 2.5):
    save(post.apply(scene(t, v1), 0), f"2_fx_t{t}.png")
v2 = View(W, H, cx=1050, cy=300, zoom=2.0)
save(post.apply(scene(1.0, v2), 0), "2_fx_zoom2.png")

# 3
for p in (0.3, 0.7):
    s, c = new_canvas(bg)
    draw_iris(c, p, 1128 * W / 1280, 125 * H / 720 + 300, W, H)
    save(s.makeImageSnapshot(), f"3_iris_{p}.png")
s, c = new_canvas(bg)
draw_fade(c, 0.5)
save(s.makeImageSnapshot(), "3_fade_0.5.png")

# 4
for p in (0.4, 1.0):
    s, c = new_canvas(bg)
    draw_title(c, "El taller del valle", "una pequeña bienvenida", p, W, H)
    save(post.apply(s.makeImageSnapshot(), 0), f"4_title_{p}.png")

# 5 determinism
def full(t):
    return scene(t, v1)

for name, fn in (("scene", lambda: post.apply(full(1.7), 5)),):
    x1 = fn().toarray(colorType=skia.kRGBA_8888_ColorType)
    x2 = PostFX(W, H).apply(full(1.7), 5).toarray(colorType=skia.kRGBA_8888_ColorType)
    assert x1.tobytes() == x2.tobytes(), "non deterministic"
# order independence
y1 = full(2.5).toarray(colorType=skia.kRGBA_8888_ColorType)
full(0.3); full(9.0)
y2 = full(2.5).toarray(colorType=skia.kRGBA_8888_ColorType)
assert y1.tobytes() == y2.tobytes()
assert not np.array_equal(post.apply(bg, 1).toarray(colorType=skia.kRGBA_8888_ColorType),
                          post.apply(bg, 2).toarray(colorType=skia.kRGBA_8888_ColorType))
print("determinism OK")

print("PostFX.apply: %.1f ms" % ms(lambda: post.apply(bg, 7)))
s, c = new_canvas(bg)
for name, obj in (("motes", motes), ("leaves", leaves), ("fireflies", flies), ("smoke", smoke), ("rays", rays)):
    print("%-10s %.1f ms" % (name, ms(lambda: obj.draw(c, 2.5, v1), 10)))
print("fade       %.1f ms" % ms(lambda: draw_fade(c, 0.5)))
print("iris       %.1f ms" % ms(lambda: draw_iris(c, 0.5, 900, 500, W, H)))
print("title      %.1f ms" % ms(lambda: draw_title(c, "El taller del valle", "una pequeña bienvenida", 1.0, W, H)))
