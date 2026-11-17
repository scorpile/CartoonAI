"""Prepara partes del titere v3 (recortes, mascara de cara, rig.json). Determinista."""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from scipy.spatial import ConvexHull

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, 'projects', 'taller-v3', 'source')
OUT = os.path.join(ROOT, 'projects', 'taller-v3', 'assets')
PAD = 6

def disk(r):
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r

def hexc(c):
    return '#%02x%02x%02x' % tuple(int(round(v)) for v in c[:3])

def lum(rgb):
    return rgb[..., 0] * .299 + rgb[..., 1] * .587 + rgb[..., 2] * .114

def clean_cell(cell):
    """Elimina motas de alfa bajo y conserva el componente principal."""
    a = cell[..., 3]
    lab, n = ndi.label(a > 16)
    sz = ndi.sum(np.ones_like(lab), lab, range(1, n + 1))
    keep = lab == (1 + int(np.argmax(sz)))
    keep = ndi.binary_dilation(keep, disk(2)) & (a > 0)
    out = cell.copy()
    out[~keep] = 0
    return out

def sheet_cell(sheet, i):
    r, c = divmod(i, 4)
    x0 = round(c * 313.5); x1 = round((c + 1) * 313.5)
    y0 = round(r * 313.5); y1 = round((r + 1) * 313.5)
    return clean_cell(sheet[y0:y1, x0:x1]), (x0, y0)

def dir_cell(img, row, col):
    cell = img[row * 443:(row + 1) * 444, col * 443:(col + 1) * 444]
    # filas/columnas: 887/2 y 1774/4
    y0 = round(row * 443.5); y1 = round((row + 1) * 443.5)
    x0 = round(col * 443.5); x1 = round((col + 1) * 443.5)
    return clean_cell(img[y0:y1, x0:x1]), (x0, y0)

def abbox(a, t=128):
    ys, xs = np.where(a > t)
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())

def crop_pad(arr, box, pad=PAD):
    x0, y0, x1, y1 = box
    h, w = arr.shape[:2]
    out = np.zeros((y1 - y0 + 1 + 2 * pad, x1 - x0 + 1 + 2 * pad) + arr.shape[2:], arr.dtype)
    sx0, sy0 = max(x0 - pad, 0), max(y0 - pad, 0)
    sx1, sy1 = min(x1 + pad + 1, w), min(y1 + pad + 1, h)
    out[sy0 - (y0 - pad):sy1 - (y0 - pad), sx0 - (x0 - pad):sx1 - (x0 - pad)] = arr[sy0:sy1, sx0:sx1]
    return out

def alpha_box(arr, t=16):
    return abbox(arr[..., 3], t)

def median_color(rgb, mask):
    return np.median(rgb[mask], axis=0)

def hull_mask(mask, ss=4):
    ys, xs = np.where(mask)
    pts = np.stack([xs, ys], 1).astype(float)
    hull = ConvexHull(pts)
    poly = pts[hull.vertices]
    h, w = mask.shape
    big = Image.new('L', (w * ss, h * ss), 0)
    ImageDraw.Draw(big).polygon([((x + .5) * ss, (y + .5) * ss) for x, y in poly], fill=255)
    return np.asarray(big.resize((w, h), Image.BOX)).astype(float) / 255.0

def skull_info(alpha, r=35):
    a = np.pad(alpha > 128, r + 2)
    core = ndi.distance_transform_edt(a) > r
    op = ndi.distance_transform_edt(~core) <= r
    return (op & a)[r + 2:-(r + 2), r + 2:-(r + 2)]

def estimate_skin(rgb, a):
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    m = (a > 250) & (R >= 235) & (G >= 195) & (G <= 235) & (B >= 130) & (B <= 205)
    q = (rgb[m] // 4 * 4).astype(int)
    vals, cnt = np.unique(q, axis=0, return_counts=True)
    mode = vals[np.argmax(cnt)] + 2
    d = np.abs(rgb - mode).sum(-1)
    return np.median(rgb[m & (d < 24)], axis=0)

def run_thickness(alpha, rgb, rows, dark=90):
    """Grosor del trazo exterior: longitud de la racha oscura desde el borde izquierdo/derecho."""
    out = []
    L = lum(rgb)
    for y in rows:
        xs = np.where(alpha[y] > 128)[0]
        if len(xs) == 0: continue
        for sgn, x in ((1, xs.min()), (-1, xs.max())):
            n = 0
            while 0 <= x < alpha.shape[1] and alpha[y, x] > 128 and L[y, x] < dark:
                n += 1; x += sgn
            if n: out.append(n)
    return float(np.median(out)) if out else 0.0

def kmeans2(px, iters=20):
    c = np.array([px[np.argmin(lum(px))], px[np.argmax(lum(px))]], float)
    for _ in range(iters):
        d = ((px[:, None, :] - c[None]) ** 2).sum(-1)
        l = d.argmin(1)
        for k in range(2):
            if (l == k).any(): c[k] = px[l == k].mean(0)
    return c, l

# ---------------------------------------------------------------- heads
def analyze_head(cell, want_mouth=False, ctx=None):
    """cell: RGBA array (limpio). Devuelve dict con plato (hull), skin y rasgos medidos."""
    rgb = cell[..., :3].astype(float); a = cell[..., 3]
    skin = estimate_skin(rgb, a)
    dist = np.abs(rgb - skin).sum(-1)
    cream = (dist < 40) & (a > 200)
    lab, n = ndi.label(cream)
    sz = ndi.sum(np.ones_like(lab), lab, range(1, n + 1))
    plate = lab == (1 + int(np.argmax(sz)))
    soft = hull_mask(plate)
    hull = soft > 0.5
    return dict(rgb=rgb, a=a, skin=skin, dist=dist, plate=plate, soft=soft, hull=hull)

def blank_head(cell, info):
    out = cell.copy().astype(float)
    rgb = info['rgb']; skin = info['skin']
    bl = (rgb[..., 0] > 215) & ((skin[1] - rgb[..., 1]) > 15) & ((skin[1] - rgb[..., 1]) < 100) & (lum(rgb) > 120)
    extra = ndi.binary_dilation(info['hull'], disk(4)) & bl & (cell[..., 3] > 200)
    extra = ndi.binary_dilation(extra, disk(1)) & ndi.binary_dilation(info['hull'], disk(4)) & (lum(rgb) > 120)
    s = np.maximum(info['soft'], extra.astype(float))[..., None]
    out[..., :3] = out[..., :3] * (1 - s) + skin[None, None, :] * s
    out[..., 3] = np.maximum(out[..., 3], s[..., 0] * 255)
    return np.clip(out + .5, 0, 255).astype(np.uint8)

def comps(mask, minarea=1):
    lab, n = ndi.label(mask)
    out = []
    for i in range(1, n + 1):
        m = lab == i
        ar = int(m.sum())
        if ar < minarea: continue
        ys, xs = np.where(m)
        out.append(dict(mask=m, area=ar, cx=xs.mean(), cy=ys.mean(), x0=xs.min(), y0=ys.min(), x1=xs.max(), y1=ys.max()))
    return out

def bbox_of(m):
    ys, xs = np.where(m)
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())

