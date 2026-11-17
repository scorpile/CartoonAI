"""Cut and measure the generated art of Ricitos (work/osos/art/ricitos/*.png) into projects/tres-osos/assets/ricitos/.

Code only crops, cleans, measures; the art is generated. Writes rig.json (measurements) next to the PNGs.
Run: python work/osos/prep_ricitos.py
"""
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT/'work/osos/art/ricitos'
OUT = ROOT/'projects/tres-osos/assets/ricitos'
OUT.mkdir(parents=True, exist_ok=True)
PAD = 6
HEAD_MAX = 1000          # head sprites are reduced to this longest side (the originals are ~1300 px)

# Appendages (free ringlets), in ORIGINAL art pixels of each head sheet: base inside the hair mass, tip at the free end.
APPS = {
    'front': {'curl_l': ((235, 900), (190, 1130)), 'curl_l2': ((375, 930), (375, 1140)),
              'curl_r2': ((905, 940), (905, 1130)), 'curl_r': ((1115, 900), (1150, 1130)),
              'tuft': ((655, 250), (655, 45))},
    '3q': {'curl_l': ((330, 930), (310, 1215)), 'curl_r': ((960, 800), (990, 1090)),
           'tuft': ((700, 230), (690, 45))},
}
# Features as fractions of the face plate bbox (x, y) and sizes (fractions of w / h).
FEATS = {
    'front': dict(eye_l=(.29, .50, .125, .17), eye_r=(.71, .50, .125, .17), brow_l=(.29, .27, .24), brow_r=(.71, .27, .24),
                  mouth=(.50, .765, .22), nose=(.50, .635, .022), blush_l=(.17, .70, .10, .075), blush_r=(.83, .70, .10, .075)),
    '3q': dict(eye_l=(.44, .50, .14, .17), eye_r=(.84, .49, .105, .16), brow_l=(.44, .27, .25), brow_r=(.84, .27, .18),
               mouth=(.62, .765, .20), nose=(.69, .635, .02), blush_l=(.17, .72, .10, .075), blush_r=(.95, .69, .06, .07)),
}


def hexc(c):
    return '#%02x%02x%02x' % tuple(int(v) for v in c)


def alpha_box(a, t=16):
    ys, xs = np.where(a > t)
    return int(xs.min()), int(ys.min()), int(xs.max())+1, int(ys.max())+1


def skin_plate(arr):
    r, g, b, a = [arr[..., i].astype(int) for i in range(4)]
    skin = (a > 200) & (r > 225) & (b > 120) & (g > 170) & (r-b < 130)
    lab, n = ndi.label(skin)
    sizes = ndi.sum(skin, lab, range(1, n+1))
    plate = lab == 1+int(np.argmax(sizes))
    return ndi.binary_fill_holes(ndi.binary_closing(plate, iterations=3))


