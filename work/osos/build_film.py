"""'Los tres osos' (comedia negra suave, sin dialogo). Direction script: records projects/tres-osos/episodes/ep01/script.json (series library) and compiles its film.json.

Scenes: `llegada` (bosque: s01-s02) and `dormitorio` (s03-s08). 8 shots, ~45 s, 1920x1080, 24 fps.
Usage: python work/osos/build_film.py
"""
import json
import math
import sys
from pathlib import Path

base = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(base))
from celstudio.v2.direct import Film, EXPRESSIONS  # noqa: E402
from celstudio.v2.project import group_scene, save  # noqa: E402

root = base/'projects/tres-osos'
CH = ('papa_oso', 'mama_osa', 'osito', 'ricitos')
F = {'papa_oso': 1.15, 'mama_osa': 1.055, 'osito': .85}          # body size factors of the rigs (stride, lift)
rigs = {cid: json.loads((root/f'characters/{cid}.json').read_text(encoding='utf-8')) for cid in CH}
CURL = dict(json.loads((root/'assets/props/curl/spec.json').read_text(encoding='utf-8')), id='curl')
film = Film('tres-osos', 'Los tres osos', rigs, props={'curl': CURL})
STORY = ('Tres osos vuelven a su cabana, huelen algo raro, entran y encuentran a una nina de rizos dorados dormida en la cama '
         'pequena. Se miran, sonrien despacio, se atan los baberos y levantan tenedor y cuchillo. Ella abre un ojo.')

# ------------------------------------------------------------------ geometry
GY, SC = 640.0, .62              # bosque: ground line and actor scale on the path
DOOR_X, DOOR_Y, DOOR_SC = 985.0, 572.0, .52
DY, SD = 655.0, .70              # dormitorio
RX, RY, RS = 1012.0, 478.0, .70  # Ricitos: waist (root), scale. Head sits ~126 units to the left on the pillow.
RC_POSE = dict(arm_l_x=-26, arm_l_y=-36, arm_l_bend=.9, hand_l='open', arm_r_x=-3, arm_r_y=16, hand_r='curled')   # hand under the cheek, other near the chest
S01, S02 = 5.5, 7.4              # durations used to keep the march continuous across the cut


# ------------------------------------------------------------------ helpers
def march(t, shot_off, x0, T0, x1, T1, f, view='profile', step=78, lift=15, swing=17, bob=2.6, phase=0.0):
    """One continuous walk expressed in global time, so that it is the same walk in every shot it crosses."""
    return t.walk(T0-shot_off, T1-shot_off, x0, x1, scale=SC, step=step*f, lift=lift*f, swing=swing, bob=bob, phase=phase, view=view)


def skip(t, at, h=13):
    """Osito's little hop-skip to catch up: lift arc + squash on landing (does not touch the feet channels)."""
    t.key(at, 'lift', 0, 'linear')
    t.key(at+.15, 'lift', h, 'out')
    t.key(at+.3, 'lift', 0, 'in')
    t.to(at, .1, 'out', overlap=0, sy=.95, sx=1.04)
    t.to(at+.1, .14, 'out', overlap=0, sy=1.05, sx=.96)
    t.to(at+.28, .08, 'out', overlap=0, sy=.93, sx=1.06)
    t.to(at+.36, .2, 'back', overlap=0, sy=1.0, sx=1.0)


def diagonal(t, ta, tb, y0, y1, s0, s1, x_end=None):
    """While x advances from its value at ta to x_end (default: its value at tb), y and scale follow it linearly
    (walking towards the door); beyond x_end they hold."""
    x0, x1 = t.value('x', ta), (x_end if x_end is not None else t.value('x', tb))
    n = max(2, round((tb-ta)*24))
    for i in range(n+1):
        tt = ta+(tb-ta)*i/n
        u = min(1.0, max(0.0, (t.value('x', tt)-x0)/((x1-x0) or 1)))
        t.key(tt, 'y', y0+(y1-y0)*u, 'linear')
        t.key(tt, 'scale', s0+(s1-s0)*u, 'linear')


def sniff(t, at, n=3, up=1.0):
    """Head up, eyes half shut, chest rises on the breath in and settles with the exhale; n sniffs."""
    t.to(at, .22, 'out', head_rot=-9*up, face_y=-.5*up, head_dy=-3, lean=-5*up, torso_sy=1.03, lid=.55, squint=.25, mouth_w=.45, smile=.1, brow_y=.5)
    for i in range(n):
        a = at+.3+i*.34
        t.to(a, .12, 'out', overlap=.2, torso_sy=1.07, head_dy=-5, head_rot=-12*up, shoulder_l_dy=-4, shoulder_r_dy=-4, mouth_round=.5)
        t.to(a+.12, .2, 'inout', overlap=.2, torso_sy=1.03, head_dy=-3, head_rot=-8*up, shoulder_l_dy=0, shoulder_r_dy=0, mouth_round=.1)
    end = at+.3+n*.34
    return end


BASE = dict(wear='', item_l='', item_r='', hand_l='closed', hand_r='closed')


def actor_order(shot, take, order):
    take.spec['order'] = order
    for a in shot.script['actors']:
        if a['id'] == take.ref:
            a['order'] = order