def meas_features(info, outline_t, kind):
    """Mide rasgos en la cabeza ORIGINAL (coordenadas de celda)."""
    rgb, a, skin, dist, hull = info['rgb'], info['a'], info['skin'], info['dist'], info['hull']
    L = lum(rgb)
    inner = ndi.binary_erosion(hull, disk(2))
    fx0, fy0, fx1, fy1 = bbox_of(hull)
    pcx = (fx0 + fx1) / 2
    white = inner & (rgb[..., 0] > 215) & (rgb[..., 1] > 215) & (rgb[..., 2] > 205)
    white = ndi.binary_opening(white, disk(1))
    dark = inner & (L < 70)
    res = {}
    wc = [c for c in comps(white, 25)]
    eyes = {}
    for side in ('l', 'r'):
        cs = [c for c in wc if (c['cx'] < pcx) == (side == 'l')]
        wm = np.zeros_like(white)
        for c in cs: wm |= c['mask']
        wx0, wy0, wx1, wy1 = bbox_of(wm)
        zone = np.zeros_like(white); zone[max(wy0 - 22, 0):wy1 + 23, max(wx0 - 22, 0):wx1 + 23] = True
        pu = ndi.binary_opening(ndi.binary_dilation(dark, disk(0)) & zone, disk(7))
        pcs = comps(pu, 40)
        pc = max(pcs, key=lambda c: c['area'])
        px0, py0, px1, py1 = pc['x0'], pc['y0'], pc['x1'], pc['y1']
        ix0, iy0, ix1, iy1 = min(wx0, px0), min(wy0, py0), max(wx1, px1), max(wy1, py1)
        t = outline_t_eye = max(outline_t * .55, 3)
        ox0, oy0, ox1, oy1 = ix0 - t, iy0 - t, ix1 + t, iy1 + t
        eyes[side] = dict(c=[(ox0 + ox1) / 2, (oy0 + oy1) / 2], rx=(ox1 - ox0) / 2, ry=(oy1 - oy0) / 2,
                          pupil=pc, wbox=(wx0, wy0, wx1, wy1), obox=(ox0, oy0, ox1, oy1), pmask=pc['mask'])
    res['eyes'] = eyes
    eye_bottom = max(e['obox'][3] for e in eyes.values()); eye_top = min(e['obox'][1] for e in eyes.values())
    eye_cy = np.mean([e['c'][1] for e in eyes.values()])
    # mascara de ojos para excluirlos
    ezone = np.zeros_like(white)
    for e in eyes.values():
        x0, y0, x1, y1 = e['obox']
        ezone[int(y0) - 3:int(y1) + 4, int(x0) - 3:int(x1) + 4] = True
    rest = dark & ~ezone
    rc = comps(ndi.binary_opening(rest, disk(0)), 12)
    brows = {}
    for side in ('l', 'r'):
        cs = [c for c in rc if c['cy'] < eye_cy and (c['cx'] < pcx) == (side == 'l')]
        if cs:
            c = max(cs, key=lambda c: c['area'])
            brows[side] = dict(c=[(c['x0'] + c['x1']) / 2, (c['y0'] + c['y1']) / 2], w=c['x1'] - c['x0'] + 1,
                               thickness=c['area'] / max(c['x1'] - c['x0'] + 1, 1) * 1.15, box=(c['x0'], c['y0'], c['x1'], c['y1']))
    res['brows'] = brows
    cs = [c for c in rc if c['cy'] > eye_bottom - 5 and c['area'] > 40]
    mc = max(cs, key=lambda c: c['area'])
    res['mouth'] = dict(c=[(mc['x0'] + mc['x1']) / 2, (mc['y0'] + mc['y1']) / 2], w=mc['x1'] - mc['x0'] + 1,
                        h=mc['y1'] - mc['y0'] + 1, box=(mc['x0'], mc['y0'], mc['x1'], mc['y1']),
                        thickness=mc['area'] / max(mc['x1'] - mc['x0'] + 1, 1) * 1.15)
    # nariz: no oscuro, marron, entre ojos y boca
    nz = inner & ~ezone & (dist > 50) & (L > 50) & (L < 140)
    nz &= (np.arange(a.shape[0])[:, None] > eye_cy - 5) & (np.arange(a.shape[0])[:, None] < res['mouth']['box'][1] + 2)
    nz = ndi.binary_opening(nz, disk(1))
    ncs = [c for c in comps(nz, 20) if abs(c['cx'] - pcx) < (fx1 - fx0) * .3 and c['area'] < 400]
    if ncs:
        c = max(ncs, key=lambda c: c['area'])
        res['nose'] = dict(c=[c['cx'], c['cy']], r=(np.sqrt(c['area'] / np.pi)), mask=c['mask'])
    else:
        res['nose'] = None
    # rubor
    bl = inner & ~ezone & (rgb[..., 0] > 225) & ((skin[1] - rgb[..., 1]) > 22) & ((skin[1] - rgb[..., 1]) < 90) & (L > 150)
    if res['nose'] is not None: bl &= ~ndi.binary_dilation(res['nose']['mask'], disk(3))
    bl &= ~ndi.binary_dilation(dark, disk(2))
    bl = ndi.binary_opening(bl, disk(3))
    bcs = [c for c in comps(bl, 150)]
    blush = {}
    for side in ('l', 'r'):
        cs = [c for c in bcs if (c['cx'] < pcx) == (side == 'l') and c['cy'] > eye_cy]
        if cs:
            c = max(cs, key=lambda c: c['area'])
            loose = ndi.binary_dilation(hull, disk(4)) & ~ezone & (rgb[..., 0] > 215) & ((skin[1] - rgb[..., 1]) > 15) & ((skin[1] - rgb[..., 1]) < 100) & (L > 120)
            llab, ln = ndi.label(loose)
            ids = np.unique(llab[c['mask'] & (llab > 0)])
            if len(ids):
                lm = np.isin(llab, ids)
                ys, xs = np.where(lm)
                c = dict(c, x0=xs.min(), y0=ys.min(), x1=xs.max(), y1=ys.max(), mask=lm)
            blush[side] = dict(c=[(c['x0'] + c['x1']) / 2, (c['y0'] + c['y1']) / 2], rx=(c['x1'] - c['x0'] + 1) / 2,
                               ry=(c['y1'] - c['y0'] + 1) / 2, mask=c['mask'])
    res['blush'] = blush
    res['white_mask'] = white
    # brillo en pupila
    hl = {}
    for side, e in eyes.items():
        pm = ndi.binary_fill_holes(e['pmask'])
        bright = pm & (L > 140)
        cs = comps(bright, 3)
        if cs:
            c = max(cs, key=lambda c: c['area'])
            pc_ = e['pupil']
            hl[side] = dict(r=np.sqrt(c['area'] / np.pi), off=[c['cx'] - (pc_['x0'] + pc_['x1']) / 2, c['cy'] - (pc_['y0'] + pc_['y1']) / 2])
    res['hl'] = hl
    return res

