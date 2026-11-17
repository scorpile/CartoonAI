"""Cut and measure the generated bear part sheets (work/osos/art/bears/<id>-{heads,body,hands}.png).

Writes projects/tres-osos/assets/<id>/*.png and assets/<id>/rig.json (measurements only; the engine rig comes from
build_rig_osos.py). Art is never drawn here: only cut, cleaned (alpha) and measured. Deterministic.
Usage: python work/osos/prep_bears.py [osito mama_osa papa_oso]
"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'v3'))
import prep_parts as pp

ROOT = pp.ROOT
ART = os.path.join(HERE, 'art', 'bears')
OUT = os.path.join(ROOT, 'projects', 'tres-osos', 'assets')
REVIEW = os.path.join(HERE, 'review', 'bears')
PAD = 6

# approximate colours (only used to find the pixels; the real colours are medians of those pixels)
CFG = {
    'osito':    dict(fur='#d08a40', muzzle='#fcd699', blush='#f2967a', eyes=dict(
        front=dict(dx=.205, dy=.150, rx=.115, ry=.140), q3=dict(dxl=.220, dxr=.125, rxl=.118, rxr=.080, dy=.150, ry=.140),
        prof=dict(dx=.215, dy=.130, rx=.070, ry=.125))),
    'mama_osa': dict(fur='#b57945', muzzle='#ecc99a', blush='#f09a80', eyes=dict(
        front=dict(dx=.200, dy=.150, rx=.100, ry=.125), q3=dict(dxl=.210, dxr=.115, rxl=.104, rxr=.074, dy=.150, ry=.125),
        prof=dict(dx=.205, dy=.130, rx=.062, ry=.115))),
    'papa_oso': dict(fur='#7c4a2f', muzzle='#e2b377', blush='#9a5a3c', eyes=dict(
        front=dict(dx=.185, dy=.150, rx=.082, ry=.105), q3=dict(dxl=.190, dxr=.110, rxl=.085, rxr=.062, dy=.150, ry=.105),
        prof=dict(dx=.195, dy=.125, rx=.053, ry=.098))),
}


def rgb_of(hexc):
    return np.array([int(hexc[i:i + 2], 16) for i in (1, 3, 5)], float)


def split_row(arr, n, mingap=40, minw=40):
    cols = (arr[..., 3] > 16).any(axis=0)
    runs = [r for r in pp.runs(cols) if r[1] - r[0] > minw]
    merged = [list(runs[0])]
    for a, b in runs[1:]:
        if a - merged[-1][1] < mingap:
            merged[-1][1] = b
        else:
            merged.append([a, b])
    assert len(merged) == n, merged
    cells = []
    for a, b in merged:
        cell = np.zeros_like(arr)
        cell[:, a:b + 1] = arr[:, a:b + 1]
        cells.append(pp.clean_cell(cell))
    return cells


def split_rows(arr, nrows):
    rows = (arr[..., 3] > 16).any(axis=1)
    runs = [r for r in pp.runs(rows) if r[1] - r[0] > 40]
    assert len(runs) == nrows, runs
    out = []
    for a, b in runs:
        strip = np.zeros_like(arr)
        strip[a:b + 1] = arr[a:b + 1]
        out.append(strip)
    return out


def save(arr, path):
    Image.fromarray(arr).save(path)


def crop(cell):
    box = pp.alpha_box(cell, 16)
    return pp.crop_pad(cell, box), box


def pick_color(rgb, a, approx, tol=45):
    d = np.abs(rgb - rgb_of(approx)).sum(-1)
    m = (a > 250) & (d < tol)
    return m, np.median(rgb[m], axis=0)


def outline_thickness(sprite):
    a = sprite[..., 3]
    y0, _, y1 = pp.abbox(a)[1], 0, pp.abbox(a)[3]
    rows = range(y0 + int((y1 - y0) * .4), y0 + int((y1 - y0) * .6))
    return pp.run_thickness(a, sprite[..., :3].astype(float), rows, dark=48)


def find_nose(rgb, a, sil, t, muzzle_c):
    """Nose = a dark blob thicker than the outline stroke: opening removes the strokes, the nose stays."""
    dark = (pp.lum(rgb) < 62) & (a > 200)
    r = max(5, int(t * .9))
    op = ndi.binary_opening(dark, pp.disk(r))
    cs = pp.comps(op, 80)
    cs = [c for c in cs if c['cy'] > np.where(sil.any(1))[0].min() + .45 * sil.any(1).sum()]
    mx, my = muzzle_c
    c = min(cs, key=lambda c: (c['cx'] - mx) ** 2 + (c['cy'] - my) ** 2 * .5)
    return c


def process_head(bid, view, cell, outdir, ref_t=None):
    cfg = CFG[bid]
    sprite, box = crop(cell)
    H, W = sprite.shape[:2]
    rgb = sprite[..., :3].astype(float)
    a = sprite[..., 3]
    sil = ndi.binary_fill_holes(a > 128)
    fur_m, fur = pick_color(rgb, a, cfg['fur'])
    muz_m, muzzle = pick_color(rgb, a, cfg['muzzle'])
    t = outline_thickness(sprite) if ref_t is None else ref_t
    # muzzle = component of muzzle-coloured pixels that is lowest/biggest (ear insides are small and high)
    muz_m = ndi.binary_opening(muz_m, pp.disk(4))
    mcs = pp.comps(muz_m, 400)
    big = max(mcs, key=lambda c: c['area'] * (1 if c['cy'] > H * .45 else .05))
    muzzle_mask = big['mask']
    mc = (big['cx'], big['cy'])
    nose = find_nose(rgb, a, sil, t, mc)
    dark_ring = (pp.lum(rgb) < 70) & (a > 250)
    outline_c = np.median(rgb[dark_ring & ~nose['mask']], axis=0)
    nose_c = np.median(rgb[ndi.binary_erosion(nose['mask'], pp.disk(3))], axis=0)
    # face plate = plain fur + muzzle + nose, minus ears and accessories (cap, bow) which stay outside the plate
    plate = ndi.binary_closing(fur_m | muz_m | ndi.binary_dilation(nose['mask'], pp.disk(3)), pp.disk(3))
    plate = ndi.binary_fill_holes(plate)
    lab, n = ndi.label(plate)
    sz = ndi.sum(np.ones_like(lab), lab, range(1, n + 1))
    plate = lab == (1 + int(np.argmax(sz)))
    ys, xs = np.where(sil)
    sh_full = ys.max() - ys.min()
    pa = (plate * 255).astype(np.uint8)
    skull_p = pp.skull_info(pa, int(.20 * sh_full))
    plate = ndi.binary_erosion(skull_p & plate, pp.disk(2))
    soft = ndi.gaussian_filter(plate.astype(float), 1.0)
    sk, _unused = pp.appendages(a, bid)
    scx = (sk[0] + sk[2]) / 2
    SW, SH = sk[2] - sk[0], sk[3] - sk[1]
    # ears: silhouette left once the skull (plus its outline ring) and the accessory (cap / bow) are taken out
    accessory = (rgb[..., 0] > 170) & (rgb[..., 1] < 120) & (rgb[..., 2] < 110) & (a > 200)
    accessory = ndi.binary_opening(accessory, pp.disk(3))
    plate_full = plate
    resid = sil & ~ndi.binary_dilation(skull_p, pp.disk(int(t * 1.3))) & ~ndi.binary_dilation(accessory, pp.disk(int(t * 1.2)))
    resid = ndi.binary_opening(resid, pp.disk(6))
    pys, pxs = np.where(skull_p)
    pcx, pcy = pxs.mean(), pys.mean()
    cands = [c for c in pp.comps(resid, 250) if c['cy'] < pcy]
    contact = ndi.binary_dilation(skull_p, pp.disk(int(t * 1.5) + 6))
    apps = []
    for c in cands:
        m_ = c['mask']
        ys_, xs_ = np.where(m_)
        d = (xs_ - pcx) ** 2 + (ys_ - pcy) ** 2
        far = d >= np.percentile(d, 97)
        tip = [float(xs_[far].mean()), float(ys_[far].mean())]
        mc_ = ndi.binary_dilation(m_, pp.disk(4)) & contact
        if not mc_.any():
            continue
        cy_, cx_ = np.where(mc_)
        apps.append(dict(name='ear_l' if c['cx'] < pcx else 'ear_r', base=[float(cx_.mean()), float(cy_.mean())], tip=tip, area=c['area'], cx=c['cx']))
    if view == 'profile':
        apps = sorted(apps, key=lambda p: -p['area'])[:1]
        for p in apps:
            p['name'] = 'ear_l'
    else:
        apps = sorted(apps, key=lambda p: p['cx'])
        apps = [apps[0], apps[-1]] if len(apps) > 1 else apps
    eyes = cfg['eyes']
    nx, ny = nose['cx'], nose['cy']
    skw, skh = SW, SH
    face = {}
    if view == 'front':
        e = eyes['front']
        mk = lambda sx: dict(c=[nx + sx * e['dx'] * skw, ny - e['dy'] * skh * 1.0], rx=e['rx'] * skw, ry=e['ry'] * skh)
        face['eye_l'], face['eye_r'] = mk(-1), mk(1)
    elif view == '3q':
        e = eyes['q3']
        face['eye_l'] = dict(c=[nx - e['dxl'] * skw, ny - e['dy'] * skh], rx=e['rxl'] * skw, ry=e['ry'] * skh)
        face['eye_r'] = dict(c=[nx + e['dxr'] * skw, ny - e['dy'] * skh * .95], rx=e['rxr'] * skw, ry=e['ry'] * skh * .98)
    else:
        e = eyes['prof']
        face['eye_r'] = dict(c=[nx - e['dx'] * skw, ny - e['dy'] * skh], rx=e['rx'] * skw, ry=e['ry'] * skh)
    mw_t = outline_thickness(sprite) if ref_t is None else ref_t
    for s in 'lr':
        if 'eye_' + s in face:
            ee = face['eye_' + s]
            face['brow_' + s] = dict(c=[ee['c'][0], ee['c'][1] - 1.5 * ee['ry']], w=ee['rx'] * 2.1, thickness=mw_t * .85)
    # mouth: on the muzzle under the nose
    if view == 'profile':
        mouth = dict(c=[nx - .060 * skw, ny + .115 * skh], w=.105 * skw, thickness=mw_t * .85)
    else:
        mouth = dict(c=[nx + (0 if view == 'front' else .004 * skw), ny + .105 * skh], w=.20 * skw if view == 'front' else .18 * skw, thickness=mw_t * .85)
    face['mouth'] = mouth
    # blush on the cheeks beside the muzzle
    if view == 'front':
        for s in 'lr':
            face['blush_' + ('l' if s == 'l' else 'r')] = dict(c=[nx + (-1 if s == 'l' else 1) * .30 * skw, ny - .015 * skh], rx=.065 * skw, ry=.045 * skh)
    elif view == '3q':
        face['blush_l'] = dict(c=[nx - .31 * skw, ny - .01 * skh], rx=.068 * skw, ry=.046 * skh)
        face['blush_r'] = dict(c=[nx + .20 * skw, ny - .02 * skh], rx=.035 * skw, ry=.044 * skh)
    else:
        face['blush_r'] = dict(c=[nx - .25 * skw, ny - .005 * skh], rx=.06 * skw, ry=.045 * skh)
    # feature box (+ margin): the engine clips the face layer to it
    boxes = []
    for k, v in face.items():
        if k.startswith('eye') or k.startswith('blush'):
            boxes.append([v['c'][0] - v['rx'], v['c'][1] - v['ry'], v['c'][0] + v['rx'], v['c'][1] + v['ry']])
        elif k.startswith('brow'):
            boxes.append([v['c'][0] - v['w'] / 2, v['c'][1] - v['w'] * .3, v['c'][0] + v['w'] / 2, v['c'][1] + v['w'] * .1])
        elif k == 'mouth':
            boxes.append([v['c'][0] - v['w'] / 2, v['c'][1] - v['w'] * .3, v['c'][0] + v['w'] / 2, v['c'][1] + v['w'] * 1.2])
    boxes.append([big['x0'], big['y0'], big['x1'], big['y1']])
    bx = np.array(boxes)
    mx0, my0, mx1, my1 = pp.bbox_of(plate)
    m = .08 * skw
    fbox = [max(bx[:, 0].min() - m, mx0), max(bx[:, 1].min() - m, my0), min(bx[:, 2].max() + m, mx1 + 1), min(bx[:, 3].max() + m, my1 + 1)]
    pupil_rx = np.mean([v['rx'] for k, v in face.items() if k.startswith('eye')]) * .58
    pupil_ry = np.mean([v['ry'] for k, v in face.items() if k.startswith('eye')]) * .68
    pupil = dict(rx=pupil_rx, ry=pupil_ry, highlight_r=max(2.0, pupil_rx * .30), highlight_offset=[pupil_rx * .30, -pupil_ry * .32])
    name = {'front': 'head_front', '3q': 'head_3q', 'profile': 'head_profile'}[view]
    save(sprite, os.path.join(outdir, name + '.png'))
    Image.fromarray((np.clip(soft, 0, 1) * 255 + .5).astype(np.uint8), 'L').save(os.path.join(outdir, name + '_face.png'))
    neck = pp.neck_point(a, sk)
    Rn = lambda v: pp.R(v, 1)
    out = dict(file=name + '.png', size=[W, H], neck=Rn(neck), skull_bbox=Rn([sk[0], sk[1], sk[2] + 1, sk[3] + 1]),
               face_bbox=Rn(fbox), pupil=pupil, mouth=mouth, nose=None,
               appendages=[dict(name=p['name'], base=Rn(p['base']), tip=Rn(p['tip'])) for p in apps])
    for k, v in face.items():
        if k not in ('mouth',):
            out[k] = v
    out = json.loads(json.dumps(out, default=lambda o: float(o)))
    return dict(h=out, sprite=sprite, plate=plate, fur=fur, muzzle=muzzle, outline=outline_c, nose=nose_c, t=t,
                nose_xy=(nx, ny), skull=sk)


def overlay_head(res, path):
    h = res['h']
    im = Image.fromarray(res['sprite'])
    bg = Image.new('RGBA', im.size, (128, 128, 128, 255))
    bg.alpha_composite(im)
    pl = np.zeros(im.size[::-1] + (4,), np.uint8)
    pl[res['plate']] = (255, 255, 255, 70)
    bg.alpha_composite(Image.fromarray(pl))
    d = ImageDraw.Draw(bg)
    for k in ('eye_l', 'eye_r'):
        if k in h:
            e = h[k]
            d.ellipse([e['c'][0] - e['rx'], e['c'][1] - e['ry'], e['c'][0] + e['rx'], e['c'][1] + e['ry']], outline=(0, 255, 255, 255), width=3)
            p = h['pupil']
            d.ellipse([e['c'][0] - p['rx'], e['c'][1] - p['ry'], e['c'][0] + p['rx'], e['c'][1] + p['ry']], outline=(255, 0, 255, 255), width=3)
    for k in ('brow_l', 'brow_r'):
        if k in h:
            b = h[k]
            d.line([b['c'][0] - b['w'] / 2, b['c'][1], b['c'][0] + b['w'] / 2, b['c'][1]], fill=(255, 255, 0, 255), width=4)
    m = h['mouth']
    d.line([m['c'][0] - m['w'] / 2, m['c'][1], m['c'][0] + m['w'] / 2, m['c'][1]], fill=(255, 40, 40, 255), width=4)
    for k in ('blush_l', 'blush_r'):
        if k in h:
            b = h[k]
            d.ellipse([b['c'][0] - b['rx'], b['c'][1] - b['ry'], b['c'][0] + b['rx'], b['c'][1] + b['ry']], outline=(255, 140, 0, 255), width=3)
    x0, y0, x1, y1 = h['face_bbox']
    d.rectangle([x0, y0, x1, y1], outline=(180, 180, 255, 255), width=2)
    x0, y0, x1, y1 = h['skull_bbox']
    d.rectangle([x0, y0, x1, y1], outline=(255, 255, 255, 255), width=2)
    for ap in h['appendages']:
        d.line([ap['base'][0], ap['base'][1], ap['tip'][0], ap['tip'][1]], fill=(60, 120, 255, 255), width=5)
    n = h['neck']
    d.line([n[0] - 20, n[1], n[0] + 20, n[1]], fill=(255, 255, 255, 255), width=4)
    return bg


def process_hand(cell, outdir, name):
    sprite, _ = crop(cell)
    a = sprite[..., 3]
    ys, xs = np.where(a > 128)
    bx0 = xs.min()
    rows = np.where(a[:, bx0:bx0 + 3].max(axis=1) > 128)[0]
    wy0, wy1 = rows.min(), rows.max()
    wrist = [bx0 + .5, (wy0 + wy1 + 1) / 2]
    oy, ox = np.where(a > 128)
    d = (ox - wrist[0]) ** 2 + (oy - wrist[1]) ** 2
    far = d >= np.percentile(d, 97)
    tip = np.array([ox[far].mean(), oy[far].mean()]) - wrist
    ang = float(np.degrees(np.arctan2(tip[1], tip[0])))
    save(sprite, os.path.join(outdir, name + '.png'))
    res = dict(file=name + '.png', size=[sprite.shape[1], sprite.shape[0]], wrist=[round(float(wrist[0]), 1), round(float(wrist[1]), 1)],
               dir_deg=round(ang, 1), wrist_h=int(wy1 - wy0 + 1))
    filled = ndi.binary_fill_holes(a > 128)
    holes = filled & ~(a > 128)
    holes = ndi.binary_opening(holes, pp.disk(2))
    lab, n = ndi.label(holes)
    if n:
        sz = ndi.sum(np.ones_like(lab), lab, range(1, n + 1))
        k = 1 + int(np.argmax(sz))
        hy, hx = np.where(lab == k)
        res['grip'] = [round(float(hx.mean() + .5), 1), round(float(hy.mean() + .5), 1)]
        res['grip_r'] = round(float(np.sqrt(sz.max() / np.pi)), 1)
    return res, sprite


def foot_info(sprite):
    return sprite


def process(bid):
    cfg = CFG[bid]
    od = os.path.join(OUT, bid)
    os.makedirs(od, exist_ok=True)
    os.makedirs(REVIEW, exist_ok=True)
    rig = {}
    # ---- heads
    arr = np.array(Image.open(os.path.join(ART, f'{bid}-heads.png')).convert('RGBA'))
    hf, h3, hp = split_row(arr, 3)
    F = process_head(bid, 'front', hf, od)
    Q = process_head(bid, '3q', h3, od, ref_t=F['t'])
    P = process_head(bid, 'profile', hp, od, ref_t=F['t'])
    ov = [overlay_head(r, None) for r in (F, Q, P)]
    sheet = Image.new('RGBA', (sum(o.width for o in ov) + 20, max(o.height for o in ov)), (128, 128, 128, 255))
    x = 0
    for o in ov:
        sheet.paste(o, (x, 0))
        x += o.width + 10
    sheet.convert('RGB').resize((sheet.width // 2, sheet.height // 2)).save(os.path.join(REVIEW, f'_heads_{bid}.png'))
    sf = F['h']['skull_bbox']
    s3 = Q['h']['skull_bbox']
    sp_ = P['h']['skull_bbox']
    scale3 = (sf[3] - sf[1]) / (s3[3] - s3[1])
    scalep = (sf[3] - sf[1]) / (sp_[3] - sp_[1]) / scale3
    P['h']['upp_over_3q'] = round(scalep, 4)
    colors = dict(outline=pp.hexc(F['outline']), fur=pp.hexc(F['fur']), muzzle=pp.hexc(F['muzzle']), nose=pp.hexc(F['nose']))
    rig['heads'] = dict(front=F['h'], **{'3q': Q['h']})
    rig['head_profile'] = P['h']
    rig['head_scale_3q_over_front'] = round(scale3, 4)
    rig['outline_px'] = dict(head=round(F['t'], 1))
    # ---- body
    arr = np.array(Image.open(os.path.join(ART, f'{bid}-body.png')).convert('RGBA'))
    tc, tpc, hc, fc = split_row(arr, 4)
    sp, _ = crop(tc)
    save(sp, os.path.join(od, 'torso.png'))
    a = sp[..., 3] > 128
    Ht, Wt = a.shape
    x0, y0, x1, y1 = pp.bbox_of(a)
    xs_top = np.where(a[y0 + int(.04 * (y1 - y0))])[0]
    neck = [(xs_top.min() + xs_top.max() + 1) / 2, y0 + .075 * (y1 - y0)]
    rig['torso'] = dict(file='torso.png', size=[Wt, Ht], neck=pp.R(neck), top=y0, waist=pp.R([(x0 + x1 + 1) / 2, y1 + 1]), body_bbox=[x0, y0, x1, y1])
    t_t = outline_thickness(sp)
    sp, _ = crop(tpc)
    save(sp, os.path.join(od, 'torso_profile.png'))
    a = sp[..., 3] > 128
    px0, py0, px1, py1 = pp.bbox_of(a)
    front_h = Ht - 2 * PAD
    k = front_h / (py1 - py0 + 1)
    xs_b = np.where(a[py1 - 6])[0]
    waist = [(xs_b.min() + xs_b.max() + 1) / 2, py1 + 1.0]
    xs_t = np.where(a[py0 + int(.09 * (py1 - py0))])[0]
    rig['torso_profile'] = dict(file='torso_profile.png', size=[a.shape[1], a.shape[0]], waist=pp.R(waist),
                                neck=pp.R([(xs_t.min() + xs_t.max() + 1) / 2, py0 + .075 * (py1 - py0)]),
                                shoulder=pp.R([(xs_t.min() + xs_t.max() + 1) / 2, py0 + .30 * (py1 - py0)]), upp_over_front=pp.R(k, 4))
    sp, _ = crop(hc)
    save(sp, os.path.join(od, 'hips.png'))
    rig['hips'] = dict(file='hips.png', size=[sp.shape[1], sp.shape[0]])
    sp, _ = crop(fc)
    save(sp, os.path.join(od, 'boot_side.png'))
    a = sp[..., 3] > 128
    Hf, Wf = a.shape
    x0, y0, x1, y1 = pp.bbox_of(a)
    rig['boots'] = dict(side=dict(file='boot_side.png', size=[Wf, Hf], sole_y=y1 + 1.0, bbox=[x0, y0, x1, y1]))
    # fur colour of the limbs, measured from the foot ankle
    fm, fur_limb = pick_color(sp[..., :3].astype(float), sp[..., 3], cfg['fur'], 60)
    rig['outline_px']['parts'] = round(t_t, 1)
    # ---- hands
    arr = np.array(Image.open(os.path.join(ART, f'{bid}-hands.png')).convert('RGBA'))
    top, bottom = split_rows(arr, 2)
    names = ('closed', 'open', 'point', 'grip')
    rig['hands'], rig['handsb'] = {}, {}
    for row, key, pre in ((top, 'hands', 'hand_'), (bottom, 'handsb', 'handb_')):
        cells = split_row(row, 4, mingap=30, minw=60)
        for nm, c in zip(names, cells):
            info, _ = process_hand(c, od, pre + nm)
            rig[key][nm] = info
    pal = np.array(Image.open(os.path.join(od, 'hand_closed.png')))
    hm, hand_fur = pick_color(pal[..., :3].astype(float), pal[..., 3], cfg['fur'], 60)
    colors['limb'] = pp.hexc(np.median(np.stack([fur_limb, hand_fur, F['fur']]), axis=0))
    colors['blush'] = cfg['blush']
    rig['colors'] = colors
    with open(os.path.join(od, 'rig.json'), 'w', encoding='utf-8') as f:
        json.dump(rig, f, indent=1)
    print(bid, 'ok', colors, 'head sizes', F['h']['size'], Q['h']['size'], P['h']['size'])


if __name__ == '__main__':
    for bid in (sys.argv[1:] or ['osito', 'mama_osa', 'papa_oso']):
        process(bid)