def layer_order(shot, **orders):
    shot.spec['layer_order'] = dict(orders)
    shot.script['layer_order'] = dict(orders)


# ================================================================== LLEGADA (bosque)
CAM_Y = 372
# ---- s01 general: the family marches along the path, osito skipping to keep up
s = film.shot('s01', S01, 'bosque', 'General. Papa, mama y osito caminan en fila hacia la cabana; osito da saltitos para seguir el paso.')
s.dof(1.2)
s.cam(0, 520, CAM_Y, 1.0).cam(S01, 690, CAM_Y, 1.05, 'inout')
s.fade_in(.8)
PX = dict(papa_oso=(80., 880.), mama_osa=(-20., 800.), osito=(-125., 725.))     # start x, x at the end of the global march
GOAL = dict(papa_oso=795., mama_osa=712., osito=635.)                             # sniff spot in front of the door
T_STOP = dict(papa_oso=7.45, mama_osa=7.9, osito=8.15)                              # global time of arrival
papa = s.actor('papa_oso', x=80, y=GY, scale=SC, facing=1, turn=2, smile=.4, look_x=.7, look_y=-.1, **BASE)
mama = s.actor('mama_osa', x=-20, y=GY, scale=SC, facing=1, turn=2, smile=.5, look_x=.7, **BASE)
osito = s.actor('osito', x=-125, y=GY, scale=SC, facing=1, turn=2, smile=.85, look_x=.6, look_y=-.1, eye_open=1.1, **BASE)
for who, cid, off in ((papa, 'papa_oso', 0), (mama, 'mama_osa', 0), (osito, 'osito', 0)):
    pass
march(papa, 0, 80, 0.0, GOAL['papa_oso'], T_STOP['papa_oso'], F['papa_oso'], phase=0.0)
march(mama, 0, -20, 0.0, GOAL['mama_osa'], T_STOP['mama_osa'], F['mama_osa'], phase=.3)
march(osito, 0, -125, 0.0, GOAL['osito'], T_STOP['osito'], F['osito'], step=70, lift=17, swing=22, phase=.1)
for at in (1.0, 2.3, 3.6, 4.7):
    skip(osito, at)
# life in the faces: papa surveys, mama glances at osito, osito watches the others
papa.look(1.4, .85, -.15, .1, head=.2); papa.blink(1.9, 4.3)
mama.look(2.6, .45, .1, .1, head=.2); mama.blink(2.2, 4.8)
mama.look(3.2, .85, 0, .1, head=.2)
osito.look(2.0, .9, .3, .1, head=.3); osito.blink(3.1)
osito.look(3.9, .5, 0, .1, head=.2)
papa.face(4.6, 'curious', dur=.4)                               # something in the air
papa.look(4.8, .95, -.4, .1, head=.35)

# ---- s02 medio en la puerta: sniff, nudge, they sneak in one by one
s = film.shot('s02', S02, 'bosque', 'Medio en la puerta. Papa olfatea el aire, mama le da un codazo, entran uno a uno y desaparecen tras el marco.')
s.dof(2.5)
s.cam(0, 840, 432, 1.5).cam(3.0, 870, 428, 1.56, "inout").cam(S02, 900, 424, 1.6, "inout")
papa = s.actor('papa_oso', x=GOAL['papa_oso'], y=GY, scale=SC, facing=1, turn=2, smile=.4, look_x=.95, look_y=-.4, brow_y=.6, **BASE)
mama = s.actor('mama_osa', x=GOAL['mama_osa'], y=GY, scale=SC, facing=1, turn=2, smile=.5, look_x=.85, **BASE)
osito = s.actor('osito', x=GOAL['osito'], y=GY, scale=SC, facing=1, turn=2, smile=.85, look_x=.6, **BASE)
for t_, k_ in ((papa, 'papa_oso'), (mama, 'mama_osa'), (osito, 'osito')):
    t_.key(0, 'x', PX[k_][0]+0, 'step') if False else None
march(papa, S01, 80, 0.0, GOAL['papa_oso'], T_STOP['papa_oso'], F['papa_oso'], phase=0.0)
march(mama, S01, -20, 0.0, GOAL['mama_osa'], T_STOP['mama_osa'], F['mama_osa'], phase=.3)
march(osito, S01, -125, 0.0, GOAL['osito'], T_STOP['osito'], F['osito'], step=70, lift=17, swing=22, phase=.1)
# the walks above end in a three-quarter view; everybody is held in profile while they wait
for who, cid in ((papa, 'papa_oso'), (mama, 'mama_osa'), (osito, 'osito')):
    who.key(T_STOP[cid]-S01, 'turn', 2.0, 'step')