def appendages(alpha, kind):
    a = alpha > 128
    x0, y0, x1, y1 = bbox_of(a)
    r = int(round(0.38 * (y1 - y0)))
    op = skull_info(alpha, r)
    sx0, sy0, sx1, sy1 = bbox_of(op)
    scx, scy = (sx0 + sx1) / 2, (sy0 + sy1) / 2
    resid = a & ~ndi.binary_dilation(op, disk(2))
    resid = ndi.binary_opening(resid, disk(3))
    res = []
    contact = ndi.binary_dilation(op, disk(5))
    for c in comps(resid, 150):
        m = c['mask']
        ys, xs = np.where(m)
        d = (xs - scx) ** 2 + (ys - scy) ** 2
        far = d >= np.percentile(d, 97)
        tip = [float(xs[far].mean()), float(ys[far].mean())]
        # base: punto del componente mas cercano al craneo (centroide de los pixeles de contacto)
        mc = ndi.binary_dilation(m, disk(3)) & contact & a
        if mc.sum() == 0:
            continue
        cy_, cx_ = np.where(mc)
        base = [float(cx_.mean()), float(cy_.mean())]
        if base[1] > sy0 + 0.78 * (sy1 - sy0):
            continue
        if c['cy'] < sy0 + 0.1 * (sy1 - sy0) and abs(c['cx'] - scx) < 0.3 * (sx1 - sx0) and kind == 'pip':
            name = 'antenna'
        elif kind == 'pip':
            name = 'ear_l' if c['cx'] < scx else 'ear_r'
        else:
            name = 'ear_l' if c['cx'] < scx else 'ear_r'
        res.append(dict(name=name, base=base, tip=tip, mask=m))
    return (sx0, sy0, sx1, sy1), res

def neck_point(alpha, sk):
    sx0, sy0, sx1, sy1 = sk
    a = alpha > 128
    sub = a[sy1 - 4:sy1 + 1, :]
    xs = np.where(sub.any(0))[0]
    return [float((xs.min() + xs.max()) / 2), float(sy1) + .5]

