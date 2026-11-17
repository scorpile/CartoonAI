"""Measured parts (assets/<id>/rig.json from prep_bears.py) -> engine rigs (projects/tres-osos/characters/<id>.json).

Registration only. Size: osito is the reference (factor 1.0, Luma-sized); mama 1.15x; papa 1.35x and broader (wm).
Usage: python work/osos/build_rig_osos.py
"""
import json, os
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
PROJ = ROOT/'projects/tres-osos'

# f: overall size (the stage clips a figure at 400 world units above the ground, so papa must stay below ~390)
# f: overall size; wm: extra width of torso / hips / limbs; widths in world units at actor scale 1 (before f*wm)
CFG = {
    'osito':    dict(name='Osito', f=.85, wm=1.0, skull=122.0, torso=106.0, hips=82.0, foot=60.0, arm=29.0, leg=33.0, sx=.37, sy=.24,
                     blush_alpha=1.0),
    'mama_osa': dict(name='Mama osa', f=1.055, wm=1.0, skull=122.0, torso=100.0, hips=96.0, foot=58.0, arm=27.0, leg=31.0, sx=.37, sy=.20,
                     blush_alpha=1.0),
    'papa_oso': dict(name='Papa oso', f=1.15, wm=1.12, skull=122.0, torso=100.0, hips=88.0, foot=60.0, arm=28.0, leg=33.0, sx=.37, sy=.26,
                     blush_alpha=0.0),
}
EAR = {'ear_l': dict(freq=5.0, damp=.3, gain=.55, spread=.8), 'ear_r': dict(freq=5.4, damp=.3, gain=.55, spread=.8)}


def mix(a, b, u):
    a, b = a.lstrip('#'), b.lstrip('#')
    return '#%02x%02x%02x' % tuple(round(int(a[i:i+2], 16)*(1-u)+int(b[i:i+2], 16)*u) for i in (0, 2, 4))


def appendage(a, w):
    base, tip = list(a['base']), list(a['tip'])
    dx, dy = base[0]-tip[0], base[1]-tip[1]
    length = (dx*dx+dy*dy)**.5 or 1
    k = w/260
    base = [tip[0]+dx/length*62*k, tip[1]+dy/length*62*k]
    return dict(name=a['name'], base=base, tip=tip, **EAR[a['name']])