skip(osito, .15)
papa.face(.0, 'curious', dur=.01)
# papa sniffs (profile, nose up) ~1.5 .. 3.1
e = sniff(papa, 1.55, n=3)
papa.blink(e+.1)
papa.to(e+.1, .3, 'inout', head_rot=-3, face_y=-.1, lean=-1, lid=0, squint=0, mouth_round=0, torso_sy=1, brow_y=.9, brow_rot=8, mouth_w=.6, smile=-.1)
papa.look(e+.15, .6, 0, .1, head=.3)
# mama and osito arrive and wait; osito pants
mama.face(2.0, 'curious', dur=.3)
mama.look(2.1, .95, -.2, .1, head=.4)
osito.look(2.35, .9, -.5, .1, head=.3)
osito.to(2.4, .3, 'inout', head_rot=-4, lean=-2)
osito.pulse(2.7, .15, .1, .25, hip_dy=2.5, head_dy=2)             # catching breath
# mama steps up and elbows papa; papa is jolted forward, 'oops' (he has been caught sniffing)
T = 3.0
mama.to(T-.4, .3, 'inout', overlap=.3, lean=-3, head_rot=-3)       # wind-up
mama.set(T-.35, hand_l='open')
mama.to(T-.35, .35, 'inout', overlap=0, arm_l_x=-12, arm_l_y=60, arm_l_bend=1.0, lean=-4)
mama.to(T, .1, 'out', overlap=0, arm_l_x=62, arm_l_y=2, arm_l_bend=.4, lean=6, hip_dy=2, head_rot=3)
mama.face(T, 'smug', dur=.15)
mama.to(T+.35, .35, 'back', overlap=0, arm_l_x=38, arm_l_y=22, lean=2)
mama.to(T+.9, .4, 'inout', overlap=0, arm_l_x=mama.defaults['arm_l_x'], arm_l_y=mama.defaults['arm_l_y'], arm_l_bend=1.0, lean=0, head_rot=0)
mama.set(T+1.2, hand_l='closed')
papa.to(T+.08, .1, 'out', overlap=.2, lean=10, hip_dx=6, head_rot=7, torso_sy=.97, hip_dy=3)   # the jolt
papa.face(T+.1, 'oops', dur=.1)
papa.look(T+.1, -.9, 0, .06, head=.5)                          # looks back at mama
papa.to(T+.35, .35, 'back', lean=0, hip_dx=0, head_rot=-2, torso_sy=1, hip_dy=0)
papa.blink(T+.55)
papa.face(T+.9, 'soft', dur=.3)                                 # sheepish, then business
papa.look(T+1.1, .9, 0, .1, head=.3)
osito.react(T+.1, -.8, .3, head=.4)                              # osito watches the elbow
osito.face(T+.25, 'happy', dur=.2)
osito.pulse(T+.7, .12, .05, .25, hip_dy=3, head_dy=2)             # suppressed giggle
# entering, one by one: they sneak (small steps, lifted knees), rising on the path towards the doorway
# On the path they are in front of the cabin (order above the door frame); when the feet cross the threshold the
# order drops below the frame, so the jamb covers them, and they fade into the dark interior (door_dark is behind
# everyone). x_in: the last stretch is the step into the doorway.
X_IN, Y_SILL, Y_IN = DOOR_X+22, 604.0, 548.0
for who, cid, ts, dur in ((papa, 'papa_oso', 3.45, 2.75), (mama, 'mama_osa', 3.85, 2.85), (osito, 'osito', 4.2, 3.0)):
    x_here = GOAL[cid]
    who.set(ts, hand_l='closed')
    march(who, 0.0, x_here, ts, X_IN, ts+dur, F[cid], view='3q', step=50 if cid != 'osito' else 42, lift=18, swing=9, bob=2.0,
          phase=0.0)
    n = max(2, round(dur*24))
    t_cross = None
    for i in range(n+1):
        tt = ts+dur*i/n
        x = who.value('x', tt)
        if x <= DOOR_X:
            u = min(1.0, max(0.0, (x-x_here)/(DOOR_X-x_here)))
            y, sc = GY+(Y_SILL-GY)*u, SC+(SC*.94-SC)*u
        else:
            u = min(1.0, (x-DOOR_X)/(X_IN-DOOR_X))
            y, sc = Y_SILL+(Y_IN-Y_SILL)*u, SC*.94+(SC*.80-SC*.94)*u
            if t_cross is None and y < 590:
                t_cross = tt
        who.key(tt, 'y', y, 'linear')
        who.key(tt, 'scale', sc, 'linear')
    t_cross = t_cross or ts+dur-.5
    who.key(0, 'order', {'papa_oso': 5, 'mama_osa': 4, 'osito': 3}[cid], 'step')
    who.key(t_cross, 'order', 1, 'step')
    who.key(t_cross, 'opacity', 1.0, 'linear')
    who.key(ts+dur, 'opacity', 0.0, 'in')
    who.to(ts-.1, .15, 'out', overlap=0, lean=-2)
    who.look(ts-.1, .95, .0, .1, head=.3)
    who.face(ts, 'curious', dur=.3)
papa.to(3.0+.35, .3, 'inout', overlap=0, head_rot=0)
osito.face(4.2, 'happy', dur=.2)
layer_order(s, door_dark=-1, door_frame=2)

# ================================================================== DORMITORIO
# ---- s03 general: they come in from the left; osito trots to the small bed and points
s = film.shot('s03', 6.5, 'dormitorio', 'General. Entran por la izquierda y ven las camas; osito se adelanta, se detiene y senala la cama pequena.')
s.dof(1.0)
s.cam(0, 560, 372, 1.0).cam(6.5, 660, 380, 1.1, 'inout')
STOP = dict(papa_oso=470., mama_osa=360., osito=585.)
papa = s.actor('papa_oso', x=140, y=DY, scale=SD, facing=1, turn=2, smile=.35, look_x=.8, look_y=-.1, brow_y=.3, **BASE)
mama = s.actor('mama_osa', x=50, y=DY, scale=SD, facing=1, turn=2, smile=.35, look_x=.8, brow_y=.3, **BASE)
osito = s.actor('osito', x=-55, y=DY+26, scale=SD+.04, facing=1, turn=2, smile=.5, look_x=.8, brow_y=.3, **BASE)