def R(v, n=1):
    if isinstance(v, (list, tuple, np.ndarray)):
        return [R(x, n) for x in v]
    return round(float(v), n)

def build_head(cid, name, cell, outline_rows, outdir):
    info = analyze_head(cell)
    bx0, by0, bx1, by1 = alpha_box(cell, 16)
    ox, oy = bx0 - PAD, by0 - PAD
    thick = run_thickness(info['a'], info['rgb'], outline_rows)
    feat = meas_features(info, thick, cid)
    sk, apps = appendages(info['a'], cid)
    blank = blank_head(cell, info)
    sprite = crop_pad(blank, (bx0, by0, bx1, by1))
    Image.fromarray(sprite).save(os.path.join(outdir, f'head_{name}.png'))
    face = crop_pad((info['soft'] * 255 + .5).astype(np.uint8), (bx0, by0, bx1, by1))
    Image.fromarray(face, 'L').save(os.path.join(outdir, f'head_{name}_face.png'))
    orig = crop_pad(cell, (bx0, by0, bx1, by1))
    H, W = sprite.shape[:2]
    def P(p): return [p[0] - ox + .5, p[1] - oy + .5]  # centros de pixel -> coordenadas de borde
    neck = neck_point(info['a'], sk)
    fx0, fy0, fx1, fy1 = bbox_of(info['hull'])
    e = feat['eyes']
    prx = np.mean([(v['pupil']['x1'] - v['pupil']['x0'] + 1) / 2 for v in e.values()])
    pry = np.mean([(v['pupil']['y1'] - v['pupil']['y0'] + 1) / 2 for v in e.values()])
    def eye(v):
        x0, y0, x1, y1 = v['obox']
        return dict(c=R(P([(x0 + x1) / 2, (y0 + y1) / 2])), rx=R((x1 - x0 + 1) / 2), ry=R((y1 - y0 + 1) / 2))
    def rest(v):
        pc = v['pupil']
        return R([(pc['x0'] + pc['x1']) / 2 - (v['obox'][0] + v['obox'][2]) / 2, (pc['y0'] + pc['y1']) / 2 - (v['obox'][1] + v['obox'][3]) / 2])
    hl = feat['hl']
    h = dict(file=f'head_{name}.png', size=[W, H], origin_in_source=[ox, oy],
             neck=R(P(neck)), skull_bbox=R([sk[0] - ox, sk[1] - oy, sk[2] - ox + 1, sk[3] - oy + 1]),
             face_bbox=R([fx0 - ox, fy0 - oy, fx1 - ox + 1, fy1 - oy + 1]),
             eye_l=eye(e['l']), eye_r=eye(e['r']),
             pupil=dict(rx=R(prx), ry=R(pry),
                        highlight_r=R(np.mean([v['r'] for v in hl.values()])) if hl else R(max(2.0, prx * .22)),
                        highlight_offset=R(np.mean([v['off'] for v in hl.values()], 0)) if hl else R([prx * .28, -pry * .3]),
                        highlight_measured=bool(hl),
                        rest_offset_l=rest(e['l']), rest_offset_r=rest(e['r'])),
             mouth=dict(c=R(P(feat['mouth']['c'])), w=R(feat['mouth']['w']), thickness=R(feat['mouth']['thickness'])),
             nose=(dict(c=R(P(feat['nose']['c'])), r=R(feat['nose']['r'])) if feat['nose'] else None),
             blush_l=dict(c=R(P(feat['blush']['l']['c'])), rx=R(feat['blush']['l']['rx']), ry=R(feat['blush']['l']['ry'])),
             blush_r=dict(c=R(P(feat['blush']['r']['c'])), rx=R(feat['blush']['r']['rx']), ry=R(feat['blush']['r']['ry'])),
             appendages=[dict(name=ap['name'], base=R(P(ap['base'])), tip=R(P(ap['tip']))) for ap in apps])
    for s in ('l', 'r'):
        b = feat['brows'][s]
        h['brow_' + s] = dict(c=R(P(b['c'])), w=R(b['w']), thickness=R(b['thickness']))
    h['outline_px'] = R(thick)
    return dict(h=h, info=info, feat=feat, cell=cell, orig=orig, sprite=sprite, face=face, ox=ox, oy=oy, apps=apps, sk=sk)

def sample_colors_head(H0, H2):
    """Colores a partir de la cabeza frontal neutra (H0) y feliz (H2, boca abierta)."""
    info, feat = H0['info'], H0['feat']
    rgb, a = info['rgb'], info['a']
    L = lum(rgb)
    col = {}
    ring = (a > 250) & (L < 70)
    col['outline'] = median_color(rgb, ring)
    col['skin'] = info['skin']
    col['eye_white'] = median_color(rgb, ndi.binary_erosion(feat['white_mask'], disk(1)))
    pm = np.zeros_like(ring)
    for e in feat['eyes'].values(): pm |= e['pmask']
    col['pupil'] = median_color(rgb, ndi.binary_erosion(pm, disk(3)))
    bm = np.zeros_like(ring)
    for b in feat['blush'].values(): bm |= b['mask']
    col['blush'] = median_color(rgb, ndi.binary_erosion(bm, disk(2)))
    col['nose'] = median_color(rgb, ndi.binary_erosion(feat['nose']['mask'], disk(1)) if feat['nose'] else None) if feat['nose'] else None
    # boca abierta (celda feliz)
    i2, f2 = H2['info'], H2['feat']
    mb = f2['mouth']['box']
    # contorno oscuro de la boca -> rellenar huecos -> interior
    dk = np.zeros_like(i2['hull'])
    L2 = lum(i2['rgb'])
    dk[mb[1]:mb[3] + 1, mb[0]:mb[2] + 1] = (L2[mb[1]:mb[3] + 1, mb[0]:mb[2] + 1] < 70)
    filled = ndi.binary_fill_holes(dk)
    inside = ndi.binary_erosion(filled & ~dk, disk(2))
    px = i2['rgb'][inside]
    c, l = kmeans2(px)
    # boca = cluster mas oscuro; lengua = el mas claro
    dkc, lc = (c[0], c[1]) if lum(c[0:1])[0] < lum(c[1:2])[0] else (c[1], c[0])
    col['mouth_inside'] = dkc; col['tongue'] = lc
    return col, f2['mouth']

