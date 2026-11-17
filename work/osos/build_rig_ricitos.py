"""Convert the measured parts of Ricitos (assets/ricitos/rig.json) into projects/tres-osos/characters/ricitos.json.

Registration only: scales, pivots and colours come from measurements of the generated art. Ricitos is only ever seen from the
waist up, so hips and boots are fully transparent 4x4 placeholders (not art) and the legs shrink to a dot under the waist.
Also writes characters/ricitos_guino.json: same art, but the far eye is a flat lens (the engine has one `lid` for both eyes).
Run: python work/osos/build_rig_ricitos.py
"""
import json
import copy
from pathlib import Path
from PIL import Image

root = Path(__file__).resolve().parents[2]/'projects/tres-osos'
folder = root/'assets/ricitos'
TORSO_W = 80.0          # world units (actor scale 1) at the waist
HEAD_UPP = .155         # units per px of the (reduced) front head sprite
WRIST = 14.0            # units: height of the wrist cut of the hand art
FREQ = {'curl_l': 2.6, 'curl_l2': 3.3, 'curl_r2': 3.0, 'curl_r': 3.7}
ARM = {'upper': 30.0, 'fore': 28.0, 'w': [20.0, 19.0, 16.0]}


def blank(name):
    Image.new('RGBA', (4, 4), (0, 0, 0, 0)).save(folder/name)


def head_view(h, upp, line):
    face = h['face']
    eye = face['eye_l']
    pupil = {'rx': eye['rx']*.52, 'ry': eye['ry']*.62, 'highlight_r': eye['ry']*.07, 'highlight_offset': [eye['rx']*.1, -eye['ry']*.18]}
    stem = Path(h['file']).stem
    apps = []
    for a in h['appendages']:
        spec = dict(freq=FREQ.get(a['name'], 3.0), damp=.2, gain=1.9, spread=.45, vertical=1.6) if a['name'].startswith('curl') else \
            dict(freq=3.6, damp=.22, gain=.9, spread=.8, vertical=1.2)
        apps.append(dict(a, **spec))
    return {'file': f"assets/ricitos/{h['file']}", 'mask': f'assets/ricitos/{stem}_face.png', 'size': h['size'], 'upp': upp,
            'pivot': h['neck'], 'top': h['top'],
            'face': dict(face, line=line, pupil=pupil), 'appendages': apps}


def build():
    m = json.loads((folder/'rig.json').read_text(encoding='utf-8'))
    front, tq = m['heads']['front'], m['heads']['3q']
    c = {'outline': '#371400', 'skin': front['skin'], 'eye_white': '#fcfaf7', 'pupil': '#3a1a08', 'mouth_inside': '#953522',
         'tongue': '#f37b5e', 'blush': '#f59a8a', 'nose': '#c9815a', 'sleeve': m['torso']['gown'], 'sleeve_shade': '#7fb2d8',
         'forearm': front['skin'], 'cuff': '#fffdf8', 'thigh': m['torso']['gown'], 'shin': m['torso']['gown'], 'leg_shade': '#7fb2d8',
         'neck': front['skin'], 'hair': front['gold']}
    upp3 = HEAD_UPP*front['plate_h']/tq['plate_h']
    line = 9.0
    heads = {'front': head_view(front, HEAD_UPP, line), '3q': head_view(tq, upp3, line)}
    t = m['torso']
    tu = TORSO_W/t['width']
    waist = [t['waist'][0], t['waist'][1]-10/tu]
    neck = [(t['neck'][0]-waist[0])*tu, (t['neck'][1]-waist[1])*tu]
    sh_y = (t['shoulder_row']+34-waist[1])*tu
    shoulder = [(t['shoulder_span'][1]-t['shoulder_span'][0])/2*tu*.62, sh_y]
    blank('hips.png')
    blank('boot.png')
    hands, hand_back = {}, {}
    for name, h in m['hands'].items():
        upp = WRIST/h['wrist_h']
        hands[name] = {'file': f"assets/ricitos/{h['file']}", 'upp': upp, 'pivot': h['wrist'], 'dir': h['dir_deg']}
        b = m['hands_back'][name]
        hands[name]['back'] = {'file': f"assets/ricitos/{b['file']}", 'upp': WRIST/b['wrist_h'], 'pivot': b['wrist'], 'dir': b['dir_deg']}
    rig = {
        'name': 'Ricitos', 'colors': c, 'outline': 1.9, 'anatomy': True,
        'hip_height': 12.0, 'hip_half': 5.0, 'hip_joint_dy': 0.0, 'ankle_h': 2.0, 'foot': {'toe': 2.0, 'heel': 2.0, 'depth': 0.0},
        'arm': {**ARM, 'smooth': .72, 'bands': [{'from': 0, 'to': 1, 'color': c['sleeve']}], 'cuff': {'from': .80, 'to': .97, 'color': c['cuff']}},
        'leg': {'thigh': 5.0, 'shin': 5.0, 'smooth': .3, 'w': [1.0, 1.0, 1.0], 'bands': [{'from': 0, 'to': 1, 'color': c['sleeve']}]},
        'neck': {'color': c['skin'], 'w': 26.0},
        'torso': {'file': 'assets/ricitos/torso.png', 'upp': tu, 'pivot': waist, 'shoulder': shoulder, 'neck': [0.0, neck[1]+1]},
        'hips': {'file': 'assets/ricitos/hips.png', 'upp': 10.0, 'pivot': [2, 2]},
        'hands': hands,
        'boots': {'side': {'file': 'assets/ricitos/boot.png', 'upp': 10.0, 'pivot': [2, 2]}},
        'head': heads,
        # Lying-in-bed default: the whole figure leans on the pillow, the head is brought back to nearly upright, asleep.
        'defaults': {'rot': -82.0, 'head_rot': 62.0, 'lid': 1.0, 'shadow': 0.0, 'smile': .45, 'life': .7},
    }
    (root/'characters').mkdir(exist_ok=True)
    (root/'characters/ricitos.json').write_text(json.dumps(rig, indent=1), encoding='utf-8')
    # Wink variant: far eye drawn as a flat lens, so lid=1 on the open eye reads as one eye closed + one eye closing/opening.
    wink = copy.deepcopy(rig)
    for key in ('front', '3q'):
        eye = wink['head'][key]['face']['eye_r']
        eye['ry'] = max(3.0, eye['ry']*.05)
    (root/'characters/ricitos_guino.json').write_text(json.dumps(wink, indent=1), encoding='utf-8')
    return rig


if __name__ == '__main__':
    rig = build()
    print('shoulder', [round(v, 1) for v in rig['torso']['shoulder']], 'neck', round(rig['torso']['neck'][1], 1),
          'head upp', {k: round(v['upp'], 3) for k, v in rig['head'].items()})