def dwalk(t, x0, t0, x1, t1, f, **kw):
    kw = dict(dict(step=60*f, lift=14*f, swing=14, bob=2.2), **kw)
    return t.walk(t0, t1, x0, x1, scale=SD, view='profile', **kw)


dwalk(papa, 140, -.1, STOP['papa_oso'], 2.6, F['papa_oso'], phase=.35)
dwalk(mama, 50, -.1, STOP['mama_osa'], 2.8, F['mama_osa'], phase=.8)
dwalk(osito, -55, 0.0, STOP['osito'], 4.3, F['osito'], step=70, lift=17, swing=20, phase=.2)
for who, cid in ((papa, 'papa_oso'), (mama, 'mama_osa'), (osito, 'osito')):
    pass
skip(osito, 2.0, 12); skip(osito, 3.2, 12)
actor_order(s, papa, 1); actor_order(s, mama, 1); actor_order(s, osito, 2)
layer_order(s, blanket_small=.5)
rc = s.actor('ricitos', x=RX, y=RY, scale=RS, turn=1, **RC_POSE)
rc.auto_blink(False)
# papa looks over the beds (left to right), slow nod; mama checks the big bed
papa.look(.9, -.2, .1, .1, head=.5); papa.look(1.8, .5, -.1, .1, head=.4)
mama.look(1.0, .9, -.3, .1, head=.4); mama.look(2.1, -.1, .1, .1, head=.4); mama.look(2.9, .9, 0, .1, head=.3)
papa.face(1.2, 'curious', dur=.4)
mama.face(1.4, 'curious', dur=.4)
for who, cid in ((papa, 'papa_oso'), (mama, 'mama_osa')):
    who.key(2.6 if cid == 'papa_oso' else 2.8, 'turn', 1.0, 'smooth')
# osito arrives, stops (weight forward), looks at the small bed and freezes, then points
osito.to(4.25, .12, 'out', overlap=0, lean=9, hip_dy=5)
osito.to(4.37, .25, 'back', overlap=0, lean=0, hip_dy=0)
osito.look(4.3, 1, -.2, .08, head=.6)
osito.face(4.35, 'awe', dur=.12)
osito.gasp(4.4, .8)
osito.to(4.8, .16, 'out', overlap=0, arm_l_x=18, arm_l_y=70, lean=-3)                                 # anticipation: arm pulls back
osito.set(4.9, hand_l='point')
osito.to(4.95, .22, 'out', overlap=0, arm_l_x=84, arm_l_y=-26, arm_l_bend=.45, lean=5, head_dy=-2)       # shoots past
osito.to(5.17, .3, 'soft', overlap=0, arm_l_x=74, arm_l_y=-18, arm_l_bend=.6, lean=3, head_dy=0)
osito.drift(5.45, 6.5, 1.2, arm_l_x=2.4, arm_l_y=2.2, hand_l_rot=4, lean=.9)
# parents turn to the small bed after him: eyes, head, body
papa.react(5.0, .95, -.1, head=.5, lean=2); papa.face(5.05, 'awe', dur=.2)
mama.react(5.15, .95, -.1, head=.5, lean=2); mama.face(5.2, 'surprise', dur=.15)
papa.blink(5.8); mama.blink(6.05)

# ---- s04 close-up Ricitos asleep
s = film.shot('s04', 4.0, 'dormitorio', 'Primer plano de Ricitos. Duerme, respira, se acomoda y un rizo le cae sobre la cara.')
s.dof(3.5)
CX, CY = 930, 438
s.cam(0, CX, CY, 3.2).cam(4.0, CX-4, CY-2, 3.4, 'inout')
layer_order(s, blanket_small=.5)
rc = s.actor('ricitos', x=RX, y=RY, scale=RS, turn=1, **RC_POSE)
rc.auto_blink(False)
rc.key(0, 'life', 1.0)
curl = s.prop('curl')
rc.to(1.1, .9, 'inout', overlap=.4, head_rot=58, head_dx=-2, head_dy=2, lean=1)                # snuggles into the pillow
rc.to(1.4, .6, 'inout', overlap=.3, arm_l_x=-10, arm_l_y=30)
rc.pulse(1.5, .3, .3, .5, smile=.6, brow_y=.2)                                                  # a dreamy half smile
rc.to(2.7, .8, 'inout', overlap=.4, head_rot=60, head_dx=0, head_dy=0)
CURL_X, CURL_Y = 934.0, 402.0
curl.key(0, 'opacity', 0, 'step'); curl.key(2.2, 'opacity', 1, 'step')
curl.key(0, 'x', CURL_X); curl.key(0, 'y', CURL_Y); curl.key(0, 'scale', 1.5)
curl.key(2.2, 'frame', 0, 'step'); curl.key(2.5, 'frame', 1, 'step'); curl.key(2.78, 'frame', 2, 'step')
curl.key(2.2, 'rot', 0); curl.key(2.5, 'rot', 8, 'out'); curl.key(2.78, 'rot', 0, 'out')
curl.key(2.5, 'x', CURL_X+4, 'out'); curl.key(2.78, 'x', CURL_X+10, 'out'); curl.key(2.78, 'y', CURL_Y+10, 'out')
# the face reacts: nose twitch, a puff, the curl jumps and falls back
rc.pulse(3.0, .15, .55, .35, mouth_w=.5, mouth_round=.55, mouth_open=.18, smile=.1, brow_y=.5, brow_rot=6)
curl.key(3.18, 'frame', 1, 'step'); curl.key(3.34, 'frame', 0, 'step'); curl.key(3.6, 'frame', 2, 'step')
curl.key(3.18, 'y', CURL_Y+10); curl.key(3.3, 'y', CURL_Y-2, 'out'); curl.key(3.6, 'y', CURL_Y+10, 'in')

