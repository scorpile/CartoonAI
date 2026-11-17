"""Visual checks for the deformable puppet: joints, torso bend/yaw/hem, head turn.
Usage: python work/v3/deform_test.py [joints|bend|head|time ...]   (outputs work/v3/review/deform-*.jpg)
"""
import sys, json, time
sys.path.insert(0, '.')
import skia
from pathlib import Path
from celstudio.v2.puppet import Rig
from celstudio.v2.direct import EXPRESSIONS

root = Path('projects/taller-v3')
RIGS = {c: Rig(json.loads((root/f'characters/{c}.json').read_text(encoding='utf-8')), root) for c in ('luma', 'pip')}
BG = skia.Color(233, 196, 143)
OUT = Path('work/v3/review')


def values(rig, **over):
    v = dict(rig.defaults)
    v.update(over)
    return v


def render(cid, w, h, ox, oy, scale, wobble=None, facing=1, **over):
    rig = RIGS[cid]
    v = values(rig, **over)
    surface = skia.Surface(w, h)
    c = surface.getCanvas()
    c.clear(BG)
    c.save()
    c.translate(ox, oy)
    c.scale(scale*facing, scale)
    wob = wobble or {}
    p = rig.pose(v, wob)
    rig.draw(c, p, v, wob)
    c.restore()
    return surface.makeImageSnapshot()


def sheet(rows, cw, ch, path, labels=None):
    surface = skia.Surface(cw*max(len(r) for r in rows), ch*len(rows))
    c = surface.getCanvas()
    c.clear(BG)
    for j, row in enumerate(rows):
        for i, img in enumerate(row):
            c.drawImage(img, i*cw, j*ch)
    surface.makeImageSnapshot().save(str(path), skia.kJPEG, 92)


def full(cid, **kw):
    return render(cid, 420, 660, 210, 625, 2.1, **kw)


def head(cid, **kw):
    return render(cid, 300, 300, 150, 150+232*1.9, 1.9, **kw)


def joints():
    poses = [
        dict(),
        dict(arm_l_x=-18, arm_l_y=24, arm_l_bend=.9, arm_r_x=18, arm_r_y=24, arm_r_bend=-.9, hand_l='open', hand_r='open'),
        dict(arm_l_x=-36, arm_l_y=-62, arm_l_bend=.9, hand_l='open', hand_l_rot=-20),
        dict(arm_l_x=-30, arm_l_y=40, arm_r_x=34, arm_r_y=30),
        dict(arm_l_x=60, arm_l_y=-10, arm_l_bend=-.6, hand_l='point'),
        dict(arm_l_x=30, arm_l_y=25, arm_l_bend=-.9, arm_l_z=2),
    ]
    rows = []
    for cid in ('luma', 'pip'):
        for turn in (0, 1):
            rows.append([full(cid, turn=turn, **pz) for pz in poses])
    sheet(rows, 420, 660, OUT/'deform-joints.jpg')


def bend():
    rows = []
    for cid in ('luma', 'pip'):
        rows.append([full(cid, bend=b, lean=-b*.4) for b in (-20, -10, 0, 10, 20)])
        rows.append([full(cid, wobble={'hem': h}, ) for h in (-9, -4.5, 0, 4.5, 9)])
        rows.append([full(cid, body_yaw=y, turn=0) for y in (-1, -.5, 0, .5, 1)])
    sheet(rows, 420, 660, OUT/'deform-bend.jpg')


def heads():
    sweeps = [('x', [-1, -.67, -.33, 0, .33, .67, 1]), ('y', [-1, -.5, 0, .5, 1])]
    combos = [dict(face_x=.7, face_y=-.4, **EXPRESSIONS['happy'], look_x=.5), dict(face_x=-.8, face_y=.5, **EXPRESSIONS['surprise'], look_x=-.4)]
    for cid in ('luma', 'pip'):
        rows = []
        for turn in (0, 1):
            rows.append([head(cid, turn=turn, face_x=x) for x in sweeps[0][1]])
            rows.append([head(cid, turn=turn, face_y=y) for y in sweeps[1][1]])
        rows.append([head(cid, turn=t, **cb) for t in (0, 1) for cb in combos])
        sheet(rows, 300, 300, OUT/f'deform-head-{cid}.jpg')


def timing():
    import numpy as np
    for cid in ('luma', 'pip'):
        rig = RIGS[cid]
        for name, over, wob in (('default', {}, {}), ('all', dict(face_x=.6, face_y=.3, bend=12, body_yaw=.6, arm_l_x=-30, arm_l_y=-60), {'hem': 5, 'ear_l': .2, 'ear_r': -.1, 'antenna': .2})):
            v = values(rig, **over)
            surface = skia.Surface(900, 1000)
            c = surface.getCanvas()
            ts = []
            for k in range(12):
                c.clear(BG)
                c.save()
                c.translate(450, 950)
                c.scale(3.2, 3.2)
                t = time.perf_counter()
                p = rig.pose(v, wob)
                rig.draw(c, p, v, wob)
                ts.append((time.perf_counter()-t)*1000)
                c.restore()
            print(cid, name, 'ms median', round(float(np.median(ts[2:])), 1))


def wrist():
    rows = []
    for cid in ('luma', 'pip'):
        for hand in ('closed', 'open', 'point'):
            row = []
            for rot_ in (-60, -30, 0, 30, 60):
                rig = RIGS[cid]
                v = values(rig, turn=0, hand_l=hand, hand_l_rot=rot_, arm_l_x=-22, arm_l_y=70)
                p = rig.pose(v)
                hx, hy = p['hand_l']
                row.append(render(cid, 240, 240, 120-hx*5, 120-hy*5, 5.0, turn=0, hand_l=hand, hand_l_rot=rot_, arm_l_x=-22, arm_l_y=70))
            rows.append(row)
    sheet(rows, 240, 240, OUT/'deform-wrist.jpg')


if __name__ == '__main__':
    OUT.mkdir(exist_ok=True)
    for name in (sys.argv[1:] or ['joints', 'bend', 'head']):
        {'joints': joints, 'bend': bend, 'head': heads, 'time': timing, 'wrist': wrist}[name]()

