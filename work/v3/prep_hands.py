"""Cut the generated hand sheets (work/v3/art/hands/<cid>-hands.png) into hand2_<pose>.png and measure them.

Convention of the raw sheets: fingers point right, thumb on the upper side (a quarter turn anticlockwise from the
fingers, as the engine expects), flat vertical wrist cut on the left. Writes `hands2` into assets/<cid>/rig.json
(the old `hands` entry is left untouched). Run: python work/v3/prep_hands.py
"""
import json
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT/'work/v3/art/hands'
ASSETS = ROOT/'projects/taller-v3/assets'
POSES = ('closed', 'open', 'point')
PAD = 6
# Scale: each new hand gets the same on-screen area as the old sprite of that pose (old upp 0.3), times a tweak.
OLD_UPP = 0.3
UPP_MULT = {'closed': 1.3, 'open': 1.3, 'point': 1.3}


def split(arr):
    cols = (arr[..., 3] > 16).any(axis=0)
    runs, start = [], None
    for x, v in enumerate(cols):
        if v and start is None:
            start = x
        if not v and start is not None:
            runs.append((start, x)); start = None
    if start is not None:
        runs.append((start, len(cols)))
    runs = [r for r in runs if r[1]-r[0] > 60]
    assert len(runs) == 3, runs
    return runs


def process(cid, back=False):
    pre = 'hand2b_' if back else 'hand2_'
    sheet = np.array(Image.open(ART/(f'{cid}-hands-back.png' if back else f'{cid}-hands.png')).convert('RGBA'))
    rig = json.loads((ASSETS/cid/'rig.json').read_text(encoding='utf-8'))
    out = {}
    for pose, (x0, x1) in zip(POSES, split(sheet)):
        cell = sheet[:, x0:x1].copy()
        lab, n = ndi.label(cell[..., 3] > 16)
        sizes = ndi.sum(np.ones_like(lab), lab, range(1, n+1))
        cell[lab != 1+int(np.argmax(sizes))] = 0
        ys, xs = np.where(cell[..., 3] > 128)
        bx0, by0, bx1, by1 = xs.min(), ys.min(), xs.max(), ys.max()
        # the flat wrist cut is the left edge: use the rows that touch the first columns
        cutx = bx0
        rows = np.where(cell[:, cutx:cutx+3, 3].max(axis=1) > 128)[0]
        wy0, wy1 = rows.min(), rows.max()
        wrist_h = wy1-wy0+1
        sp = np.zeros((by1-by0+1+2*PAD, bx1-bx0+1+2*PAD, 4), np.uint8)
        sp[PAD:PAD+by1-by0+1, PAD:PAD+bx1-bx0+1] = cell[by0:by1+1, bx0:bx1+1]
        Image.fromarray(sp).save(ASSETS/cid/f'{pre}{pose}.png')
        wrist = [PAD+.5, (wy0+wy1+1)/2-by0+PAD]
        a = sp[..., 3] > 128
        oy, ox = np.where(a)
        d = (ox-wrist[0])**2+(oy-wrist[1])**2
        far = d >= np.percentile(d, 97)
        tip = np.array([ox[far].mean(), oy[far].mean()])-wrist
        ang = float(np.degrees(np.arctan2(tip[1], tip[0])))
        out[pose] = dict(file=f'{pre}{pose}.png', size=[sp.shape[1], sp.shape[0]], wrist=[round(float(wrist[0]), 1), round(float(wrist[1]), 1)],
                         dir_deg=round(ang, 1), wrist_h=int(wrist_h))
    for pose, v in out.items():
        if back:   # same on-screen size as the palm of the same pose: same area ratio -> match palm silhouette area
            palm = rig['hands2'][pose]
            pa = (np.array(Image.open(ASSETS/cid/palm['file']))[..., 3] > 128).sum()
            na = (np.array(Image.open(ASSETS/cid/v['file']))[..., 3] > 128).sum()
            v['upp'] = round(palm['upp']*float(np.sqrt(pa/na)), 5)
            continue
        old = (np.array(Image.open(ASSETS/cid/f'hand_{pose}.png'))[..., 3] > 128).sum()
        new = (np.array(Image.open(ASSETS/cid/v['file']))[..., 3] > 128).sum()
        v['upp'] = round(OLD_UPP*float(np.sqrt(old/new))*UPP_MULT[pose], 5)
    rig['hands2b' if back else 'hands2'] = out
    (ASSETS/cid/'rig.json').write_text(json.dumps(rig, indent=1), encoding='utf-8')
    print(cid, json.dumps(out))


if __name__ == '__main__':
    for cid in ('luma', 'pip'):
        process(cid)
        if (ART/f'{cid}-hands-back.png').exists():
            process(cid, back=True)
