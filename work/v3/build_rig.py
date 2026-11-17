"""Convert measured parts (assets/<cid>/rig.json) into engine puppet rigs (characters/<cid>.json).

Registration only: scales, pivots and colours come from measurements of the generated art.
"""
from pathlib import Path
import json
from PIL import Image, ImageOps

root = Path(__file__).resolve().parents[2]/'projects/taller-v3'
SKULL_W = 148.0      # world units at actor scale 1
TORSO_W, HIPS_W, BOOT_H = 96.0, 74.0, 36.0
ARM_W = 27.0
BACK3Q_V3 = True     # False = no three-quarter back art (backups: characters/<id>.preback.json); `turn` then tops out at 2
PROFILE_V3 = True    # False = no profile art (backups: characters/<id>.views1.json); the rig then only has front and 3/4 views
HANDS_V2 = True      # False = the original hand_*.png sprites (backups: characters/<id>.hands1.json)

STYLE = {
    'luma': {
        'shoulder': [22.0, -58.0],
        'arm_bands': lambda c: [{'from': 0, 'to': 1, 'color': c['sleeve']}],
        'cuff': lambda c: {'from': .84, 'to': .97, 'color': c['cuff']},
        'arm_highlight': None, 'leg_highlight': None,
        'appendages': {'ear_l': dict(freq=5.2, damp=.3, gain=.55, spread=.8), 'ear_r': dict(freq=5.6, damp=.3, gain=.55, spread=.8)},
    },
    'pip': {
        'shoulder': [27.0, -56.0],
        'arm_bands': lambda c: [{'from': 0, 'to': 1, 'color': c['sleeve']}],
        'cuff': lambda c: {'from': .80, 'to': .97, 'color': c['cuff']},
        'arm_highlight': lambda c: {'color': '#a9d9c4', 'w': 2.4, 'alpha': .9, 'from': .1, 'to': .42, 'offset': -.2},
        'leg_highlight': lambda c: {'color': '#a9d9c4', 'w': 2.4, 'alpha': .9, 'from': .12, 'to': .45, 'offset': -.2},
        'appendages': {'antenna': dict(freq=2.7, damp=.11, gain=1.7, spread=1.1, vertical=2.2)},
    },
}


def appendage(a, style, k):
    base, tip = list(a['base']), list(a['tip'])
    if a['name'].startswith('ear_'):
        # Ears are short cones: root the bend deeper in the hood so the whole ear follows.
        dx, dy = base[0]-tip[0], base[1]-tip[1]
        length = (dx*dx+dy*dy)**.5 or 1
        base = [tip[0]+dx/length*62*k, tip[1]+dy/length*62*k]
    return dict(name=a['name'], base=base, tip=tip, **style)


def mirror_view(view, folder, cid):
    """Flip a head view horizontally so every 3/4 head natively looks to screen-right."""
    width = view['size'][0]
    for key, suffix in (('file', ''), ('mask', '')):
        source = folder/Path(view[key]).name
        target = source.with_name(source.stem+'_flip.png')
        ImageOps.mirror(Image.open(source)).save(target)
        view[key] = f'assets/{cid}/{target.name}'

    def fx(point):
        return [width-point[0], point[1]]
    face = view['face']
    face['bbox'] = [width-face['bbox'][2], face['bbox'][1], width-face['bbox'][0], face['bbox'][3]]
    for a, b in (('eye_l', 'eye_r'), ('brow_l', 'brow_r'), ('blush_l', 'blush_r')):
        left, right = face[a], face[b]
        left['c'], right['c'] = fx(right['c']), fx(left['c'])
        for k in set(left) & set(right):
            if k != 'c':
                left[k], right[k] = right[k], left[k]
    face['mouth']['c'] = fx(face['mouth']['c'])
    if face.get('nose'):
        face['nose']['c'] = fx(face['nose']['c'])
    face['pupil']['highlight_offset'][0] *= -1
    view['pivot'] = fx(view['pivot'])
    for item in view['appendages']:
        item['base'], item['tip'] = fx(item['base']), fx(item['tip'])
        if item['name'].startswith('ear_'):
            item['name'] = 'ear_r' if item['name'] == 'ear_l' else 'ear_l'


def profile_view(m, cid, upp3q, style):
    """Head in profile facing right: a single visible eye/brow/blush (the `_r` entries), mouth at the front edge."""
    source = m['head_profile']
    pupil = dict(source['pupil'])
    return {
        'file': f"assets/{cid}/{source['file']}", 'mask': f"assets/{cid}/{Path(source['file']).stem}_face.png", 'profile': True,
        'size': source['size'], 'upp': upp3q*source['upp_over_3q'], 'pivot': list(source['neck']), 'top': source['skull_bbox'][1],
        'face': {
            'bbox': source['face_bbox'], 'line': m['outline_px']['head_3q']*.82*.5*(1+m['outline_px']['head']/m['outline_px']['head_3q']),
            'eye_r': source['eye_r'],
            'pupil': {'rx': pupil['rx']*1.16, 'ry': pupil['ry']*1.12, 'highlight_r': pupil['highlight_r']*1.7, 'highlight_offset': [pupil['highlight_offset'][0]*1.25, pupil['highlight_offset'][1]*1.25]},
            'brow_r': source['brow_r'], 'mouth': source['mouth'], 'nose': source.get('nose'), 'blush_r': source['blush_r'],
        },
        'appendages': [appendage(a, style['appendages'][a['name']], source['size'][0]/260)
                       for a in source.get('appendages', []) if a['name'] in style['appendages']],
    }