# ---- s05 the three bears look at each other: surprise, pause, slow grin
s = film.shot('s05', 6.0, 'dormitorio', 'Medio de los tres. Se miran entre si: sorpresa, pausa, y una sonrisa lenta compartida.')
s.dof(4.0)
s.cam(0, 490, 448, 1.75).cam(6.0, 494, 444, 1.88, 'inout')
layer_order(s, blanket_small=.5)
papa = s.actor('papa_oso', x=STOP['papa_oso'], y=DY, scale=SD, facing=1, turn=1, look_x=.9, look_y=-.1, **BASE)
mama = s.actor('mama_osa', x=STOP['mama_osa'], y=DY, scale=SD, facing=1, turn=1, look_x=.9, look_y=-.1, **BASE)
osito = s.actor('osito', x=STOP['osito'], y=DY+14, scale=SD+.02, facing=1, turn=1, look_x=.9, look_y=-.1, **BASE)
actor_order(s, papa, 1); actor_order(s, mama, 1); actor_order(s, osito, 2)
for who, ex in ((papa, 'awe'), (mama, 'surprise'), (osito, 'awe')):
    for k, v in EXPRESSIONS[ex].items():
        who.key(0, k, v)
osito.set(0, hand_l='point'); osito.key(0, 'arm_l_x', 74); osito.key(0, 'arm_l_y', -18); osito.key(0, 'arm_l_bend', .6); osito.key(0, 'lean', 3)
osito.to(.1, .5, 'inout', arm_l_x=osito.defaults['arm_l_x'], arm_l_y=osito.defaults['arm_l_y'], arm_l_bend=1.0, lean=0)
osito.set(.6, hand_l='closed')
# 0.45-0.9: the eyes leave the bed and find each other; papa and osito turn their bodies (through the front) to face the others
papa.look(.4, .1, .1, .08)                                                              # eyes jump off the bed...
papa.turn_around(.62, -1, arms=False)                                                  # ...the body follows
papa.face(.55, 'surprise', dur=.15); papa.gasp(.8, .9)
papa.look(.95, .95, .1, .1, head=.3)
mama.react(.55, .95, .1, head=.3); mama.face(.7, 'surprise', dur=.15); mama.gasp(.78, .9)
osito.turn_around(1.0, -1, arms=False); osito.face(.88, 'surprise', dur=.15)
osito.look(1.3, .95, -.5, .1, head=.3)
papa.blink(1.9); mama.blink(2.15); osito.blink(2.4)
# the pause: they stare, tiny movements only (weight settles, a swallow)
papa.pulse(1.5, .2, .3, .5, head_dy=1.5, torso_sy=1.02)
mama.pulse(1.9, .2, .3, .5, head_rot=2)
osito.look(2.2, .95, -.9, .1, head=.3)
# the grin spreads, one after the other, slowly, brows lowering (mischief)
for who, t0, big in ((papa, 2.55, .5), (mama, 2.85, .45), (osito, 3.15, .7)):
    who.to(t0, 1.7, 'inout', overlap=.4, smile=1.25, mouth_open=.2+.3*big, mouth_w=1.3, mouth_round=0, brow_y=.1, brow_rot=-8,
           eye_open=.98, squint=.35, lid=.12, pupil=1.0)
    who.to(t0+.4, 1.2, 'soft', overlap=.3, head_rot=-3, lean=1.5)
osito.pulse(3.9, .12, .05, .25, hip_dy=3, head_dy=2)                  # a gleeful little bounce
# together they turn their eyes, then heads, back to the small bed, grin held
papa.turn_around(4.7, 1, arms=False); osito.turn_around(4.9, 1, arms=False)
for who, t0 in ((papa, 5.05), (mama, 4.85), (osito, 5.2)):
    who.look(t0, .95, .25, .12, head=.4)
papa.to(4.9, .5, 'inout', lean=3); mama.to(4.95, .5, 'inout', lean=3); osito.to(5.0, .5, 'inout', lean=3)

