"""Dormitorio: copy Codex layers, cut the small bed's quilt out of beds.png as a front layer, measure landmarks and write
projects/tres-osos/sets/dormitorio.json. Texture import + measuring only."""
import json
import shutil
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT/'work/osos/art/sets/dormitorio'
PROJ = ROOT/'projects/tres-osos'
OUT = PROJ/'assets/sets/dormitorio'
OUT.mkdir(parents=True, exist_ok=True)

for n in ('wall', 'beds', 'door'):
    shutil.copy(ART/f'{n}.png', OUT/f'{n}.png')

beds = np.array(Image.open(ART/'beds.png').convert('RGBA'))
H, W = beds.shape[:2]
alpha = beds[..., 3] > 128
# separate objects: dilate to merge a bed, label
labels, n = ndimage.label(ndimage.binary_dilation(alpha, iterations=1))
objs = []
for i, box in enumerate(ndimage.find_objects(labels), 1):
    if (alpha[box] & (labels[box] == i)).sum() > 8000:
        objs.append((box[1].start, box[1].stop, box[0].start, box[0].stop, i))
objs.sort()
assert len(objs) == 4, objs
big, med, small, chest = objs
sx0, sx1, sy0, sy1, sid = small
r, g, b = (beds[..., k].astype(int) for k in range(3))
blue = (b > r+45) & (b > g+10) & alpha & (np.arange(W)[None, :] >= sx0) & (np.arange(W)[None, :] < sx1)
rows = np.where(blue.any(axis=1))[0]
quilt_top = int(rows.min())
# pillow of the small bed: cream pixels above the quilt inside the small bed
cream = (r > 225) & (g > 205) & (b > 170) & (b < 235) & alpha & (np.arange(H)[:, None] < quilt_top+20)
cream[:, :sx0] = False
cream[:, sx1:] = False
py, px = np.where(cream)
pillow = [int(px.min()), int(py.min()), int(px.max()), int(py.max())]
CUT = quilt_top-4
mask = np.zeros((H, W), bool)
mask[CUT:, sx0:sx1] = True
mask &= (labels == sid) & ndimage.binary_dilation(alpha, iterations=1)
front = beds.copy()
front[~mask] = 0
Image.fromarray(front).save(OUT/'blanket_small.png')
floor_row = max(o[3] for o in objs[:3])
# detail: bed rows
info = {'size': [W, H], 'bed_boxes': {'big': big[:4], 'medium': med[:4], 'small': small[:4], 'chest': chest[:4]},
        'quilt_top_row': quilt_top, 'cut_row': CUT, 'pillow_small_px': pillow, 'floor_row': floor_row}
(ART/'measure.json').write_text(json.dumps(info, indent=1), encoding='utf-8')

wall = np.array(Image.open(ART/'wall.png').convert('RGBA'))
# baseboard row: darkest horizontal band in the lower part
lum = wall[..., :3].astype(float).mean(axis=2)
rowmean = lum[int(H*.6):int(H*.9), 60:int(W*.1)].mean(axis=1)
base_row = int(H*.6)+int(np.argmin(rowmean))
info['baseboard_row'] = base_row

W_LAYER = 1380.0
upp = W_LAYER/W
X, Y = 640.0, 360.0


def wx(px_):
    return X+(px_-W/2)*upp


def wy(py_):
    return Y+(py_-H/2)*upp