def head(name, src):
    arr = np.array(Image.open(ART/src).convert('RGBA'))
    x0, y0, x1, y1 = alpha_box(arr[..., 3])
    plate = skin_plate(arr)
    ys, xs = np.where(plate)
    px0, py0, px1, py1 = xs.min(), ys.min(), xs.max()+1, ys.max()+1
    skin = np.median(arr[plate][..., :3], axis=0)
    dark = arr[(arr[..., 3] > 250) & (arr[..., :3].astype(int).sum(axis=2) < 200)][..., :3]
    outline = np.median(dark, axis=0)
    gold = np.median(arr[(arr[..., 3] > 250) & (arr[..., 0] > 235) & (arr[..., 2] < 90)][..., :3], axis=0)
    k = min(1.0, HEAD_MAX/max(x1-x0, y1-y0))
    cx0, cy0 = x0-PAD, y0-PAD
    box = (cx0, cy0, x1+PAD, y1+PAD)
    crop = Image.fromarray(arr).crop(box)
    size = (round(crop.width*k), round(crop.height*k))
    crop.resize(size, Image.LANCZOS).save(OUT/f'head_{name}.png')
    m = Image.fromarray((plate*255).astype(np.uint8)).crop(box).resize(size, Image.LANCZOS).filter(ImageFilter.GaussianBlur(1.2))
    m.convert('L').save(OUT/f'head_{name}_face.png')

    def P(p):
        return [(p[0]-cx0)*k, (p[1]-cy0)*k]
    bbox = [(px0-cx0)*k, (py0-cy0)*k, (px1-cx0)*k, (py1-cy0)*k]
    w, h = bbox[2]-bbox[0], bbox[3]-bbox[1]

    def at(fx, fy):
        return [round(bbox[0]+fx*w, 1), round(bbox[1]+fy*h, 1)]
    f = FEATS[name]
    face = {'bbox': [round(v, 1) for v in bbox]}
    for side in 'lr':
        fx, fy, rx, ry = f['eye_'+side]
        face['eye_'+side] = {'c': at(fx, fy), 'rx': round(rx*w, 1), 'ry': round(ry*h, 1)}
        fx, fy, bw = f['brow_'+side]
        face['brow_'+side] = {'c': at(fx, fy), 'w': round(bw*w, 1), 'thickness': round(.012*w+2, 1)}
        fx, fy, rx, ry = f['blush_'+side]
        face['blush_'+side] = {'c': at(fx, fy), 'rx': round(rx*w, 1), 'ry': round(ry*h, 1)}
    fx, fy, mw = f['mouth']
    face['mouth'] = {'c': at(fx, fy), 'w': round(mw*w, 1), 'thickness': round(.014*w+2, 1)}
    fx, fy, nr = f['nose']
    face['nose'] = {'c': at(fx, fy), 'r': round(nr*w, 1)}
    apps = [{'name': n, 'base': [round(v, 1) for v in P(b)], 'tip': [round(v, 1) for v in P(t)]} for n, (b, t) in APPS[name].items()]
    return dict(file=f'head_{name}.png', size=list(size), neck=[round((bbox[0]+bbox[2])/2, 1), round(bbox[3]+.03*h, 1)],
                top=round((y0-cy0)*k, 1), face_bbox=face['bbox'], face=face, appendages=apps,
                plate_w=round(w, 1), plate_h=round(h, 1), skin=hexc(skin), outline=hexc(outline), gold=hexc(gold), k=k)


def torso():
    arr = np.array(Image.open(ART/'torso.png').convert('RGBA'))
    x0, y0, x1, y1 = alpha_box(arr[..., 3])
    k = min(1.0, 700/(y1-y0))
    img = Image.fromarray(arr).crop((x0-PAD, y0-PAD, x1+PAD, y1+PAD))
    img = img.resize((round(img.width*k), round(img.height*k)), Image.LANCZOS)
    img.save(OUT/'torso.png')
    px = np.array(img)
    a = px[..., 3]
    H, W = a.shape
    rgb = px[..., :3].astype(int)
    blue = (a > 250) & (rgb[..., 2] > 215) & (rgb[..., 0] < 190) & (rgb[..., 1] > 170)
    gown = np.median(rgb[blue], axis=0)
    skin = (a > 250) & (rgb[..., 0] > 240) & (rgb[..., 1] > 170) & (rgb[..., 1] < 215) & (rgb[..., 2] < 170) & (rgb[..., 2] > 110)
    ys, xs = np.where(skin)
    rows = np.where((a > 128).any(axis=1))[0]
    top_row, bottom = rows[0], rows[-1]

    def cols(y):
        c = np.where(a[y] > 128)[0]
        return int(c[0]), int(c[-1])
    sh_y = int(top_row+(bottom-top_row)*.30)
    bot = cols(int(bottom-8))
    return dict(file='torso.png', size=[W, H], gown=hexc(gown), neck=[float(xs.mean()), float(ys.min()+(ys.max()-ys.min())*.55)],
                waist=[(bot[0]+bot[1])/2, float(bottom)], shoulder_row=sh_y, shoulder_span=list(cols(sh_y)), width=bot[1]-bot[0], top=int(top_row))


def split(arr, minw=60):
    cols = (arr[..., 3] > 16).any(axis=0)
    runs, start = [], None
    for x, v in enumerate(cols):
        if v and start is None:
            start = x
        if not v and start is not None:
            runs.append((start, x)); start = None
    if start is not None:
        runs.append((start, len(cols)))
    return [r for r in runs if r[1]-r[0] > minw]