# ---- s06 baberos
s = film.shot('s06', 7.0, 'dormitorio', 'Medio. Uno tras otro sacan un babero y se lo atan al cuello: papa, mama y osito, tarde y torpe.')
s.dof(4.0)
s.cam(0, 490, 448, 1.8).cam(7.0, 496, 446, 1.9, 'inout')
layer_order(s, blanket_small=.5)
papa = s.actor('papa_oso', x=STOP['papa_oso'], y=DY, scale=SD, facing=1, turn=1, look_x=.95, look_y=.25, **BASE)
mama = s.actor('mama_osa', x=STOP['mama_osa'], y=DY, scale=SD, facing=1, turn=1, look_x=.95, look_y=.25, **BASE)
osito = s.actor('osito', x=STOP['osito'], y=DY+14, scale=SD+.02, facing=1, turn=1, look_x=.95, look_y=.25, **BASE)
actor_order(s, papa, 1); actor_order(s, mama, 1); actor_order(s, osito, 2)
GRIN = dict(smile=1.1, mouth_open=.25, mouth_w=1.15, mouth_round=0, brow_y=.1, brow_rot=-8, eye_open=.98, squint=.35, lid=.12)
for who in (papa, mama, osito):
    for k, v in GRIN.items():
        who.key(0, k, v)
    who.key(0, 'lean', 3)


def bib_on(who, t0, hurry=1.0, side='l'):
    """Reach behind the back, pull the bib out, show it, raise it to the neck, it snaps on, tie it behind the head, pat it.
    Returns the time the bib is settled. `hurry` stretches the timing."""
    h, a = f'hand_{side}', f'arm_{side}'
    k = hurry
    rest = who.rest_arm(side)
    who.to(t0, .18*k, 'out', overlap=0, lean=6, hip_dy=2)                                                 # anticipation: bends to reach back
    who.to(t0+.1*k, .32*k, 'inout', overlap=.2, **{a+'_x': -34, a+'_y': 58, a+'_bend': 1.0})              # hand goes behind the back
    who.look(t0+.1*k, .2, .4, .1, head=.2)
    who.set(t0+.5*k, **{h: 'grip', 'item_'+side: 'babero_mano'})                                            # pulls it from the back pocket
    who.to(t0+.5*k, .22*k, 'out', overlap=.2, lean=-2, **{a+'_x': 10, a+'_y': 46})
    who.to(t0+.72*k, .4*k, 'back', overlap=.2, lean=0, **{a+'_x': 40, a+'_y': -8, a+'_bend': .8})         # out and up: "ta-da"
    who.look(t0+.9*k, .9, .9, .1, head=.5)                                                                  # looks down at the bib
    who.pulse(t0+1.1*k, .15, .1, .3, hip_dy=1.5, head_dy=2)
    who.to(t0+1.4*k, .3*k, 'inout', overlap=.2, lean=-1, **{a+'_x': 20, a+'_y': -66, a+'_bend': .6})       # up to the neck
    who.look(t0+1.4*k, .5, 0, .1, head=.3)
    on = t0+1.75*k
    who.set(on, **{'item_'+side: '', 'wear': 'babero'})                                                      # it snaps onto the chest
    who.pulse(on, .08, .05, .25, torso_sy=1.04, shoulder_l_dy=-3, shoulder_r_dy=-3)
    who.to(on, .22*k, 'out', overlap=.2, head_rot=-2, **{a+'_x': 4, a+'_y': -96, a+'_bend': .8})             # hand up behind the head
    # tying: fingers busy behind the neck, head tilts and moves with the tugs
    for i in range(3):
        who.to(on+.2*k+i*.2*k, .1*k, 'sine', overlap=0, head_rot=-3+2*(i % 2), head_dx=(1 if i % 2 else -1)*1.2,
               **{a+'_x': 2, a+'_y': -98, h+'_rot': 14})
        who.to(on+.3*k+i*.2*k, .1*k, 'sine', overlap=0, **{a+'_x': 8, a+'_y': -92, h+'_rot': -14})
    done = on+.9*k
    who.set(done, **{h: 'closed'})
    who.to(done, .32*k, 'inout', overlap=.2, head_dx=0, head_rot=0, **{a+'_x': 22, a+'_y': 36, a+'_bend': .9, h+'_rot': 0})    # pat the bib
    who.look(done, .95, .4, .1, head=.3)
    who.pulse(done+.32*k, .1, .08, .2, **{a+'_y': 26})
    who.pulse(done+.62*k, .1, .08, .25, torso_sy=1.02, **{a+'_y': 26})
    who.set(done+.95*k, **{h: 'closed'})
    who.to(done+.95*k, .4, 'inout', overlap=.2, lean=3, **{a+'_x': rest[a+'_x'], a+'_y': rest[a+'_y'], a+'_bend': 1.0})
    return done+.95*k


T_PAPA = bib_on(papa, .45, 1.0)
T_MAMA = bib_on(mama, 1.95, 1.0)
papa.face(T_PAPA, 'happy', dur=.3); mama.face(T_MAMA, 'happy', dur=.3)
# listeners react: each looks at whoever is busy
mama.react(.9, -.1, .6, head=.4)
mama.look(T_PAPA-.5, .95, .6, .1, head=.3)
papa.react(2.3, -.9, .1, head=.4); papa.look(T_MAMA+.3, .3, .6, .1, head=.3)
osito.react(1.0, -.9, -.4, head=.5); osito.react(2.4, -.9, -.4, head=.5)
osito.look(3.0, .95, .9, .1, head=.2)
papa.blink(3.0); mama.blink(4.2)