def skull_shift(skA, skB):
    return ((skA[0] + skA[2]) / 2 - (skB[0] + skB[2]) / 2, (skA[1] + skA[3]) / 2 - (skB[1] + skB[3]) / 2)

GRAY = (128, 128, 128, 255)

def on_gray(arr, scale=2):
    im = Image.fromarray(arr)
    bg = Image.new('RGBA', im.size, GRAY)
    bg.alpha_composite(im)
    return bg.resize((im.width * scale, im.height * scale), Image.NEAREST)

def draw_overlay(img, h, s=2):
    d = ImageDraw.Draw(img)
    def ell(c, rx, ry, col, w=1):
        d.ellipse([(c[0] - rx) * s, (c[1] - ry) * s, (c[0] + rx) * s, (c[1] + ry) * s], outline=col, width=w)
    def cross(c, col, r=6):
        d.line([(c[0] * s - r, c[1] * s), (c[0] * s + r, c[1] * s)], fill=col, width=1)
        d.line([(c[0] * s, c[1] * s - r), (c[0] * s, c[1] * s + r)], fill=col, width=1)
    for k, col in (('eye_l', (0, 255, 255, 255)), ('eye_r', (0, 255, 255, 255))):
        e = h[k]; ell(e['c'], e['rx'], e['ry'], col)
        off = h['pupil']['rest_offset_' + k[-1]]
        ell([e['c'][0] + off[0], e['c'][1] + off[1]], h['pupil']['rx'], h['pupil']['ry'], (255, 0, 255, 255))
    for k in ('brow_l', 'brow_r'):
        b = h[k]; d.line([(b['c'][0] - b['w'] / 2) * s, b['c'][1] * s, (b['c'][0] + b['w'] / 2) * s, b['c'][1] * s], fill=(255, 255, 0, 255), width=2)
    m = h['mouth']; d.line([(m['c'][0] - m['w'] / 2) * s, m['c'][1] * s, (m['c'][0] + m['w'] / 2) * s, m['c'][1] * s], fill=(255, 40, 40, 255), width=2)
    if h['nose']: ell(h['nose']['c'], h['nose']['r'], h['nose']['r'], (0, 255, 0, 255))
    for k in ('blush_l', 'blush_r'):
        b = h[k]; ell(b['c'], b['rx'], b['ry'], (255, 140, 0, 255))
    cross(h['neck'], (255, 255, 255, 255), 10)
    x0, y0, x1, y1 = h['skull_bbox']; d.rectangle([x0 * s, y0 * s, x1 * s, y1 * s], outline=(255, 255, 255, 255))
    x0, y0, x1, y1 = h['face_bbox']; d.rectangle([x0 * s, y0 * s, x1 * s, y1 * s], outline=(180, 180, 255, 255))
    for ap in h['appendages']:
        d.line([ap['base'][0] * s, ap['base'][1] * s, ap['tip'][0] * s, ap['tip'][1] * s], fill=(60, 120, 255, 255), width=2)
        cross(ap['base'], (60, 120, 255, 255), 5)
        ell(ap['tip'], 3, 3, (255, 60, 60, 255))
    return img

def heads_check(H, outdir):
    rows = []
    for name in ('front', '3q'):
        hh = H[name]
        a = on_gray(hh['sprite']); b = on_gray(hh['orig']); c = draw_overlay(on_gray(hh['orig']), hh['h'])
        row = Image.new('RGBA', (a.width * 3, a.height), GRAY)
        row.paste(a, (0, 0)); row.paste(b, (a.width, 0)); row.paste(c, (a.width * 2, 0))
        rows.append(row)
    W = max(r.width for r in rows)
    out = Image.new('RGBA', (W, sum(r.height for r in rows)), GRAY)
    y = 0
    for r in rows: out.paste(r, (0, y)); y += r.height
    out.convert('RGB').save(os.path.join(outdir, '_check_heads.png'))

def process_heads(cid, sheet, dirs, ci, outdir):
    H = {}
    c0, _ = sheet_cell(sheet, 0)
    H['front'] = build_head(cid, 'front', c0, range(130, 200), outdir)
    c3, _ = dir_cell(dirs, ci, 0)
    H['3q'] = build_head(cid, '3q', c3, range(190, 300), outdir)
    c2, _ = sheet_cell(sheet, 2)
    info2 = analyze_head(c2)
    f2 = meas_features(info2, H['front']['h']['outline_px'], cid)
    sk2, _ = appendages(info2['a'], cid)
    H2 = dict(info=info2, feat=f2)
    return H, H2, sk2