def build(cid):
    c = CFG[cid]
    f, wm = c['f'], c['wm']
    folder = PROJ/'assets'/cid
    m = json.loads((folder/'rig.json').read_text(encoding='utf-8'))
    col = m['colors']
    fur = col['limb']
    colors = {'outline': col['outline'], 'skin': col['fur'], 'eye_white': '#fcfaf7', 'pupil': col['outline'], 'mouth_inside': '#7a2a1e',
              'tongue': '#e8707a', 'blush': col['blush'], 'nose': col['nose'], 'sleeve': fur, 'forearm': fur, 'cuff': fur, 'thigh': fur,
              'shin': fur, 'leg_shade': mix(fur, col['outline'], .3), 'neck': fur}
    # ---- torso
    t = m['torso']
    torso_upp = c['torso']*f*wm/t['size'][0]
    waist = [t['waist'][0], t['waist'][1]-10/torso_upp]
    tu = lambda p: [(p[0]-waist[0])*torso_upp, (p[1]-waist[1])*torso_upp]
    x0, y0, x1, y1 = t['body_bbox']
    top_y = (y0-waist[1])*torso_upp
    torso_h = (y1-y0)*torso_upp
    half_w = (x1-x0)/2*torso_upp
    shoulder = [c['sx']*(x1-x0)*torso_upp, top_y+c['sy']*torso_h]
    # the engine blends the sleeve into the torso colour found at the shoulder: when that is just the torso's own fur, use it for the limbs
    timg = np.array(Image.open(folder/t['file']).convert('RGBA'))
    cx_, cy_ = int(waist[0]+shoulder[0]/torso_upp), int(waist[1]+(shoulder[1]+4)/torso_upp)
    blk = timg[cy_-3:cy_+4, cx_-3:cx_+4].reshape(-1, 4)
    blk = blk[blk[:, 3] > 250][:, :3].astype(float)
    if len(blk):
        med = np.median(blk, axis=0)
        ref = np.array([int(fur[i:i+2], 16) for i in (1, 3, 5)], float)
        if np.abs(med-ref).sum() < 60:
            fur = '#%02x%02x%02x' % tuple(int(v) for v in med)
            colors.update({k: fur for k in ('sleeve', 'forearm', 'cuff', 'thigh', 'shin', 'neck')})
            colors['leg_shade'] = mix(fur, col['outline'], .3)
    neck = tu(t['neck'])
    # ---- heads
    heads = {}
    front_upp = c['skull']*f/(m['heads']['front']['skull_bbox'][2]-m['heads']['front']['skull_bbox'][0])
    line = m['outline_px']['head']*.70
    for name, src in list(m['heads'].items())+[('profile', m['head_profile'])]:
        if name == 'front':
            upp = front_upp
        elif name == '3q':
            upp = front_upp*m['head_scale_3q_over_front']
        else:
            upp = front_upp*m['head_scale_3q_over_front']*src['upp_over_3q']
        face = {'bbox': src['face_bbox'], 'line': line, 'pupil': src['pupil'], 'mouth': src['mouth'], 'nose': None}
        for k in ('eye_l', 'eye_r', 'brow_l', 'brow_r', 'blush_l', 'blush_r'):
            if k in src:
                face[k] = src[k]
        view = {'file': f'assets/{cid}/{src["file"]}', 'mask': f'assets/{cid}/{Path(src["file"]).stem}_face.png', 'size': src['size'],
                'upp': upp, 'pivot': list(src['neck']), 'top': src['skull_bbox'][1], 'face': face,
                'appendages': [appendage(a, src['size'][0]) for a in src.get('appendages', [])]}
        if name == 'profile':
            view['profile'] = True
        heads[name] = view
    # ---- profile torso
    tp = m['torso_profile']
    pupp = torso_upp*tp['upp_over_front']
    pwaist = [tp['waist'][0], tp['waist'][1]-10/pupp]
    ptop = None
    torso_profile = {'file': f'assets/{cid}/{tp["file"]}', 'upp': pupp, 'pivot': pwaist,
                     'shoulder': [(tp['shoulder'][0]-pwaist[0])*pupp, shoulder[1]],
                     'neck': [(tp['neck'][0]-pwaist[0])*pupp, (tp['neck'][1]-pwaist[1])*pupp+1]}
    if cid in ('papa_oso', 'mama_osa'):
        torso_profile['merge'] = False     # the clothing at the shoulder is not the arm's fur: no torso patch over the arm root
    # ---- hips
    hp = m['hips']
    hips_upp = c['hips']*f*wm/hp['size'][0]
    # ---- boot (bear paw foot): the ankle is the centre of the top opening
    bt = m['boots']['side']
    alpha = np.array(Image.open(folder/bt['file']))[..., 3] > 128
    rows = np.where(alpha.any(axis=1))[0]
    top, height = int(rows[0]), int(rows[-1]-rows[0])
    cols = np.where(alpha[top+round(height*.17)])[0]
    cx, rx = (cols[0]+cols[-1])/2, (cols[-1]-cols[0])/2
    ry = rx*.27
    line_px = m['outline_px']['parts']
    mouth = {'c': [float(cx), float(top+ry)], 'rx': float(rx-line_px*.8), 'ry': float(ry-line_px*.5)}
    bupp = c['foot']*f*wm/bt['size'][0]
    ankle_h = (bt['sole_y']-mouth['c'][1])*bupp
    xs = np.where(alpha.any(axis=0))[0]
    boots = {'side': {'file': f'assets/{cid}/{bt["file"]}', 'upp': bupp, 'pivot': [mouth['c'][0], bt['sole_y']-ankle_h/bupp],
                      'mouth': {'c': [mouth['c'][0], bt['sole_y']-ankle_h/bupp], 'rx': mouth['rx'], 'ry': mouth['ry']}}}
    foot = {'toe': round((xs[-1]-cx)*bupp*.85, 2), 'heel': round((cx-xs[0])*bupp*.8, 2), 'depth': 3.5}
    # ---- limbs
    arm_w = c['arm']*f*wm
    hip_height = (8+(44.0+38.0)*.985+9.0)*f
    reach = (hip_height-8*f-ankle_h)/.985
    thigh, shin = reach*44/82, reach*38/82
    leg_w = c['leg']*f*wm
    arm = {'upper': 45.0*f, 'fore': 41.0*f, 'w': [arm_w, arm_w*.96, arm_w*.86], 'smooth': .72,
           'bands': [{'from': 0, 'to': 1, 'color': fur}], 'cuff_extend': 0}
    leg = {'thigh': thigh, 'shin': shin, 'smooth': .3, 'w': [leg_w, leg_w*.92, min(leg_w*.84, 2*mouth['rx']*bupp*.96)],
           'bands': [{'from': 0, 'to': 1, 'color': fur}]}
    # ---- hands (paws): same on-screen size for every pose; backs match the palm's silhouette area
    hands = {}
    end_w = arm['w'][2]
    wh = np.mean([h['wrist_h'] for h in m['hands'].values()])
    hupp = 1.30*end_w/wh
    for pose, h in m['hands'].items():
        pa = (np.array(Image.open(folder/h['file']))[..., 3] > 128).sum()
        entry = {'file': f'assets/{cid}/{h["file"]}', 'upp': hupp, 'pivot': h['wrist'], 'dir': h['dir_deg']}
        b = m['handsb'][pose]
        ba = (np.array(Image.open(folder/b['file']))[..., 3] > 128).sum()
        entry['back'] = {'file': f'assets/{cid}/{b["file"]}', 'upp': round(hupp*float(np.sqrt(pa/ba)), 5), 'pivot': b['wrist'], 'dir': b['dir_deg']}
        if 'grip' in h:
            entry['grip'] = h['grip']
            entry['back']['grip'] = b['grip']
        hands[pose] = entry
    rig = {'name': c['name'], 'colors': colors, 'outline': m['outline_px']['parts']*torso_upp*.9,
           'hip_height': hip_height, 'hip_half': 20.0*f*wm, 'hip_joint_dy': 8.0*f, 'ankle_h': ankle_h, 'foot': foot,
           'arm': arm, 'leg': leg,
           'torso': {'file': f'assets/{cid}/{t["file"]}', 'upp': torso_upp, 'pivot': waist, 'shoulder': shoulder, 'neck': [0.0, neck[1]+1],
                     'profile': torso_profile},
           'hips': {'file': f'assets/{cid}/{hp["file"]}', 'upp': hips_upp, 'pivot': [hp['size'][0]/2, hp['size'][1]/2]},
           'hands': hands, 'boots': boots, 'head': heads, 'defaults': {'blush': c['blush_alpha']}}
    # fork and bib: registered when their art exists (props made by another agent)
    props = PROJ/'assets/props'
    meta = {'torso_h': torso_h, 'torso_upp': torso_upp, 'neck_px': t['neck'], 'waist_px': waist}
    fork = props/'tenedor/tenedor.png'
    if fork.exists():
        fw, fh = Image.open(fork).size
        # the handle's lower part sits in the fist; the fork is ~105 world units long (before f)
        rig['items'] = {'tenedor': {'file': 'assets/props/tenedor/tenedor.png', 'upp': 105.0*f/fh, 'pivot': [fw/2, fh*.80], 'dir': -90.0}}
    knife = props/'cuchillo/cuchillo.png'
    if knife.exists():      # companion of the fork: same length, gripped at the same height of the handle
        kw, kh = Image.open(knife).size
        rig.setdefault('items', {})['cuchillo'] = {'file': 'assets/props/cuchillo/cuchillo.png', 'upp': 105.0*f/kh,
                                                   'pivot': [kw/2, kh*.745], 'dir': -90.0}
    held = props/'babero/babero_mano.png'
    if held.exists():       # the bib before it is tied: gripped by its top edge, hanging down
        rig.setdefault('items', {})['babero_mano'] = {'file': 'assets/props/babero/babero_mano.png', 'upp': c['torso']*f*wm*.64/418.0,
                                                      'pivot': [211.0, 40.0], 'dir': -90.0}
    bib = {}
    bw = c['torso']*f*wm*.64                       # the bib is ~64% of the torso width
    for key, fn, pivot in (('front', 'babero_puesto.png', None), ('profile', 'babero_perfil.png', None)):
        fpath = props/'babero'/fn
        if not fpath.exists():
            continue
        im = Image.open(fpath)
        w, h = im.size
        upp_b = bw/418.0                            # same scale for every view (front bib = 418 px wide)
        if key == 'front':
            piv = [w/2, 40.0]
            at = [0.0, -2.0]
        else:
            piv = [w*.5, 40.0]
            at = [10.0*f*wm, -2.0]
        bib[key] = {'file': f'assets/props/babero/{fn}', 'upp': upp_b, 'pivot': piv, 'at': at}
    if bib:
        rig['wear'] = {'babero': bib}
    (PROJ/'characters').mkdir(exist_ok=True)
    (PROJ/'characters'/f'{cid}.json').write_text(json.dumps(rig, indent=1), encoding='utf-8')
    return rig, meta


if __name__ == '__main__':
    for cid in CFG:
        rig, meta = build(cid)
        head_h = rig['head']['front']['size'][1]*rig['head']['front']['upp']
        print(cid, 'hip', round(rig['hip_height'], 1), 'torso_h', round(meta['torso_h'], 1), 'head_h', round(head_h, 1),
              'total~', round(rig['hip_height']+meta['torso_h']-10*0+head_h*.85), 'ankle_h', round(rig['ankle_h'], 1), 'outline', round(rig['outline'], 2))