# osito: late and clumsy. He realises he is behind, reaches back twice and misses, pulls the bib out crooked, cannot reach the knot.
o = osito
o.face(3.1, 'oops', dur=.15)
o.gasp(3.15, .9)
o.to(3.3, .2, 'out', overlap=0, lean=9, hip_dy=3)
for i, tt in enumerate((3.4, 4.0)):                                              # two misses: the arm swings behind and finds nothing
    o.to(tt, .22, 'inout', overlap=.2, arm_l_x=-30+6*i, arm_l_y=44+5*i, lean=9, head_rot=5)
    o.to(tt+.25, .2, 'out', overlap=.2, arm_l_x=-10, arm_l_y=70, lean=3)
    o.look(tt+.1, -.5, .3, .1, head=.2)
o.face(3.8, 'worried', dur=.2)
o.to(4.5, .22, 'inout', overlap=.2, arm_l_x=-36, arm_l_y=52, lean=10, head_rot=6)
o.set(4.75, hand_l='grip', item_l='babero_mano')
o.to(4.75, .2, 'out', overlap=.2, arm_l_x=8, arm_l_y=48, lean=0)
o.face(4.75, 'happy', dur=.15)
o.to(4.95, .4, 'back', overlap=.2, arm_l_x=42, arm_l_y=-8, arm_l_bend=.8, hand_l_rot=25)                 # holds it up crooked
o.to(5.5, .3, 'inout', overlap=.2, arm_l_x=24, arm_l_y=-60, arm_l_bend=.6, hand_l_rot=0, lean=-1)       # to the neck
o.set(5.85, item_l='', wear='babero')
o.pulse(5.85, .08, .05, .25, torso_sy=1.04)
o.to(5.85, .25, 'out', overlap=.2, arm_l_x=-2, arm_l_y=-88, arm_r_x=12, arm_r_y=-84, arm_l_bend=.9, head_rot=-4)     # arms too short: strains
for i in range(4):
    o.to(6.1+i*.22, .11, 'sine', overlap=0, arm_l_x=-6, arm_l_y=-92, head_dx=1.4*(1 if i % 2 else -1), head_rot=3*(1 if i % 2 else -1))
    o.to(6.21+i*.22, .11, 'sine', overlap=0, arm_l_x=2, arm_l_y=-84)
o.pulse(6.3, .12, .3, .3, hip_dy=-3, torso_sy=1.03)                                                       # on tiptoe, straining
o.face(6.4, 'focus', dur=.2)
o.to(7.0, .25, 'out', overlap=.2, arm_l_x=24, arm_l_y=14, arm_l_bend=.9, lean=2)
o.face(7.0, 'joy', dur=.15)
papa.look(5.9, -.95, .5, .1, head=.3); mama.look(5.7, .95, .5, .1, head=.3)                         # the parents watch him struggle
papa.face(5.9, 'soft', dur=.3); mama.face(5.7, 'soft', dur=.3)
papa.look(6.9, .95, .3, .1, head=.2); mama.look(6.9, .95, .3, .1, head=.2)

# ---- s07 tenedores
s = film.shot('s07', 5.5, 'dormitorio', 'Medio. Sacan tenedor y cuchillo, los levantan a la vez y se relamen.')
s.dof(2.5)
s.cam(0, 560, 440, 1.4).cam(5.5, 600, 436, 1.5, 'inout')
layer_order(s, blanket_small=.5)
papa = s.actor('papa_oso', x=STOP['papa_oso'], y=DY, scale=SD, facing=1, turn=1, look_x=.95, look_y=.2, **dict(BASE, wear='babero'))
mama = s.actor('mama_osa', x=STOP['mama_osa'], y=DY, scale=SD, facing=1, turn=1, look_x=.95, look_y=.2, **dict(BASE, wear='babero'))
osito = s.actor('osito', x=STOP['osito'], y=DY+14, scale=SD+.02, facing=1, turn=1, look_x=.95, look_y=.2, **dict(BASE, wear='babero'))
actor_order(s, papa, 1); actor_order(s, mama, 1); actor_order(s, osito, 2)
rc = s.actor('ricitos', x=RX, y=RY, scale=RS, turn=1, **RC_POSE)
rc.auto_blink(False)
for who in (papa, mama, osito):
    for k, v in dict(GRIN, smile=1.05, mouth_open=.15).items():
        who.key(0, k, v)
    who.key(0, 'lean', 3)
for who, t0 in ((papa, .35), (mama, .6), (osito, .85)):                  # fork out from behind the back, one after another
    who.to(t0, .2, 'out', overlap=0, lean=6, hip_dy=2)
    who.to(t0+.1, .3, 'inout', overlap=.2, arm_l_x=-30, arm_l_y=56, arm_l_bend=1.0)
    who.set(t0+.5, hand_l='grip', item_l='cuchillo')
    who.to(t0+.5, .3, 'back', overlap=.2, arm_l_x=14, arm_l_y=56, lean=2)
    who.look(t0+.5, .5, .2, .1, head=.2)