def hands(back):
    pre = 'handb_' if back else 'hand_'
    sheet = np.array(Image.open(ART/('hands-back.png' if back else 'hands-palm.png')).convert('RGBA'))
    runs = split(sheet)
    assert len(runs) == 3, runs
    out = {}
    for pose, (x0, x1) in zip(('closed', 'open', 'curled'), runs):
        cell = sheet[:, x0:x1].copy()
        lab, n = ndi.label(cell[..., 3] > 16)
        sizes = ndi.sum(np.ones_like(lab), lab, range(1, n+1))
        cell[lab != 1+int(np.argmax(sizes))] = 0
        ys, xs = np.where(cell[..., 3] > 128)
        bx0, by0, bx1, by1 = xs.min(), ys.min(), xs.max(), ys.max()
        rows = np.where(cell[:, bx0:bx0+3, 3].max(axis=1) > 128)[0]
        wy0, wy1 = rows.min(), rows.max()
        sp = np.zeros((by1-by0+1+2*PAD, bx1-bx0+1+2*PAD, 4), np.uint8)
        sp[PAD:PAD+by1-by0+1, PAD:PAD+bx1-bx0+1] = cell[by0:by1+1, bx0:bx1+1]
        Image.fromarray(sp).save(OUT/f'{pre}{pose}.png')
        wrist = [PAD+.5, (wy0+wy1+1)/2-by0+PAD]
        oy, ox = np.where(sp[..., 3] > 128)
        d = (ox-wrist[0])**2+(oy-wrist[1])**2
        far = d >= np.percentile(d, 97)
        tip = np.array([ox[far].mean(), oy[far].mean()])-wrist
        out[pose] = dict(file=f'{pre}{pose}.png', size=[sp.shape[1], sp.shape[0]], wrist=[round(float(wrist[0]), 1), round(float(wrist[1]), 1)],
                         dir_deg=round(float(np.degrees(np.arctan2(tip[1], tip[0]))), 1), wrist_h=int(wy1-wy0+1))
    return out


def curl_prop():
    """Equal-size tiles (root at the top centre of each) so one `pivot` serves the three poses: hang, swing, across."""
    sheet = np.array(Image.open(ART/'curl-props.png').convert('RGBA'))
    runs = split(sheet, 30)
    assert len(runs) == 3, runs
    cells = []
    for x0, x1 in runs:
        cell = sheet[:, x0:x1].copy()
        lab, n = ndi.label(cell[..., 3] > 16)
        sizes = ndi.sum(np.ones_like(lab), lab, range(1, n+1))
        cell[lab != 1+int(np.argmax(sizes))] = 0
        bx0, by0, bx1, by1 = alpha_box(cell[..., 3])
        top = cell[by0:by0+4, bx0:bx1, 3] > 128
        rx = float(np.where(top.any(axis=0))[0].mean())
        cells.append((cell[by0:by1, bx0:bx1], rx))
    tw = int(max(max(c.shape[1], 2*max(rx, c.shape[1]-rx)) for c, rx in cells))+2*PAD
    th = int(max(c.shape[0] for c, _ in cells))+2*PAD
    out = np.zeros((th, tw*3, 4), np.uint8)
    for i, (c, rx) in enumerate(cells):
        ox = int(round(tw/2-rx))
        out[PAD:PAD+c.shape[0], i*tw+ox:i*tw+ox+c.shape[1]] = c
    folder = ROOT/'projects/tres-osos/assets/props/curl'
    folder.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out).save(folder/'curl.png')
    spec = {'sheet': 'assets/props/curl/curl.png', 'cells': [[i*tw, 0, (i+1)*tw, th] for i in range(3)],
            'pivot': [tw/2, PAD+1.0], 'upp': round(30.0/(th-2*PAD), 4), 'layer': 'front'}
    (folder/'spec.json').write_text(json.dumps(spec, indent=1), encoding='utf-8')
    print('curl prop', spec)


def main():
    rig = {'heads': {'front': head('front', 'head-front.png'), '3q': head('3q', 'head-3q.png')}, 'torso': torso(),
           'hands': hands(False)}
    if (ART/'hands-back.png').exists():
        rig['hands_back'] = hands(True)
    if (ART/'curl-props.png').exists():
        curl_prop()
    (OUT/'rig.json').write_text(json.dumps(rig, indent=1), encoding='utf-8')
    for n, h in rig['heads'].items():
        print(n, h['size'], 'neck', h['neck'], 'plate', h['plate_w'], h['plate_h'], h['skin'], h['outline'], h['gold'])
    print('torso', {k: v for k, v in rig['torso'].items()})
    print('hands', {k: (v['size'], v['wrist_h'], v['dir_deg']) for k, v in rig['hands'].items()})


if __name__ == '__main__':
    main()
