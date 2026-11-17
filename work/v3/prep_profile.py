"""Corta y mide las vistas de perfil (cabeza y torso mirando a la derecha) de work/v3/art/profile/<id>-profile.png.

Escribe assets/<id>/head_profile.png, head_profile_face.png, torso_profile.png, _check_profile.png y añade las
claves `head_profile` y `torso_profile` a assets/<id>/rig.json (no toca nada más; no relanza prep_parts.py).
Determinista. Uso: python work/v3/prep_profile.py
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(__file__))
import prep_parts as pp

ART = os.path.join(pp.ROOT, 'work', 'v3', 'art', 'profile')
PAD = pp.PAD
# Luma: el naranja generado es mas saturado que el de las demas piezas; se lleva al tono medido (G y B).
ORANGE_SHIFT = {'luma': (0, 28, 32)}
# Proporciones del ojo/boca de perfil respecto al tres cuartos. EYE_V2 = False recupera las anteriores.
EYE_V2 = True
EYE_K = {'luma': .80, 'pip': .70}       # escala del ojo (el perfil es mas estrecho que el tres cuartos)
MOUTH_K = {'luma': .85, 'pip': .85}


def split_sheet(arr):
    cols = (arr[..., 3] > 16).any(axis=0)
    runs = [r for r in pp.runs(cols) if r[1] - r[0] > 40]
    # une tramos separados por menos de 30 px (antena, orejas)
    merged = [list(runs[0])]
    for a, b in runs[1:]:
        if a - merged[-1][1] < 30:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    assert len(merged) == 2, merged
    cells = []
    for a, b in merged:
        cell = np.zeros_like(arr)
        cell[:, a:b + 1] = arr[:, a:b + 1]
        cells.append(pp.clean_cell(cell))
    return cells


def recolor(cell, cid):
    shift = ORANGE_SHIFT.get(cid)
    if not shift:
        return cell
    out = cell.astype(float)
    r, g, b = out[..., 0], out[..., 1], out[..., 2]
    w = np.clip((r - 150) / 80, 0, 1) * ((b < 90) & (g < 150))
    for i, s in enumerate(shift):
        out[..., i] += s * w
    return np.clip(out + .5, 0, 255).astype(np.uint8)


def edge_x(plate, y, side):
    ys = int(np.clip(round(y), 0, plate.shape[0] - 1))
    xs = np.where(plate[ys])[0]
    return float(xs.max() + 1 if side == 'front' else xs.min())


def process_head(cid, cell, m, od):
    skin_hex = m['colors']['skin']
    skin = np.array([int(skin_hex[i:i + 2], 16) for i in (1, 3, 5)], float)
    cell = recolor(cell, cid)
    info = pp.analyze_head(cell)
    plate = ndi.binary_fill_holes(info['plate'])
    # placa: rellena con el color de piel del personaje; el borde antialias conserva la mezcla original
    out = cell.copy()
    out[plate, :3] = skin.round().astype(np.uint8)
    face = ndi.gaussian_filter(ndi.binary_dilation(plate, pp.disk(1)).astype(float), .8)
    bx0, by0, bx1, by1 = pp.alpha_box(out, 16)
    ox, oy = bx0 - PAD, by0 - PAD
    sprite = pp.crop_pad(out, (bx0, by0, bx1, by1))
    Image.fromarray(sprite).save(os.path.join(od, 'head_profile.png'))
    Image.fromarray(pp.crop_pad((face * 255 + .5).astype(np.uint8), (bx0, by0, bx1, by1)), 'L').save(os.path.join(od, 'head_profile_face.png'))
    H, W = sprite.shape[:2]
    P = lambda p: [p[0] - ox + .5, p[1] - oy + .5]
    sk, apps = pp.appendages(info['a'], cid)
    neck = pp.neck_point(info['a'], sk)
    px0, py0, px1, py1 = pp.bbox_of(plate)
    pw, ph = px1 - px0 + 1, py1 - py0 + 1
    # escala: el craneo de perfil mide lo mismo que el de tres cuartos
    h3 = m['heads']['3q']
    k = (h3['skull_bbox'][3] - h3['skull_bbox'][1]) / (sk[3] - sk[1] + 1)          # upp del perfil = upp 3q * k
    # medidas de los rasgos del tres cuartos, llevadas al mundo y de vuelta al dibujo de perfil
    eye3 = h3['eye_l'] if h3['eye_l']['ry'] > h3['eye_r']['ry'] else h3['eye_r']
    ry = min(eye3['ry'] / k, .24 * ph)
    rx = ry * .72
    es = 1.0
    if EYE_V2:
        es = EYE_K[cid]
        ry = min(eye3['ry'] / k, .24 * ph) * es
        rx = ry * .86
    cy = py0 + .46 * ph
    front = edge_x(plate, cy, 'front')
    cx = front - max(rx * 1.3, .26 * pw)
    pup = h3['pupil']
    brow_w = 2 * rx * 1.05
    brow = dict(c=P([cx + rx * .1, cy - 1.45 * ry]), w=pp.R(brow_w), thickness=pp.R(h3['brow_l']['thickness'] / k))
    my = py0 + .76 * ph
    mw = min(.5 * pw, h3['mouth']['w'] / k * (MOUTH_K[cid] if EYE_V2 else .62))
    mfront = edge_x(plate, my, 'front')
    mouth = dict(c=P([mfront - mw / 2 - (.05 if EYE_V2 else .08) * pw, my]), w=pp.R(mw), thickness=pp.R(h3['mouth']['thickness'] / k))
    nose = None
    if h3.get('nose'):
        ny = py0 + .60 * ph
        nr = h3['nose']['r'] / k
        if EYE_V2:      # the face mask clips whatever leaves the plate: a nose centred on the edge was mostly cut away
            nr *= 1.3
            nose = dict(c=P([edge_x(plate, ny, 'front') - nr * 1.45, ny]), r=pp.R(nr))
        else:
            nose = dict(c=P([edge_x(plate, ny, 'front') - nr * 1.1, ny]), r=pp.R(nr))
    bl = h3['blush_l']
    blush = dict(c=P([cx - rx * .5, py0 + .75 * ph]), rx=pp.R(bl['rx'] / k), ry=pp.R(bl['ry'] / k))
    prof = dict(file='head_profile.png', size=[W, H], neck=pp.R(P(neck)),
                skull_bbox=pp.R([sk[0] - ox, sk[1] - oy, sk[2] - ox + 1, sk[3] - oy + 1]),
                face_bbox=pp.R([px0 - ox, py0 - oy, px1 - ox + 1, py1 - oy + 1]),
                eye_r=dict(c=pp.R(P([cx, cy])), rx=pp.R(rx), ry=pp.R(ry)),
                pupil=dict(rx=pp.R(pup['rx'] / k * .9 * es), ry=pp.R(pup['ry'] / k * es), highlight_r=pp.R(pup['highlight_r'] / k * es),
                           highlight_offset=pp.R([abs(pup['highlight_offset'][0]) / k * .8 * es, pup['highlight_offset'][1] / k * es])),
                brow_r=brow, mouth=mouth, nose=nose, blush_r=blush,
                appendages=[dict(name=a['name'], base=pp.R(P(a['base'])), tip=pp.R(P(a['tip']))) for a in apps],
                upp_over_3q=pp.R(k, 4))
    return dict(h=prof, sprite=sprite, face=face)


def process_torso(cid, cell, m, od):
    cell = recolor(cell, cid)
    sp, _ = pp.save_crop(cell, os.path.join(od, 'torso_profile.png'))
    a = sp[..., 3] > 128
    H, W = a.shape
    x0, y0, x1, y1 = pp.bbox_of(a)
    t3 = m['torso']
    # misma altura en el mundo que el torso frontal
    front_h = t3['size'][1] - 2 * PAD
    k = front_h / (y1 - y0 + 1)                                   # sprite px frontales por px de perfil
    rows = np.where(a[int(y1 - .05 * (y1 - y0)):y1 + 1].any(axis=0))[0] if False else None
    xs_b = np.where(a[y1 - 6])[0]
    waist = [(xs_b.min() + xs_b.max() + 1) / 2, y1 + 1.0]
    xs_t = np.where(a[int(y0 + .09 * (y1 - y0))])[0]
    neck = [(xs_t.min() + xs_t.max() + 1) / 2, y0 + .09 * (y1 - y0)]
    sy = int(y0 + .30 * (y1 - y0))
    xs_s = np.where(a[sy])[0]
    shoulder = [(xs_s.min() + xs_s.max() + 1) / 2, float(sy)]
    return dict(file='torso_profile.png', size=[W, H], neck=pp.R(neck), shoulder=pp.R(shoulder), waist=pp.R(waist),
                upp_over_front=pp.R(k, 4))


def check(cid, head, torso, rig, od):
    S = 1
    def tile(fn):
        im = Image.open(os.path.join(od, fn)).convert('RGBA')
        bg = Image.new('RGBA', im.size, pp.GRAY); bg.alpha_composite(im)
        return bg
    h = tile('head_profile.png'); d = ImageDraw.Draw(h)
    f = rig['head_profile']
    def ell(c, rx, ry, col):
        d.ellipse([c[0] - rx, c[1] - ry, c[0] + rx, c[1] + ry], outline=col, width=2)
    ell(f['eye_r']['c'], f['eye_r']['rx'], f['eye_r']['ry'], (0, 255, 255, 255))
    pr = f['pupil']; ell(f['eye_r']['c'], pr['rx'], pr['ry'], (255, 0, 255, 255))
    b = f['brow_r']; d.line([b['c'][0] - b['w'] / 2, b['c'][1], b['c'][0] + b['w'] / 2, b['c'][1]], fill=(255, 255, 0, 255), width=4)
    mo = f['mouth']; d.line([mo['c'][0] - mo['w'] / 2, mo['c'][1], mo['c'][0] + mo['w'] / 2, mo['c'][1]], fill=(255, 40, 40, 255), width=4)
    if f['nose']: ell(f['nose']['c'], f['nose']['r'], f['nose']['r'], (0, 255, 0, 255))
    bl = f['blush_r']; ell(bl['c'], bl['rx'], bl['ry'], (255, 140, 0, 255))
    x0, y0, x1, y1 = f['face_bbox']; d.rectangle([x0, y0, x1, y1], outline=(180, 180, 255, 255), width=2)
    x0, y0, x1, y1 = f['skull_bbox']; d.rectangle([x0, y0, x1, y1], outline=(255, 255, 255, 255), width=2)
    n = f['neck']; d.line([n[0] - 20, n[1], n[0] + 20, n[1]], fill=(255, 255, 255, 255), width=3); d.line([n[0], n[1] - 20, n[0], n[1] + 20], fill=(255, 255, 255, 255), width=3)
    for ap in f['appendages']:
        d.line([ap['base'][0], ap['base'][1], ap['tip'][0], ap['tip'][1]], fill=(60, 120, 255, 255), width=4)
    t = tile('torso_profile.png'); d = ImageDraw.Draw(t)
    tt = rig['torso_profile']
    for p, col in ((tt['neck'], (255, 255, 255, 255)), (tt['shoulder'], (255, 40, 40, 255)), (tt['waist'], (60, 140, 255, 255))):
        d.line([p[0] - 14, p[1], p[0] + 14, p[1]], fill=col, width=3); d.line([p[0], p[1] - 14, p[0], p[1] + 14], fill=col, width=3)
    fh = Image.fromarray((head['face'] * 255).astype(np.uint8)).convert('RGBA')
    out = Image.new('RGBA', (h.width + t.width + 30, max(h.height, t.height) + 20), pp.GRAY)
    out.paste(h, (10, 10)); out.paste(t, (h.width + 20, 10))
    out.convert('RGB').resize((out.width // 2, out.height // 2)).save(os.path.join(od, '_check_profile.png'))


def main():
    for cid in ('luma', 'pip'):
        od = os.path.join(pp.OUT, cid)
        path = os.path.join(od, 'rig.json')
        m = json.load(open(path, encoding='utf-8'))
        arr = np.array(Image.open(os.path.join(ART, f'{cid}-profile.png')).convert('RGBA'))
        hc, tc = split_sheet(arr)
        head = process_head(cid, hc, m, od)
        torso = process_torso(cid, tc, m, od)
        m['head_profile'], m['torso_profile'] = head['h'], torso
        json.dump(m, open(path, 'w', encoding='utf-8'), indent=1)
        check(cid, head, torso, m, od)
        print(cid, 'head', head['h']['size'], 'upp/3q', head['h']['upp_over_3q'], 'torso', torso['size'], 'upp/front', torso['upp_over_front'])


if __name__ == '__main__':
    main()