CID = dict(papa_oso='papa_oso', mama_osa='mama_osa', osito='osito')
SPREAD = dict(papa_oso=5., mama_osa=-32., osito=38.)
for who, dl in ((papa, 0.0), (mama, .03), (osito, .06)):                 # together: crouch, turn to the camera, both forks up with overshoot
    who.to(1.55+dl, .3, 'inout', overlap=0, turn=0.0)                                                       # three-quarter -> front
    who.to(1.5+dl, .6, 'inout', overlap=0, x=STOP[CID[who.ref]]+SPREAD[who.ref])                          # a small side-step to make room for the raised arms
    who.to(1.7+dl, .3, 'out', overlap=0, lean=-1, hip_dy=5, torso_sy=.96, arm_l_x=-30, arm_l_y=66, arm_r_x=30, arm_r_y=66)   # anticipation
    who.set(1.75+dl, hand_r='grip', item_r='tenedor')
    who.to(2.0+dl, .2, 'out', overlap=.2, hip_dy=-2, torso_sy=1.05, arm_l_x=-50, arm_l_y=-76, arm_r_x=50, arm_r_y=-76,
           arm_l_bend=.8, arm_r_bend=-.8, hand_l_rot=-70, hand_r_rot=70, lean=0)
    who.to(2.2+dl, .3, 'soft', overlap=.2, hip_dy=0, torso_sy=1.0, arm_l_x=-44, arm_l_y=-66, arm_r_x=44, arm_r_y=-66, hand_l_rot=-58, hand_r_rot=58)
    who.drift(2.7+dl, 5.4, 1.1, arm_l_x=2, arm_l_y=2, arm_r_x=2, arm_r_y=2, hand_l_rot=5, hand_r_rot=-5)
    who.look(1.8+dl, 0, .15, .1, head=.0)
# the lick: tongue out, left to right, twice; eyes narrow, a hungry lean forward
for who, dl in ((papa, 0.0), (mama, .12), (osito, .24)):
    who.face(2.5+dl, 'happy', dur=.2, mouth_open=.6, squint=.4)
    for i in range(2):
        who.to(3.0+dl+i*.55, .22, 'inout', overlap=0, mouth_w=1.35, mouth_open=.75, head_rot=5, face_x=.12)
        who.to(3.22+dl+i*.55, .3, 'inout', overlap=0, mouth_w=.85, mouth_open=.5, head_rot=-3, face_x=-.12)
    who.to(3.9+dl, .5, 'inout', overlap=.2, mouth_w=1.1, mouth_open=.3, head_rot=1, lean=5, face_x=0)
    who.blink(1.6+dl, 4.6+dl)
osito.laugh(4.1, .8, beats=3, strength=.4)

# ---- s08 final
s = film.shot('s08', 4.0, 'dormitorio', 'Primer plano de Ricitos. Sigue dormida; al final abre un ojo. Fundido a negro.')
s.dof(3.5)
s.cam(0, CX, CY, 3.3).cam(4.0, CX-3, CY-2, 3.5, 'inout')
layer_order(s, blanket_small=.5)
rc = s.actor('ricitos', x=RX, y=RY, scale=RS, turn=1, **RC_POSE)
rc.auto_blink(False)
rc.pulse(.5, .3, .3, .5, smile=.7)                                           # still dreaming
rc.to(1.2, .8, 'inout', overlap=.4, head_dx=1.5, head_dy=-1)
# the eye opens slowly, a thin slit first; the pupil slides to the bears
rc.to(2.2, .5, 'inout', overlap=0, lid_r=-.3)
rc.to(2.7, .22, 'out', overlap=0, lid_r=-1.0, eye_open=1.1)
rc.look(2.7, -1, -.1, .15)
rc.to(2.7, .3, 'out', overlap=.3, smile=.15, brow_y=.4, mouth_w=.6)
rc.to(3.2, .5, 'inout', overlap=.3, brow_rot=6)
s.fade_out(.7)

# ------------------------------------------------------------------ export
STYLE = {'hold': 2, 'contour': .9, 'boil': .32, 'boil_hold': 3}
script = film.export(
    revision=0, story=STORY, style=STYLE,
    bible={'style': 'Cartoon de TV infantil, colores planos, contorno marron grueso, paleta calida.', 'story': STORY,
           'continuity': 'Osos mirando a la derecha; papa delante, luego mama y osito. Bosque: suelo y=640, escala .62. Dormitorio: suelo y=655, escala .70. Sin audio.'},
    characters={cid: f'characters/{cid}.json' for cid in CH},
    sets={'bosque': 'sets/bosque.json', 'dormitorio': 'sets/dormitorio.json'})
script = group_scene(script, 'llegada', 'bosque', 'Llegada a la cabana', 'Los tres osos llegan por el sendero, huelen el aire y entran por la puerta.')
script = group_scene(script, 'dormitorio', 'dormitorio', 'El dormitorio', 'Los osos descubren a Ricitos dormida en la cama pequena.')
ep_root = root/'episodes'/'ep01'     # the project is a series; this script writes episode ep01
script = save(ep_root, json.loads(json.dumps(script)))
compiled = json.loads((ep_root/'film.json').read_text(encoding='utf-8'))
print(json.dumps({'script': str(ep_root/'script.json'), 'shots': [(x['id'], x['duration']) for x in compiled['shots']],
                  'seconds': round(sum(x['duration'] for x in compiled['shots']), 3)}))