# ---------------------------------------------------------------- partes
def runs(mask1d):
    out = []; s = None
    for i, v in enumerate(mask1d):
        if v and s is None: s = i
        if not v and s is not None: out.append((s, i - 1)); s = None
    if s is not None: out.append((s, len(mask1d) - 1))
    return out

def save_crop(cell, path):
    box = alpha_box(cell, 16)
    sp = crop_pad(cell, box)
    Image.fromarray(sp).save(path)
    return sp, (box[0] - PAD, box[1] - PAD)

def dominant_colors(rgb, mask):
    px = rgb[mask]
    c, l = kmeans2(px)
    cnt = [int((l == k).sum()) for k in range(2)]
    return c, cnt

def cut_hand(cell, skin, outline_t, idx):
    rgb = cell[..., :3].astype(float); a = cell[..., 3]
    L = lum(rgb)
    dist = np.abs(rgb - skin).sum(-1)
    cream = (dist < 40) & (a > 200)
    cs = comps(ndi.binary_opening(cream, disk(2)), 300)
    key = 'cy' if idx == 7 else 'cx'
    hand = max(cs, key=lambda c: c[key])
    hm = hand['mask']
    colored = (a > 200) & (dist > 70) & (L > 110)
    colored = ndi.binary_opening(colored, disk(3))
    lab_c, n_c = ndi.label(colored)
    keep_ids = [i for i in range(1, n_c + 1) if (lab_c == i).sum() > 150]
    colored = np.isin(lab_c, keep_ids)
    dcol = ndi.distance_transform_edt(~colored)
    edge = hm & ~ndi.binary_erosion(hm)
    prox = edge & (dcol <= 14)
    ys, xs = np.where(prox)
    pts = np.stack([xs, ys], 1).astype(float)
    pc = pts.mean(0)
    u, s, vt = np.linalg.svd(pts - pc, full_matrices=False)
    tang = vt[0]
    n = np.array([-tang[1], tang[0]])
    if idx == 7: n = np.array([0.0, 1.0])
    if n @ (np.array([hand['cx'], hand['cy']]) - pc) < 0: n = -n
    proj = (pts - pc) @ n
    cut = float(np.percentile(proj, CUT_PCT))
    yy, xx = np.mgrid[:a.shape[0], :a.shape[1]]
    P = (xx - pc[0]) * n[0] + (yy - pc[1]) * n[1]
    near = ndi.binary_dilation(hm, disk(int(outline_t) + 4))
    sel = near & (P >= cut) & (a > 0)
    opened = ndi.binary_opening(np.pad(sel & (a > 128), 4), disk(2))[4:-4, 4:-4]
    sel &= ~((P < cut + 9) & ~ndi.binary_dilation(opened, disk(1)))
    out = cell.copy(); out[~sel] = 0
    lab, nn = ndi.label(out[..., 3] > 16)
    sz = ndi.sum(np.ones_like(lab), lab, range(1, nn + 1))
    out[lab != (1 + int(np.argmax(sz)))] = 0
    edge_px = (out[..., 3] > 128) & (P >= cut) & (P < cut + 1.5)
    ey, ex = np.where(edge_px)
    wrist = np.array([ex.mean(), ey.mean()])
    oy_, ox_ = np.where(out[..., 3] > 128)
    d = (ox_ - wrist[0]) ** 2 + (oy_ - wrist[1]) ** 2
    far = d >= np.percentile(d, 97)
    tipv = np.array([ox_[far].mean(), oy_[far].mean()]) - wrist
    ang = float(np.degrees(np.arctan2(tipv[1], tipv[0])))
    return out, wrist, ang

CUT_PCT = 80