FLOOR_Y = 655.0
notes = {
    'ground_y': FLOOR_Y,
    'floor_line_beds_y': round(wy(floor_row), 1),
    'baseboard_y': round(wy(base_row), 1),
    'beds_x': {k: [round(wx(v[0]), 1), round(wx(v[1]), 1)] for k, v in
               {'big': big, 'medium': med, 'small': small, 'chest': chest}.items()},
    'small_bed': {
        'pillow_center': [round(wx((pillow[0]+pillow[2])/2), 1), round(wy((pillow[1]+pillow[3])/2), 1)],
        'pillow_box': [round(wx(pillow[0]), 1), round(wy(pillow[1]), 1), round(wx(pillow[2]), 1), round(wy(pillow[3]), 1)],
        'blanket_top_y': round(wy(quilt_top), 1), 'blanket_cut_y': round(wy(CUT), 1),
        'blanket_x': [round(wx(sx0), 1), round(wx(sx1), 1)],
        'headboard_top_y': round(wy(sy0), 1),
    },
    'door_left': {'jamb_x': [0, round(wx(190), 1)], 'dark_opening_x': [0, round(wx(88), 1)]},
    'actors': ('Ricitos (actor detras): colocar y para que su cintura quede en blanket_top_y y su cabeza sobre pillow_center; '
               'la capa blanket (front) tapa de la cintura para abajo. Cualquier actor que pase por x en blanket_x entre y=blanket_cut_y '
               'y el suelo queda tapado por la manta: los osos deben quedarse a la izquierda de blanket_x[0] o a la derecha (zona del baul).'),
}
sunx, suny = wx(.64*W), wy(.3*H)
dorm = {
    'color': '#8a5a36', 'ground_y': FLOOR_Y, 'notes': notes,
    'layers': [
        {'id': 'wall', 'image': 'assets/sets/dormitorio/wall.png', 'depth': .94, 'x': X, 'y': Y, 'w': W_LAYER, 'blur': .15},
        {'id': 'beds', 'image': 'assets/sets/dormitorio/beds.png', 'depth': 1.0, 'x': X, 'y': Y, 'w': W_LAYER, 'blur': .1},
        {'id': 'blanket_small', 'image': 'assets/sets/dormitorio/blanket_small.png', 'depth': 1.0, 'x': X, 'y': Y, 'w': W_LAYER, 'blur': .1, 'front': True},
        {'id': 'door', 'image': 'assets/sets/dormitorio/door.png', 'depth': 1.0, 'x': X, 'y': Y, 'w': W_LAYER, 'blur': .1, 'front': True},
    ],
    'lights': [
        {'x': round(sunx, 1), 'y': round(suny, 1), 'depth': .94, 'radius': 230, 'color': '#ffe0a0', 'opacity': .22, 'pulse': .04, 'period': 6.0},
    ],
    'smoke': [],
    'particles': [{'kind': 'motes', 'count': 30, 'area': [300, 100, 1100, 620], 'depth': 1.1, 'color': '#fff0c0', 'size': 2.2, 'opacity': .5}],
    'rays': [{'x': round(sunx, 1), 'y': round(suny, 1), 'depth': .5, 'count': 4, 'length': 700, 'spread_deg': 30, 'direction_deg': 125,
              'color': '#fff0c0', 'opacity': .07}],
    'light': {
        'ambient': {'color': '#ffcf94', 'amount': .12},
        'rim': {'dir': [.75, -.5], 'color': '#ffe6b0', 'opacity': .42, 'width': 2.6},
        'shade': {'dir': [-.7, .6], 'color': '#a48a9a', 'opacity': .45, 'width': 5.0},
        'shadow': {'contact': {'width': 110, 'height': 18, 'opacity': .42, 'color': '#3a2415'},
                   'cast': {'shear': -.5, 'squash': .28, 'opacity': .14, 'blur': 5.0, 'color': '#3a2415'}},
    },
    'post': {'bloom': {'threshold': .82, 'sigma': .012, 'strength': .12},
             'grade': {'contrast': 1.05, 'saturation': 1.06, 'temperature': .03, 'lift': [0, 0, 0], 'gain': [1, 1, 1]},
             'vignette': {'strength': .25, 'radius': .8}, 'grain': {'amount': .02}},
}
(PROJ/'sets/dormitorio.json').write_text(json.dumps(dorm, indent=1), encoding='utf-8')
(ART/'measure.json').write_text(json.dumps(info, indent=1), encoding='utf-8')
print(json.dumps(notes, indent=1))
