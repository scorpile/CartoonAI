"""Bosque: copy Codex layers, cut cloud/fg sprites, cut the door frame and the dark doorway out of main.png (so they can be drawn
in front of the actors), measure landmarks and write projects/tres-osos/sets/bosque.json. Texture import + measuring only."""
import json
import shutil
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT/'work/osos/art/sets/bosque'
PROJ = ROOT/'projects/tres-osos'
OUT = PROJ/'assets/sets/bosque'
OUT.mkdir(parents=True, exist_ok=True)
(PROJ/'sets').mkdir(exist_ok=True)

for n in ('sky', 'far', 'mid', 'main'):
    shutil.copy(ART/f'{n}.png', OUT/f'{n}.png')


def components(name, minimum=3000, merge=14):
    image = Image.open(ART/f'{name}.png').convert('RGBA')
    arr = np.array(image)
    alpha = arr[..., 3] > 24
    labels, count = ndimage.label(ndimage.binary_dilation(alpha, iterations=merge))
    items = []
    for index, box in enumerate(ndimage.find_objects(labels), 1):
        mask = (labels[box] == index) & alpha[box]
        if mask.sum() < minimum:
            continue
        y, x = box
        x0, y0, x1, y1 = max(0, x.start-3), max(0, y.start-3), min(image.width, x.stop+3), min(image.height, y.stop+3)
        crop = arr[y0:y1, x0:x1].copy()
        crop[~ndimage.binary_dilation(labels[y0:y1, x0:x1] == index, iterations=2)] = 0
        items.append(((x0, y0, x1, y1), Image.fromarray(crop)))
    items.sort(key=lambda it: (it[0][0], it[0][1]))
    res = []
    for i, (box, sprite) in enumerate(items):
        sprite.save(OUT/f'{name}-{i}.png')
        res.append({'file': f'assets/sets/bosque/{name}-{i}.png', 'box': box})
    return res


clouds = components('clouds')
fg = components('fg')

# ---- doorway in main.png ----
main = np.array(Image.open(ART/'main.png').convert('RGBA'))
H, W = main.shape[:2]
lum = main[..., :3].astype(float).mean(axis=2)
dark = (lum < 75) & (main[..., 3] > 200)
region = np.zeros_like(dark)
region[300:800, 1000:1400] = True
core = ndimage.binary_opening(dark & region, structure=np.ones((3, 3)), iterations=9)   # outlines are thin: only the doorway survives
labels, n = ndimage.label(core)
sizes = ndimage.sum(core, labels, range(1, n+1))
interior = ndimage.binary_dilation(labels == (1+int(np.argmax(sizes))), iterations=9) & dark
interior = ndimage.binary_closing(interior, structure=np.ones((3, 3)), iterations=14)   # take in the warm floor glow
interior = ndimage.binary_fill_holes(interior)
ys, xs = np.where(interior)
ib = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
# threshold slab just below the opening (grey stone): include it in the occluder so feet vanish too
thr = np.zeros_like(interior)
thr[ib[3]:ib[3]+40, ib[0]-12:ib[2]+16] = True
slab = thr & (main[..., 3] > 200) & ~interior
slab = ndimage.binary_closing(slab, iterations=3)
occluder = interior | slab
ring = ndimage.binary_dilation(interior, iterations=34) & ~occluder & (main[..., 3] > 0)
ring &= ~(thr & ~interior)


def cut(mask, name):
    out = main.copy()
    out[~mask] = 0
    Image.fromarray(out).save(OUT/f'{name}.png')