def process_parts(cid, sheet, skin, outline_t_head, od):
    r = {}
    cells = {i: sheet_cell(sheet, i)[0] for i in range(16)}
    th = []
    for i in (6, 8, 9):
        c = cells[i]; x0, y0, x1, y1 = alpha_box(c, 128)
        th.append(run_thickness(c[..., 3], c[..., :3].astype(float), range(y0 + (y1 - y0) // 3, y0 + 2 * (y1 - y0) // 3), dark=45))
    parts_t = float(np.median(th))
    # torso
    c = cells[4]; sp, _ = save_crop(c, os.path.join(od, 'torso.png'))
    a = sp[..., 3] > 128; H, W = a.shape
    x0, y0, x1, y1 = bbox_of(a)
    L = lum(sp[..., :3].astype(float))
    top = (L < 75) & a; top[int(y0 + .3 * (y1 - y0)):] = False
    op = ndi.binary_opening(top, disk(6))
    lab, nn = ndi.label(op)
    if nn:
        sz = ndi.sum(np.ones_like(lab), lab, range(1, nn + 1)); m = lab == (1 + int(np.argmax(sz)))
        ys, xs = np.where(m); neck = [xs.mean() + .5, ys.mean() + .5]
    else:
        neck = [(x0 + x1 + 1) / 2, y0 + 8]
    sy = y0 + 0.30 * (y1 - y0)
    xs_row = np.where(a[int(sy)])[0]
    inset = 0.09 * (x1 - x0)
    r['torso'] = dict(file='torso.png', size=[W, H], neck=R(neck), shoulder_l=R([xs_row.min() + inset, sy]),
                      shoulder_r=R([xs_row.max() + 1 - inset, sy]), waist=R([(x0 + x1 + 1) / 2, y1 + 1]))
    # caderas
    c = cells[5]; sp, _ = save_crop(c, os.path.join(od, 'hips.png'))
    a = sp[..., 3] > 128; H, W = a.shape; x0, y0, x1, y1 = bbox_of(a)
    rs = sorted([q for q in runs(a[y1 - 6]) if q[1] - q[0] > 10], key=lambda q: q[0])
    if len(rs) >= 2:
        hl = [(rs[0][0] + rs[0][1] + 1) / 2, y1 - 6 + .5]; hr = [(rs[-1][0] + rs[-1][1] + 1) / 2, y1 - 6 + .5]
    else:
        hl = [x0 + (x1 - x0) * .25, y1 - 6]; hr = [x0 + (x1 - x0) * .75, y1 - 6]
    r['hips'] = dict(file='hips.png', size=[W, H], top=R([(x0 + x1 + 1) / 2, y0]), hip_l=R(hl), hip_r=R(hr))
    # manos
    r['hands'] = {}
    for name, idx in (('closed', 7), ('open', 11), ('point', 12)):
        out, wrist, ang = cut_hand(cells[idx], skin, outline_t_head, idx)
        box = alpha_box(out, 16)
        sp = crop_pad(out, box)
        Image.fromarray(sp).save(os.path.join(od, f'hand_{name}.png'))
        ox, oy = box[0] - PAD, box[1] - PAD
        r['hands'][name] = dict(file=f'hand_{name}.png', size=[sp.shape[1], sp.shape[0]],
                                wrist=R([wrist[0] - ox + .5, wrist[1] - oy + .5]), dir_deg=R(ang))
    # botas
    r['boots'] = {}
    for name, idx, fn in (('side', 10, 'boot_side.png'), ('tip', 13, 'boot_tip.png')):
        sp, _ = save_crop(cells[idx], os.path.join(od, fn))
        a = sp[..., 3] > 128; H, W = a.shape; x0, y0, x1, y1 = bbox_of(a)
        band = a.copy(); band[int(y0 + .08 * (y1 - y0)) + 1:] = False
        ys, xs = np.where(band)
        r['boots'][name] = dict(file=fn, size=[W, H], ankle=R([xs.mean() + .5, ys.mean() + .5]), sole_y=R(y1 + 1))
    # limbs
    def widths(i):
        a = cells[i][..., 3] > 128; return a, bbox_of(a), a.sum(1)
    a6, b6, w6 = widths(6); a8, b8, w8 = widths(8); a9, b9, w9 = widths(9)
    h8 = b8[3] - b8[1] + 1; h9 = b9[3] - b9[1] + 1
    wt = float(np.mean(w8[b8[1] + int(.05 * h8):b8[1] + int(.15 * h8) + 1]))
    wb = float(np.mean(w8[b8[3] - int(.15 * h8):b8[3] - int(.05 * h8) + 1]))
    c7 = cells[7]; rgb7 = c7[..., :3].astype(float); a7 = c7[..., 3] > 128; b7 = bbox_of(a7)
    xc = int(np.where(a7[b7[1] + 8])[0].mean())
    nd = (lum(rgb7[:, xc - 3:xc + 4]).mean(1) > 100) & a7[:, xc]
    rr = [q for q in runs(nd) if q[1] - q[0] >= 4]
    fore, cuff, hand = rr[0], rr[1], rr[2]
    fore_w = float(a7[(fore[0] + fore[1]) // 2].sum())
    fore_len = float(hand[0] - b7[1])
    def col_of(i):
        c = cells[i]; rgb = c[..., :3].astype(float); a = c[..., 3] > 200
        return rgb, ndi.binary_erosion(a, disk(int(parts_t) + 3)) & (lum(rgb) > 40)
    rgb6, m6 = col_of(6)
    cl, cn = dominant_colors(rgb6, m6)
    big = int(np.argmax(cn)); sleeve = cl[big]; other = cl[1 - big]
    shade = other if (lum(other[None])[0] < lum(sleeve[None])[0] - 12 and cn[1 - big] > .06 * sum(cn)) else sleeve
    forearm = np.median(rgb7[fore[0] + 3:fore[1] - 2, xc - 4:xc + 5].reshape(-1, 3), 0)
    cuffc = np.median(rgb7[cuff[0] + 2:cuff[1] - 1, xc - 4:xc + 5].reshape(-1, 3), 0)
    rgb8, m8 = col_of(8); rgb9, m9 = col_of(9)
    cl2, l2 = kmeans2(np.concatenate([rgb8[m8], rgb9[m9]]))
    thigh = np.median(rgb8[m8], 0); shin = np.median(rgb9[m9], 0)
    lo = cl2[int(np.argmin(lum(cl2)))]
    leg_shade = lo if lum(thigh[None])[0] - lum(lo[None])[0] > 8 else thigh
    r['limbs'] = dict(upper_arm_w=int(b6[2] - b6[0] + 1), forearm_w=R(fore_w), thigh_w_top=R(wt), thigh_w_bottom=R(wb),
                      shin_w=R(float(np.median(w9[b9[1] + int(.2 * h9):b9[3] - int(.2 * h9)]))),
                      upper_arm_len=int(b6[3] - b6[1] + 1), forearm_len=R(fore_len), thigh_len=int(h8), shin_len=int(h9))
    r['colors'] = dict(sleeve=hexc(sleeve), sleeve_shade=hexc(shade), forearm=hexc(forearm), cuff=hexc(cuffc),
                       thigh=hexc(thigh), shin=hexc(shin), leg_shade=hexc(leg_shade))
    r['parts_outline'] = R(parts_t)
    return r

def parts_check(rig, od):
    import math
    S = 2
    def load(fn): return Image.open(os.path.join(od, fn)).convert('RGBA')
    def cross(d, p, col, rr=7):
        d.line([p[0] * S - rr, p[1] * S, p[0] * S + rr, p[1] * S], fill=col, width=2)
        d.line([p[0] * S, p[1] * S - rr, p[0] * S, p[1] * S + rr], fill=col, width=2)
    def tile(fn, marks, arrow=None, hline=None):
        im = load(fn); bg = Image.new('RGBA', im.size, GRAY); bg.alpha_composite(im)
        bg = bg.resize((im.width * S, im.height * S), Image.NEAREST); d = ImageDraw.Draw(bg)
        for p, col in marks: cross(d, p, col)
        if arrow:
            w, deg = arrow
            ex, ey = w[0] + 50 * math.cos(math.radians(deg)), w[1] + 50 * math.sin(math.radians(deg))
            d.line([w[0] * S, w[1] * S, ex * S, ey * S], fill=(255, 255, 0, 255), width=3)
            d.ellipse([ex * S - 5, ey * S - 5, ex * S + 5, ey * S + 5], outline=(255, 255, 0, 255), width=3)
        if hline is not None:
            d.line([0, hline * S, bg.width, hline * S], fill=(40, 255, 40, 255), width=1)
        return bg
    RED, GRN, BLU, WHT = (255, 40, 40, 255), (40, 255, 40, 255), (60, 140, 255, 255), (255, 255, 255, 255)
    items = []
    t = rig['torso']; items.append(tile('torso.png', [(t['neck'], WHT), (t['shoulder_l'], RED), (t['shoulder_r'], RED), (t['waist'], BLU)]))
    t = rig['hips']; items.append(tile('hips.png', [(t['top'], WHT), (t['hip_l'], GRN), (t['hip_r'], GRN)]))
    for k, v in rig['hands'].items():
        items.append(tile(v['file'], [(v['wrist'], RED)], (v['wrist'], v['dir_deg'])))
    for k, v in rig['boots'].items():
        items.append(tile(v['file'], [(v['ankle'], RED)], None, v['sole_y']))
    half = (len(items) + 1) // 2
    rows = [items[:half], items[half:]]
    RW = max(sum(i.width for i in r_) + 10 * (len(r_) + 1) for r_ in rows)
    out = Image.new('RGBA', (RW, sum(max(i.height for i in r_) + 20 for r_ in rows)), GRAY)
    y = 10
    for r_ in rows:
        x = 10
        for i in r_: out.paste(i, (x, y)); x += i.width + 10
        y += max(i.height for i in r_) + 20
    out.convert('RGB').save(os.path.join(od, '_check_parts.png'))

def main():
    dirs = np.array(Image.open(f'{SRC}/heads-directional.png').convert('RGBA'))
    for ci, cid in enumerate(['luma', 'pip']):
        sheet = np.array(Image.open(f'{SRC}/{cid}-sheet.png').convert('RGBA'))
        od = os.path.join(OUT, cid); os.makedirs(od, exist_ok=True)
        H, H2, sk2 = process_heads(cid, sheet, dirs, ci, od)
        heads_check(H, od)
        col, mo = sample_colors_head(H['front'], H2)
        skin = H['front']['info']['skin']
        parts = process_parts(cid, sheet, skin, H['front']['h']['outline_px'], od)
        parts_check(parts, od)
        hf, h3 = H['front']['h'], H['3q']['h']
        h3['source'] = 'directional'; h3['looks'] = 'right' if cid == 'luma' else 'left'
        hf['source'] = 'sheet'
        for h in (hf, h3):
            h.pop('origin_in_source', None)
        sf = hf['skull_bbox']; s3 = h3['skull_bbox']
        scale = (sf[3] - sf[1]) / (s3[3] - s3[1])
        dx, dy = skull_shift(H['front']['sk'], sk2)
        mb = mo['box']; ox, oy = H['front']['ox'], H['front']['oy']
        x0, y0, x1, y1 = mb[0] + dx - ox, mb[1] + dy - oy, mb[2] + 1 + dx - ox, mb[3] + 1 + dy - oy
        colors = {k: (hexc(v) if v is not None else None) for k, v in col.items()}
        colors.update(parts.pop('colors'))
        order = ['outline', 'skin', 'eye_white', 'pupil', 'mouth_inside', 'tongue', 'blush', 'nose', 'sleeve', 'sleeve_shade', 'forearm', 'cuff', 'thigh', 'shin', 'leg_shade']
        rig = dict(colors={k: colors[k] for k in order},
                   outline_px=dict(head=hf.pop('outline_px'), head_3q=h3.pop('outline_px'), parts=parts.pop('parts_outline')),
                   heads=dict(front=hf, **{'3q': h3}),
                   head_scale_3q_over_front=round(scale, 4),
                   open_mouth_ref=dict(w=R(x1 - x0), h=R(y1 - y0), c=R([(x0 + x1) / 2, (y0 + y1) / 2])),
                   torso=parts['torso'], hips=parts['hips'], hands=parts['hands'], boots=parts['boots'], limbs=parts['limbs'])
        with open(os.path.join(od, 'rig.json'), 'w', encoding='utf-8') as f:
            json.dump(rig, f, indent=1)
        print(cid, 'ok')

if __name__ == '__main__':
    main()