def back_view(m, cid, upp3q, style):
    """Head seen from behind at three-quarter: no face (`back`), only silhouette and the springy appendages."""
    source = m['head_back3q']
    return {
        'file': f"assets/{cid}/{source['file']}", 'back': True,
        'size': source['size'], 'upp': upp3q*source['upp_over_3q'], 'pivot': list(source['neck']), 'top': source['skull_bbox'][1],
        'face': {'bbox': source['face_bbox']},
        'appendages': [appendage(a, style['appendages'][a['name']], source['size'][0]/260)
                       for a in source.get('appendages', []) if a['name'] in style['appendages']],
    }


def profile_torso(m, cid, torso_upp, shoulder_y, key='torso_profile'):
    t = m[key]
    upp = torso_upp*t['upp_over_front']
    waist = [t['waist'][0], t['waist'][1]-10/upp]
    return {'file': f"assets/{cid}/{t['file']}", 'upp': upp, 'pivot': waist,
            'shoulder': [(t['shoulder'][0]-waist[0])*upp, shoulder_y],
            'neck': [(t['neck'][0]-waist[0])*upp, (t['neck'][1]-waist[1])*upp+1]}


def build(cid):
    folder = root/'assets'/cid
    m = json.loads((folder/'rig.json').read_text(encoding='utf-8'))
    colors, style = m['colors'], STYLE[cid]
    limbs = m['limbs']
    part_upp = ARM_W/limbs['upper_arm_w']
    heads = {}
    front_upp = SKULL_W/(m['heads']['front']['skull_bbox'][2]-m['heads']['front']['skull_bbox'][0])
    for name, source in m['heads'].items():
        upp = front_upp*(m.get('head_scale_3q_over_front', 1.0) if name == '3q' else 1.0)
        pupil = dict(source['pupil'])
        view = {
            'file': f"assets/{cid}/{source['file']}", 'mask': f"assets/{cid}/{Path(source['file']).stem}_face.png",
            'size': source['size'], 'upp': upp, 'pivot': list(source['neck']), 'top': source['skull_bbox'][1],
            'face': {
                'bbox': source['face_bbox'], 'line': m['outline_px']['head']*.82,
                'eye_l': source['eye_l'], 'eye_r': source['eye_r'],
                'pupil': {'rx': pupil['rx']*1.16, 'ry': pupil['ry']*1.12, 'highlight_r': pupil['highlight_r']*1.7, 'highlight_offset': [pupil['highlight_offset'][0]*1.25, pupil['highlight_offset'][1]*1.25]},
                'brow_l': source['brow_l'], 'brow_r': source['brow_r'], 'mouth': source['mouth'],
                'nose': source.get('nose'), 'blush_l': source['blush_l'], 'blush_r': source['blush_r'],
            },
            'appendages': [appendage(a, style['appendages'][a['name']], source['size'][0]/260)
                           for a in source.get('appendages', []) if a['name'] in style['appendages']],
        }
        if name == '3q' and source.get('looks') == 'left':
            mirror_view(view, folder, cid)
        heads[name] = view
    if PROFILE_V3 and BACK3Q_V3 and 'head_back3q' in m:
        heads['back3q'] = back_view(m, cid, front_upp*m.get('head_scale_3q_over_front', 1.0), style)
    if PROFILE_V3 and 'head_profile' in m:
        heads['profile'] = profile_view(m, cid, front_upp*m.get('head_scale_3q_over_front', 1.0), style)
    torso = m['torso']
    torso_upp = TORSO_W/torso['size'][0]
    waist = [torso['waist'][0], torso['waist'][1]-10/torso_upp]

    def torso_units(point):
        return [(point[0]-waist[0])*torso_upp, (point[1]-waist[1])*torso_upp]
    shoulder_l, shoulder_r = torso_units(torso['shoulder_l']), torso_units(torso['shoulder_r'])
    shoulder = STYLE[cid].get('shoulder') or [(abs(shoulder_l[0])+abs(shoulder_r[0]))/2-2, (shoulder_l[1]+shoulder_r[1])/2+3]
    neck = torso_units(torso['neck'])
    hips = m['hips']
    hips_upp = HIPS_W/hips['size'][0]
    # The ankle is the mouth of the boot: the leg ends there and enters the opening, the boot hangs below it.
    import numpy as np
    from PIL import Image
    boots, mouths = {}, {}
    upp = BOOT_H/m['boots']['side']['size'][1]
    for name, boot in m['boots'].items():
        alpha = np.array(Image.open(root/'assets'/cid/boot['file']))[..., 3] > 128
        rows = np.where(alpha.any(axis=1))[0]
        top, height = int(rows[0]), int(rows[-1]-rows[0])
        cols = np.where(alpha[top+round(height*.15)])[0]
        cx, rx = (cols[0]+cols[-1])/2, (cols[-1]-cols[0])/2
        ry = rx*.25
        line = m['outline_px']['parts']
        mouths[name] = {'c': [float(cx), float(top+ry)], 'rx': float(rx-line*.9), 'ry': float(ry-line*.6),
                        'x0': float(np.where(alpha.any(axis=0))[0][0]), 'x1': float(np.where(alpha.any(axis=0))[0][-1])}
    side = mouths['side']
    ankle_h = (m['boots']['side']['sole_y']-side['c'][1])*upp
    for name, boot in m['boots'].items():
        mouth = mouths[name]
        boots[name] = {'file': f"assets/{cid}/{boot['file']}", 'upp': upp, 'pivot': [mouth['c'][0], boot['sole_y']-ankle_h/upp],
                       'mouth': {'c': [mouth['c'][0], boot['sole_y']-ankle_h/upp], 'rx': mouth['rx'], 'ry': mouth['ry']}}
    foot = {'toe': round((side['x1']-side['c'][0])*upp*.85, 2), 'heel': round((side['c'][0]-side['x0'])*upp*.8, 2), 'depth': 3.5}
    if HANDS_V2 and 'hands2' in m:
        hands = {name: {'file': f"assets/{cid}/{hand['file']}", 'upp': hand['upp'], 'pivot': hand['wrist'], 'dir': hand['dir_deg']}
                 for name, hand in m['hands2'].items()}
        for name, hand in m.get('hands2b', {}).items():
            hands[name]['back'] = {'file': f"assets/{cid}/{hand['file']}", 'upp': hand['upp'], 'pivot': hand['wrist'], 'dir': hand['dir_deg']}
    else:
        hands = {name: {'file': f"assets/{cid}/{hand['file']}", 'upp': part_upp, 'pivot': hand['wrist'], 'dir': hand['dir_deg']}
                 for name, hand in m['hands'].items()}
    leg_scale = 30.0/limbs['thigh_w_top']
    hip_height = 8+(44.0+38.0)*.985+9.0             # the body keeps its height; the legs end at the boot mouth
    reach = (hip_height-8-ankle_h)/.985
    thigh, shin = reach*44/82, reach*38/82
    arm = {'upper': 45.0, 'fore': 41.0, 'w': [ARM_W, ARM_W*.95, limbs['forearm_w']*part_upp*.98], 'smooth': .72,
           'bands': style['arm_bands'](colors), 'cuff': style['cuff'](colors)}
    if style['arm_highlight']:
        arm['highlight'] = style['arm_highlight'](colors)
    leg = {'thigh': thigh, 'shin': shin, 'smooth': .3,
           'w': [limbs['thigh_w_top']*leg_scale, limbs['thigh_w_bottom']*leg_scale*1.04, min(limbs['shin_w']*leg_scale*1.02, 2*side['rx']*upp*.96)],
           'bands': [{'from': 0, 'to': 1, 'color': colors['thigh']}]}
    if style['leg_highlight']:
        leg['highlight'] = style['leg_highlight'](colors)
    rig = {
        'name': cid.capitalize(), 'colors': colors,
        'outline': m['outline_px']['parts']*part_upp,
        'hip_height': hip_height, 'hip_half': 20.0, 'hip_joint_dy': 8.0, 'ankle_h': ankle_h, 'foot': foot,
        'arm': arm, 'leg': leg,
        'torso': {'file': f"assets/{cid}/{torso['file']}", 'upp': torso_upp, 'pivot': waist, 'shoulder': shoulder, 'neck': [0.0, neck[1]+1]},
        'hips': {'file': f"assets/{cid}/{hips['file']}", 'upp': hips_upp, 'pivot': [hips['size'][0]/2, hips['size'][1]/2]},
        'hands': hands, 'boots': boots, 'head': heads,
    }
    if PROFILE_V3 and 'torso_profile' in m:
        rig['torso']['profile'] = profile_torso(m, cid, torso_upp, shoulder[1])
        if BACK3Q_V3 and 'torso_back3q' in m:
            rig['torso']['back3q'] = profile_torso(m, cid, torso_upp, shoulder[1], 'torso_back3q')
    target = root/'characters'/f'{cid}.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(rig, indent=1), encoding='utf-8')
    return rig


if __name__ == '__main__':
    for cid in ('luma', 'pip'):
        rig = build(cid)
        print(cid, 'outline', round(rig['outline'], 2), 'hip', round(rig['hip_height'], 1), 'shoulder', [round(v, 1) for v in rig['torso']['shoulder']],
              'neck', [round(v, 1) for v in rig['torso']['neck']], 'head upp', {k: round(v['upp'], 3) for k, v in rig['head'].items()})