cut(occluder, 'door_dark')
cut(ring, 'door_frame')
# ground measurements
alpha = main[..., 3] > 128
ground_top_left = int(np.argmax(alpha[:, 40]))
ground_top_mid = int(np.argmax(alpha[:, W//3]))
measure = {'size': [W, H], 'interior_bbox': ib, 'ground_top_left': ground_top_left, 'ground_top_mid': ground_top_mid}
sky = np.array(Image.open(ART/'sky.png').convert('RGB')).astype(float).sum(axis=2)
yy, xx = np.where(sky > np.percentile(sky, 99.5))
measure['sun_px'] = [float(xx.mean()), float(yy.mean())]
measure['clouds'] = clouds
measure['fg'] = fg
(ART/'measure.json').write_text(json.dumps(measure, indent=1), encoding='utf-8')

# ---- world placement ----
MAIN_W = 1505.0
upp = MAIN_W/W
GROUND_Y = 640.0                    # actors' feet on the dirt path
path_center_row = 840
MAIN_X = 640.0
MAIN_Y = GROUND_Y-(path_center_row-H/2)*upp


def world(px, py):
    return (MAIN_X+(px-W/2)*upp, MAIN_Y+(py-H/2)*upp)


door_cx = (ib[0]+ib[2])/2
door_base = ib[3]
dx, dy = world(door_cx, door_base)
atop = world(door_cx, ib[1])[1]
sky_upp, sky_left, sky_top = 1340/1672, 640-670, 360-1340*941/1672/2


def placed(box, upp_, left, top):
    x0, y0, x1, y1 = box
    return {'x': left+(x0+x1)/2*upp_, 'y': top+(y0+y1)/2*upp_, 'w': (x1-x0)*upp_}


layers = [{'id': 'sky', 'image': 'assets/sets/bosque/sky.png', 'depth': .03, 'x': 640, 'y': 360, 'w': 1340, 'blur': .5}]
for i, c in enumerate(clouds):
    layers.append({'id': f'cloud{i}', 'image': c['file'], 'depth': .07, **placed(c['box'], sky_upp, sky_left, sky_top), 'blur': .8,
                   'drift': {'vx': 4.5+1.6*i, 'wrap': [-420, 1700]}})
layers += [
    {'id': 'far', 'image': 'assets/sets/bosque/far.png', 'depth': .14, 'x': 640, 'y': 200, 'w': 1700, 'blur': 1.0},
    {'id': 'mid', 'image': 'assets/sets/bosque/mid.png', 'depth': .38, 'x': 640, 'y': 372, 'w': 1700, 'blur': .75},
    {'id': 'main', 'image': 'assets/sets/bosque/main.png', 'depth': 1.0, 'x': MAIN_X, 'y': MAIN_Y, 'w': MAIN_W, 'blur': .15},
    # in front of the actors, same placement as main: pieces cut from main.png itself
    {'id': 'door_dark', 'image': 'assets/sets/bosque/door_dark.png', 'depth': 1.0, 'x': MAIN_X, 'y': MAIN_Y, 'w': MAIN_W, 'blur': .15, 'front': True},
    {'id': 'door_frame', 'image': 'assets/sets/bosque/door_frame.png', 'depth': 1.0, 'x': MAIN_X, 'y': MAIN_Y, 'w': MAIN_W, 'blur': .15, 'front': True},
]
fg_upp, fg_left, fg_top = 1460/1672, 640-730, 372-1460*941/1672/2
anchors = [(-.5, -.5), (.5, -.5), (-.5, .5), (.5, .5)]
for i, part in enumerate(fg):
    item = placed(part['box'], fg_upp, fg_left, fg_top)
    height = item['w']*(part['box'][3]-part['box'][1])/(part['box'][2]-part['box'][0])
    # keep cut edges (bottom/top touching the image border) outside every framing
    item['y'] += 30 if part['box'][3] >= H-4 else (-30 if part['box'][1] <= 4 else 0)
    ax, ay = anchors[min(i, 3)]
    layers.append({'id': f'fg{i}', 'image': part['file'], 'depth': 1.3, **item, 'blur': 1.0, 'front': True,
                   'sway': {'deg': 1.0, 'period': 4.6+i*.9, 'phase': .21*i, 'anchor': [ax*item['w'], ay*height]}})

sun = (sky_left+measure['sun_px'][0]*sky_upp, sky_top+measure['sun_px'][1]*sky_upp)
chim = world(1480, 150)
bosque = {
    'color': '#bfe0c8', 'ground_y': GROUND_Y,
    'notes': {
        'ground_y': GROUND_Y,
        'doorway': {'x': round(dx, 1), 'base_y': round(dy, 1), 'arch_top_y': round(atop, 1),
                    'width': round((ib[2]-ib[0])*upp, 1), 'height': round(dy-atop, 1),
                    'threshold_y': round(world(0, ib[3]+34)[1], 1),
                    'frame_x': [round(world(ib[0]-34, 0)[0], 1), round(world(ib[2]+34, 0)[0], 1)]},
        'path': {'y_center': GROUND_Y, 'y_from': round(world(0, 785)[1], 1), 'y_to': round(world(0, 895)[1], 1)},
        'entering': 'caminar por el sendero (y=640) hasta x~990, luego subir y de 640 a ~570 y escalar ~0.9: tras el umbral queda tapado por door_dark/door_frame (capas front)',
        'cabin_left_corner_x': round(world(760, 0)[0], 1), 'window_x': round(world(960, 0)[0], 1), 'chimney_top': [round(chim[0]), round(chim[1])],
    },
    'layers': layers,
    'lights': [
        {'x': round(sun[0], 1), 'y': round(sun[1], 1), 'depth': .03, 'radius': 260, 'color': '#ffd98a', 'opacity': .16, 'pulse': .05, 'period': 6.0},
        {'x': round(dx, 1), 'y': round(dy-20, 1), 'depth': 1.0, 'radius': 120, 'color': '#ffb85c', 'opacity': .22, 'pulse': .1, 'period': 2.7, 'flicker': 2.3},
    ],
    'smoke': [],
    'particles': [
        {'kind': 'motes', 'count': 36, 'area': [-100, 150, 1400, 700], 'depth': 1.25, 'color': '#fff0b8', 'size': 2.4, 'opacity': .45},
        {'kind': 'leaves', 'count': 2, 'area': [-100, -40, 1380, 700], 'depth': 1.2, 'opacity': .9, 'speed': .8},
    ],
    'rays': [{'x': round(sun[0], 1), 'y': round(sun[1], 1), 'depth': .1, 'count': 6, 'length': 880, 'spread_deg': 60, 'direction_deg': 52,
              'color': '#fff0c0', 'opacity': .08}],
    'light': {
        'ambient': {'color': '#ffd39a', 'amount': .09},
        'rim': {'dir': [-.7, -.66], 'color': '#ffe9b0', 'opacity': .6, 'width': 3.0},
        'shade': {'dir': [.75, .62], 'color': '#9aa0c0', 'opacity': .5, 'width': 5.5},
        'shadow': {'contact': {'width': 118, 'height': 20, 'opacity': .4, 'color': '#3f2a1c'},
                   'cast': {'shear': -.6, 'squash': .3, 'opacity': .2, 'blur': 4.5, 'color': '#3f2a1c'}},
    },
    'post': {'bloom': {'threshold': .82, 'sigma': .012, 'strength': .14},
             'grade': {'contrast': 1.05, 'saturation': 1.08, 'temperature': .02, 'lift': [0, 0, 0], 'gain': [1, 1, 1]},
             'vignette': {'strength': .18, 'radius': .85}, 'grain': {'amount': .02}},
}
# chimney smoke: tip of the chimney in main.png (measured by hand from the art: stone chimney top at ~(1485, 125))
cx, cy = world(1485, 120)
bosque['smoke'] = [{'x': round(cx, 1), 'y': round(cy, 1), 'depth': 1.0, 'rate': .8, 'rise': 30, 'life': 5.0, 'size': 11, 'drift': 9, 'opacity': .75}]
(PROJ/'sets/bosque.json').write_text(json.dumps(bosque, indent=1), encoding='utf-8')
print(json.dumps(bosque['notes'], indent=1), measure['interior_bbox'], ground_top_left, ground_top_mid)
