"""'El taller del valle — Una visita con alas'. Records the screenplay as projects/taller-v3/script.json (and sets/valley.json)
and compiles film.json from it. From now on script.json is the source of truth; this script only regenerates the pilot.

Story: Luma arrives at the workshop; Pip greets her; a butterfly lands on Pip's antenna; he tries to stay
still, sneezes, and the butterfly moves to Luma's ear before flying off into the sunset. Silent (audio deferred).
"""
import json
import math
import sys
from pathlib import Path

base = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(base))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from celstudio.v2.direct import Film, EXPRESSIONS  # noqa: E402
from celstudio.v2.project import group_scene, save  # noqa: E402
from valley_set import valley, root, SUN  # noqa: E402

GY, SC = 690.0, .66
PROFILE_WALK = True     # Luma's walks in profile (needs the profile art in characters/luma.json); False = three-quarter walks
WALK = {'view': 'profile'} if PROFILE_WALK else {}     # no argument when off: script.json stays identical to the three-quarter one
BUTTERFLY = {'id': 'butterfly', 'sheet': 'assets/props/butterfly-sheet.png',
             'cells': [[112, 293, 452, 638], [651, 288, 991, 633], [1206, 285, 1546, 630]],
             'pivot': [222, 262], 'upp': .112, 'layer': 'front', 'shadow': {'ground': GY+6, 'width': 30}}
BUTTERFLY_POSES = True  # volumetric wing poses (open, half, closed edge-on, landing); False = the old flat sheet
if BUTTERFLY_POSES:
    BUTTERFLY = {'id': 'butterfly', 'sheet': 'assets/props/butterfly-poses-sheet.png',
                 'cells': [[i*640, 0, (i+1)*640, 640] for i in range(4)],
                 'pivot': [330, 330], 'upp': .093, 'layer': 'front', 'shadow': {'ground': GY+6, 'width': 30},
                 'flap_frames': [0, 1, 2, 1], 'perch_rest': 3}
PUFF = {'sheet': 'assets/props/puff-sheet.png', 'cells': [[147, 370, 451, 629], [617, 322, 1045, 644], [1160, 351, 1565, 628]],
        'upp': .12, 'layer': 'front'}
PUFF_PHASES = True      # dust in 4 drawn phases (burst, expanding, full, dissipating); False = the old single-sticker puffs
if PUFF_PHASES:
    PUFF = {'sheet': 'assets/props/puff-phases-sheet.png',
            'cells': [[116, 274, 343, 470], [565, 264, 905, 494], [1035, 174, 1557, 569], [1677, 231, 2069, 509]],
            'upp': .11, 'layer': 'front', 'phases': True}
rigs = {cid: json.loads((root/f'characters/{cid}.json').read_text(encoding='utf-8')) for cid in ('luma', 'pip')}
film = Film('taller-v3', 'El taller del valle — Una visita con alas', rigs, props={'butterfly': BUTTERFLY, 'puff': PUFF})
STORY = ('Luma llega al taller. Pip la saluda. Una mariposa se posa en la antena de Pip; él intenta no moverse, estornuda, '
         'y la mariposa termina en la oreja de Luma antes de irse hacia el sol.')


# ───────────────────────── s01 · establishing: Luma arrives ─────────────────────────
s = film.shot('s01', 6.0, 'valley', 'General. El taller al atardecer; Pip trabaja en su banco, Luma llega caminando.')
s.dof(1.6)
s.cam(0, 612, 388, 1.04).cam(6.0, 646, 402, 1.12, 'inout')
s.fade_in(.9)
s.overlay(kind='title', title='El taller del valle', subtitle='Una visita con alas',
          keys=[[.9, 0], [1.9, 1, 'out'], [3.7, 1], [4.4, 0, 'in']])
pip = s.actor('pip', x=838, y=GY, scale=SC, facing=1, look_x=.7, look_y=.55, smile=.3, brow_y=-.2, brow_rot=-6)
pip.key(0, 'arm_r_x', 46); pip.key(0, 'arm_r_y', 34); pip.key(0, 'arm_l_x', 42); pip.key(0, 'arm_l_y', 20)
pip.key(0, 'lean', 7); pip.key(0, 'head_rot', 5)
t = .3
while t < 5.0:                    # tinkering: little hammer taps
    pip.to(t, .16, 'out', overlap=0, arm_l_y=4, arm_l_x=36, hand_l_rot=-25)
    pip.to(t+.16, .09, 'in', overlap=0, arm_l_y=24, arm_l_x=44, hand_l_rot=10)
    pip.pulse(t+.25, .05, 0, .16, head_dy=1.6)
    t += .5 if int(t*2) % 5 else .95
luma = s.actor('luma', x=-60, y=GY, scale=SC, look_x=.55, look_y=-.25, **{'smile': .75})
luma.walk(.7, 7.4, -70, 482, scale=SC, step=56, lift=16, swing=24, bob=3.4, **WALK)
luma.face(3.2, 'curious', look_x=.8)
luma.look(3.1, .85, -.1, .12, head=.4)
luma.face(4.9, 'awe')
pip.to(5.05, .16, 'out', overlap=0, arm_l_y=10, arm_l_x=38, hand_l_rot=-12)      # hammer stops mid-air: he heard something
pip.to(5.12, .3, 'back', head_dy=-2, lean=3, torso_sy=1.02)
pip.look(5.35, -.6, -.05, .09, head=.3)                                          # eyes first, head a beat later

# ───────────────────────── s02 · Pip notices and waves ─────────────────────────
s = film.shot('s02', 3.8, 'valley', 'Medio de Pip. Oye pasos, mira atrás, gira con alegría y saluda.')
s.dof(4.5)
s.cam(0, 846, 548, 2.12).cam(3.8, 836, 544, 2.24, 'inout')
pip = s.actor('pip', x=838, y=GY, scale=SC, facing=1, look_x=-.6, look_y=-.05, smile=.3, brow_y=-.2, brow_rot=-6)
pip.key(0, 'arm_r_x', 46); pip.key(0, 'arm_r_y', 34); pip.key(0, 'arm_l_x', 38); pip.key(0, 'arm_l_y', 10)
pip.key(0, 'hand_l_rot', -12); pip.key(0, 'face_x', -.18)
pip.key(0, 'lean', 3); pip.key(0, 'head_rot', 5); pip.key(0, 'head_dy', -2); pip.key(0, 'torso_sy', 1.02)
# perk: already listening when the cut lands; the eyes go all the way back, then the head
pip.face(.2, 'curious', dur=.12)
pip.look(.25, -.95, -.1, .08, head=.5)
pip.to(.3, .14, 'back', overlap=.5, head_dy=-4, head_rot=-3, lean=2, torso_sy=1.03, arm_l_y=22, arm_l_x=44, hand_l_rot=0)
pip.drift(.5, 1.0, 1.0, head_rot=1.2, lean=.8)
pip.blink(.95)
pip.turn_around(1.12, -1)
pip.look(1.2, .75, 0, .08, head=.3)
pip.to(1.18, .22, 'back', arm_l_x=-5, arm_l_y=83, arm_r_x=5, arm_r_y=83, hand_l_rot=0, lean=-3, head_rot=-4, head_dy=0, torso_sy=1)
pip.face(1.34, 'happy', dur=.16)
pip.gasp(1.36, .7)
end = pip.wave(1.86, 'l', cycles=3, period=.34)
pip.to(end-.2, .4, 'inout', lean=0, head_rot=0)
pip.face(3.3, 'soft')

# ───────────────────────── s03 · Luma reacts ─────────────────────────
s = film.shot('s03', 3.6, 'valley', 'Medio de Luma. Se detiene, descubre a Pip, salta de alegría y saluda.')
s.dof(4.5)
s.cam(0, 462, 548, 2.1).cam(3.6, 486, 544, 2.2, 'inout')
luma = s.actor('luma', x=420, y=GY, scale=SC, look_x=.8, look_y=-.05)
for name, value in dict(smile=.45, mouth_open=.38, mouth_w=.62, mouth_round=.7, brow_y=.85, brow_rot=6, eye_open=1.14, pupil=1.12).items():
    luma.key(0, name, value)
luma.walk(-1.4, .78, 345, 500, scale=SC, step=56, lift=16, swing=24, bob=3.4, phase=.35, **WALK)
luma.to(.74, .14, 'out', lean=10, hip_dy=6, head_rot=3)           # stop: weight carries forward
luma.look(.72, 1, 0, .06, head=.7)                                  # eyes land on Pip first
luma.to(.9, .3, 'back', lean=-9, hip_dy=-1, head_rot=-6, head_dy=-4, torso_sy=1.05)   # double take: rocks back, chest up
luma.face(.82, 'surprise', dur=.1, brow_y=1.3)
luma.to(.84, .2, 'out', overlap=0, arm_l_x=-26, arm_l_y=56, arm_r_x=26, arm_r_y=56, hand_l_rot=-25, hand_r_rot=25)   # hands flare out
luma.blink(1.12)
luma.to(1.14, .2, 'inout', lean=-2, head_dy=0, torso_sy=1)
luma.face(1.22, 'happy', dur=.16)
land = luma.hop(1.36, height=26, air=.36)
luma.to(1.36, .16, 'out', overlap=0, arm_l_x=-30, arm_l_y=50, arm_r_x=30, arm_r_y=50)
luma.to(1.52, .2, 'back', overlap=0, arm_l_x=-52, arm_l_y=-6, arm_r_x=54, arm_r_y=-10)
luma.to(land, .3, 'soft', overlap=0, arm_l_x=-5, arm_l_y=83, arm_r_x=5, arm_r_y=83)
luma.face(1.5, 'joy', dur=.1)
luma.face(land+.12, 'happy', dur=.2)
end = luma.wave(land+.3, 'l', cycles=3, period=.32)
luma.to(end-.25, .4, 'inout', lean=0, head_rot=0)

# ───────────────────────── s04 · meeting; the butterfly arrives ─────────────────────────
s = film.shot('s04', 6.6, 'valley', 'Plano de dos. Luma se acerca; se saludan con una reverencia. Llega una mariposa.')
s.dof(3.0)
s.cam(0, 655, 540, 1.58).cam(2.4, 688, 532, 1.64, 'inout').cam(6.6, 704, 500, 1.66, 'inout')
luma = s.actor('luma', x=500, y=GY, scale=SC, look_x=.8)
pip = s.actor('pip', x=838, y=GY, scale=SC, facing=-1, look_x=.8)
luma.face(0, 'happy'); pip.face(0, 'soft')
luma.walk(.3, 1.75, 500, 612, scale=SC, step=54, lift=15, swing=28, bob=3.2, **WALK)
# the cut lands mid-wave (end of s03): she is still waving and lowers the arm into the walk
luma.set(0, hand_l='open')
luma.key(0, 'arm_l_x', -78); luma.key(0, 'arm_l_y', -42); luma.key(0, 'arm_l_bend', .9); luma.key(0, 'hand_l_rot', 18)
luma.to(.0, .3, 'inout', overlap=0, arm_l_x=-5, arm_l_y=luma.defaults['arm_l_y'], arm_l_bend=1.0, hand_l_rot=0)
luma.set(.3, hand_l='closed')
luma.to(1.72, .12, 'out', lean=6, hip_dy=4)
luma.to(1.84, .28, 'back', lean=0, hip_dy=0)
luma.blink(1.5)
# Pip listens: eyes follow her in, a nod, weight settles when she stops
pip.look(.15, .8, .1, .08, head=.3)
pip.to(.18, .14, 'out', overlap=0, lean=3, head_dy=2)
pip.to(.32, .2, 'back', overlap=0, lean=-3, head_dy=-1)
pip.react(1.6, .85, 0, head=.35)
pip.pulse(1.74, .1, .08, .3, hip_dy=3, head_dy=1.5)
# Pip opens his arms in welcome, then both bow with an offset
pip.to(.38, .12, 'out', overlap=0, lean=3, head_dy=3, torso_sy=.97)          # anticipation: gathers before opening his arms
pip.to(.5, .3, 'back', arm_l_x=-44, arm_l_y=46, arm_r_x=50, arm_r_y=40, hand_l_rot=-30, hand_r_rot=30, lean=-5, head_dy=-2, torso_sy=1.02)
pip.to(.84, .3, 'inout', overlap=0, head_dy=0, torso_sy=1)
pip.set(.5, hand_l='open', hand_r='open')
pip.face(.5, 'happy')
pip.to(1.7, .35, 'inout', arm_l_x=-5, arm_l_y=83, arm_r_x=5, arm_r_y=83, hand_l_rot=0, hand_r_rot=0, lean=0)
pip.set(2.0, hand_l='closed', hand_r='closed')
for who, t0 in ((luma, 2.05), (pip, 2.3)):
    who.to(t0, .12, 'out', lean=-3, head_rot=-3)                              # anticipation
    who.to(t0+.12, .34, 'inout', lean=13, bend=11, head_rot=9, hip_dy=5, hip_dx=-4, lid=1, arm_l_x=6, arm_r_x=14)
    who.to(t0+.72, .4, 'back', lean=0, bend=0, head_rot=0, hip_dy=0, hip_dx=0, lid=0, arm_l_x=-5, arm_r_x=5)
    who.face(t0+.9, 'happy')
bf = s.prop('butterfly')
bf.key(0, 'opacity', 0, 'step'); bf.key(3.0, 'opacity', 1, 'step')
bf.path(3.0, 6.6, [(400, 330), (520, 440), (655, 468), (735, 425), (700, 375), (772, 352), (852, 392), (822, 420)], flutter=6, seed=1.3)
bf.flap(3.0, 6.6, rate=5.5)
luma.blink(3.42)
luma.look(3.55, -.2, -.9, .1, head=.5)
luma.face(3.6, 'awe')
luma.gasp(3.62, .7)
luma.track(bf, 3.7, 6.6, 612, 1)
# points at it: breath and pull-back, arm shoots past the target, settles, then lives in the hold
luma.to(4.26, .16, 'out', overlap=0, lean=-3, arm_r_x=14, arm_r_y=64)
luma.to(4.42, .2, 'out', arm_r_x=98, arm_r_y=-32, arm_r_bend=.55, lean=7, head_dy=-2)
luma.set(4.5, hand_r='point')
luma.to(4.62, .3, 'soft', arm_r_x=86, arm_r_y=-24, arm_r_bend=.7, lean=4, head_dy=0)
luma.drift(5.0, 6.5, 1.3, arm_r_x=2.5, arm_r_y=2.2, hand_r_rot=4, lean=.9)
luma.to(5.45, .08, 'out', overlap=.3, arm_r_x=94, arm_r_y=-30, head_rot=4, head_dy=2)    # "there!" jab as it flutters toward Pip
luma.to(5.6, .3, 'soft', overlap=.3, arm_r_x=86, arm_r_y=-24, head_rot=0, head_dy=0)
pip.face(4.2, 'curious')
pip.look(4.2, .7, -.5, .1, head=.4)
pip.to(4.35, .3, 'back', lean=-3, head_rot=4, head_dy=-2)                    # leans away to look where she points
pip.track(bf, 4.5, 6.6, 838, -1)
pip.face(5.6, 'awe')
pip.to(5.7, .3, 'back', lean=-7, head_dy=-3, torso_sy=1.03, arm_l_x=-12, arm_r_x=12)   # it comes at him: recoil, freeze

# ───────────────────────── s05 · close on Pip: it lands on his antenna ─────────────────────────
s = film.shot('s05', 4.8, 'valley', 'Primer plano de Pip. La mariposa se posa en su antena; se queda inmóvil, bizco.')
s.dof(6.5)
s.cam(0, 812, 512, 2.4).cam(4.8, 808, 504, 2.55, 'inout')
pip = s.actor('pip', x=838, y=GY, scale=SC, facing=-1)
pip.auto_blink(False)
pip.face(0, 'awe')
pip.key(0, 'lean', -7); pip.key(0, 'head_dy', -3); pip.key(0, 'torso_sy', 1.03)    # same recoil as the end of s04
pip.to(.3, .5, 'inout', lean=-2, head_dy=0, torso_sy=1)
bf = s.prop('butterfly', anchor={'actor': 'pip', 'point': 'tip_antenna', 'dx': 2, 'dy': -3})
bf.path(0, 1.25, [(822, 420), (792, 396), (812, 410), (797, 420)], flutter=4.5, seed=4.1)
bf.flap(0, 1.2, rate=5.5)
bf.key(.85, 'attach', 0); bf.key(1.25, 'attach', 1, 'out')
bf.key(1.25, 'facing', -1, 'step')
bf.perch(1.25, 4.8, 1.7)
pip.track(bf, 0, .8, 838, -1, head=.4)
pip.look(.9, .3, -1, .1, head=.35)
pip.pulse(1.22, .07, .02, .3, head_dy=4.5, head_rot=3.5)                 # the landing nudges the antenna
pip.face(1.3, 'still', dur=.14)
pip.to(1.18, .1, 'out', overlap=0, lean=-6, torso_sy=1.06)                 # the touch: whole body snaps rigid
pip.to(1.3, .3, 'out', shoulder_l_dy=-9, shoulder_r_dy=-9, torso_sy=1.04, lean=-3, arm_l_x=-14, arm_r_x=14, arm_l_y=78, arm_r_y=78)
pip.key(1.3, 'life', 1); pip.key(1.6, 'life', .4)
t = 2.0
while t < 4.7:                                                          # tiny tremble from holding still
    pip.key(t, 'head_dx', .55*math.sin(t*41), 'linear')
    t += 1/24
pip.pulse(1.95, .3, .3, .5, torso_sy=1.045, shoulder_l_dy=-13, shoulder_r_dy=-13, hip_dy=-1)     # a held breath: chest up, shoulders up
pip.pulse(2.15, .2, .5, .5, head_rot=-4, lean=-1)                       # head tilts toward the weight on the antenna
pip.pulse(3.0, .25, .3, .5, torso_sy=1.045, shoulder_l_dy=-13, shoulder_r_dy=-13, hip_dy=-1)
pip.pulse(3.8, .18, .2, .4, head_rot=3, lean=-4, head_dy=1.5)           # the wings shift: a flinch that tries not to move
pip.pulse(4.3, .2, .3, .45, torso_sy=1.05, shoulder_l_dy=-14, shoulder_r_dy=-14, mouth_w=.36, mouth_open=.3)   # the tickle builds
pip.pulse(2.85, .08, .1, .2, mouth_w=.36, smile=.2)                     # lip twitch: a nervous half-giggle
pip.look(2.45, .95, .05, .09)                                           # eyes ask Luma for help
pip.to(2.5, .15, 'out', brow_rot=12, smile=-.15)
pip.look(3.25, .3, -1, .09)
pip.to(3.3, .2, 'out', brow_rot=5, smile=.05)
pip.blink(3.9)
pip.look(4.25, .9, .1, .08, head=.3)                                    # last plea: eyes to Luma just before the cut
pip.to(4.2, .4, 'inout', mouth_w=.42, mouth_round=.6, mouth_open=.22, brow_rot=14)   # the tickle begins

# ───────────────────────── s06 · close on Luma: delighted, hushes ─────────────────────────
s = film.shot('s06', 3.6, 'valley', 'Primer plano de Luma. Se tapa la boca para no reír y señala la antena.')
s.dof(6.5)
s.cam(0, 664, 540, 2.36).cam(3.6, 670, 534, 2.5, 'inout')
luma = s.actor('luma', x=612, y=GY, scale=SC, look_x=.85, look_y=-.55, face_x=.4, face_y=-.3)
luma.face(0, 'awe')
luma.gasp(.2, .6)
luma.set(0, hand_r='closed')                                            # (the single 'point' key at 2.24 used to hold for the whole shot)
luma.face(.74, 'joy', dur=.16, mouth_open=.5)                           # the face follows the arms instead of changing on their first frame
luma.to(.3, .12, 'inout', overlap=0, arm_l_x=-2, arm_r_x=2, arm_l_y=90, arm_r_y=88, lean=-2, head_dy=1.5)   # anticipation: the arms sink and gather
luma.to(.42, .6, 'inout', overlap=.4, arm_l_x=-66, arm_l_y=-64, arm_l_bend=.8, hand_l_rot=-20, arm_r_x=86, arm_r_y=-42, arm_r_bend=.8, hand_r_rot=20)
luma.drift(.95, 2.05, .85, arm_l_x=2.5, arm_r_x=2.5, arm_l_y=3, arm_r_y=3, hand_l_rot=7, hand_r_rot=7, lean=1)   # trembling with a held laugh
luma.laugh(.8, 1.2, beats=5, strength=.55)
luma.look(1.45, .95, -.25, .08)
luma.blink(1.9)
luma.face(2.05, 'happy', dur=.2, mouth_open=.3)
luma.look(2.0, .85, -.6, .1)
luma.to(2.1, .26, 'back', arm_r_x=88, arm_r_y=-34, arm_r_bend=.6, hand_r_rot=-12, lean=5)
luma.set(2.24, hand_r='point')
luma.to(2.1, .28, 'in', arm_l_x=-5, arm_l_y=89, arm_l_bend=1, hand_l_rot=0)       # left arm drops, dips below rest...
luma.to(2.38, .2, 'inout', arm_l_x=-5, arm_l_y=83)                                # ...and settles
luma.to(2.88, .08, 'out', overlap=.3, arm_r_x=97, arm_r_y=-38, head_dy=2)       # "shh" jab at the antenna
luma.to(3.0, .3, 'soft', overlap=.3, arm_r_x=88, arm_r_y=-34, head_dy=0)
luma.nod(2.6, 2, 6, .3)

# ───────────────────────── s07 · the sneeze ─────────────────────────
s = film.shot('s07', 6.4, 'valley', 'Plano de dos. Pip aguanta… y estornuda. La mariposa sale volando; ambos ríen.')
s.dof(3.0)
T = 2.55                                                                # sneeze frame
s.cam(0, 716, 528, 1.72).cam(T-.1, 730, 522, 1.86, 'in').cam(T+.5, 706, 530, 1.62, 'out').cam(6.4, 690, 522, 1.6, 'inout')
s.cam(0, shake=0).cam(T, shake=0, ease='step').cam(T+.02, shake=7, ease='step').cam(T+.5, shake=0, ease='out')
luma = s.actor('luma', x=612, y=GY, scale=SC, look_x=.85, look_y=-.5, face_x=.4, face_y=-.3)
pip = s.actor('pip', x=838, y=GY, scale=SC, facing=-1, look_x=.3, look_y=-1)
pip.auto_blink(False)
luma.face(0, 'happy', mouth_open=.25)
# the cut lands on s06's pose: the pointing arm is still up and comes down
luma.set(0, hand_r='point')
luma.key(0, 'arm_r_x', 88); luma.key(0, 'arm_r_y', -34); luma.key(0, 'arm_r_bend', .6); luma.key(0, 'hand_r_rot', -12)
luma.to(.08, .5, 'inout', overlap=0, arm_r_x=5, arm_r_y=83, arm_r_bend=-1, hand_r_rot=0)
luma.set(.5, hand_r='closed')
pip.face(0, 'still')
for name, value in dict(mouth_w=.42, mouth_round=.6, mouth_open=.22, brow_rot=14).items():
    pip.key(0, name, value)
bf = s.prop('butterfly', anchor={'actor': 'pip', 'point': 'tip_antenna', 'dx': 2, 'dy': -3})
bf.key(0, 'attach', 1); bf.key(0, 'facing', -1, 'step')
bf.perch(0, T, 1.1)
for i, t0 in enumerate((.35, 1.05, 1.7)):                               # ah… ah… AH…
    k = i+1
    pip.to(t0, .3, 'out', head_rot=-5*k, lean=-2*k, bend=-3.5*k, face_y=-.2*k, torso_sy=1+.025*k, shoulder_l_dy=-2.5*k, shoulder_r_dy=-2.5*k,
           mouth_open=.25+.2*k, mouth_w=.42+.08*k, mouth_round=.75, smile=-.1*k, lid=.08*k, squint=.2*k, brow_rot=14+3*k, brow_y=.7+.15*k,
           hip_dy=-1*k)
    pip.to(t0+.38, .2, 'inout', head_rot=-5*k+3, torso_sy=1+.025*k-.015, mouth_open=.15+.15*k)
for i in range(5):
    pip.to(2.08+i*.08, .05, 'linear', overlap=0, head_dx=1.4 if i % 2 else -1.4, hip_dy=-3-.5*i, torso_sy=1.075+.006*i, shoulder_l_dy=-7.5-.5*i,
           shoulder_r_dy=-7.5-.5*i)
luma.react(.38, .85, -.8, head=.5, lean=3)                              # first "ah": she looks up at the antenna and leans in
luma.face(.5, 'curious', dur=.2)
luma.face(1.2, 'oops', dur=.2)
luma.to(1.2, .38, 'back', arm_l_x=72, arm_l_y=-4, arm_r_x=84, arm_r_y=-16, arm_l_bend=.5, arm_r_bend=.5, hand_l_rot=-50, hand_r_rot=-50, lean=4)
luma.set(1.25, hand_l='open', hand_r='open')
t = 1.6
i = 0
luma.to(1.5, .3, 'out', lean=7, head_dy=-2)                             # leans in toward him: urgency
while t < T-.4:                                                         # "no, no, no": wrist-led, head shakes, hands climb
    sg = 1 if i % 2 == 0 else -1
    luma.to(t, .11, 'sine', overlap=0, hand_l_rot=-26-4*i, hand_r_rot=-26-4*i, arm_l_x=77, arm_r_x=89, arm_l_y=-4-4*i, arm_r_y=-16-4*i,
            face_x=.2*sg, head_rot=3*sg)
    luma.to(t+.11, .11, 'sine', overlap=0, hand_l_rot=-66-4*i, hand_r_rot=-66-4*i, arm_l_x=67, arm_r_x=79)
    t += .22
    i += 1
luma.to(T-.3, .22, 'out', overlap=.5, lean=-3, squint=.55, face_x=-.2, head_rot=-3, arm_l_x=62, arm_l_y=2, arm_r_x=70, arm_r_y=-8)   # braces
pip.to(T-.3, .25, 'out', overlap=0, head_rot=-18, lean=-7, bend=-9, face_y=-.5, torso_sy=1.1, lid=.25)    # last inhale: chest up, head back
# the sneeze
pip.to(T-.04, .09, 'in', overlap=0, head_rot=20, lean=13, bend=15, face_y=.7, torso_sy=.88, torso_sx=1.08, hip_dy=9, hip_dx=6, squint=.3, lid=1.0,
       mouth_open=1.0, mouth_w=.95, mouth_round=.6, smile=-.7, brow_rot=-24, brow_y=-.6, shoulder_l_dy=4, shoulder_r_dy=4, head_dx=0,
       arm_l_x=-34, arm_l_y=46, arm_r_x=-22, arm_r_y=52)
pip.to(T+.12, .3, 'back', overlap=.6, head_rot=-6, lean=-4, bend=0, face_y=0, torso_sy=1.04, torso_sx=.98, hip_dy=0, hip_dx=0, mouth_open=.15, mouth_w=.6,
       shoulder_l_dy=0, shoulder_r_dy=0, arm_l_x=-5, arm_l_y=83, arm_r_x=5, arm_r_y=83)
s.puff_burst(T+.04, 838-98, GY-196*SC, direction=-1, count=3, spread=38, size=1.15)
bf.key(T, 'attach', 1); bf.key(T+.3, 'attach', 0, 'out')
bf.key(T+.05, 'x', 790); bf.key(T+.05, 'y', 388)
bf.path(T+.05, 6.4, [(790, 388), (730, 290), (640, 300), (590, 360), (665, 400), (700, 340), (640, 310), (606, 352)], flutter=6.5, seed=2.2)
bf.flap(T+.05, 6.4, rate=6)
# Pip: dizzy recovery, sheepish, then laughs
for i in range(3):
    pip.to(T+.5+i*.3, .15, 'sine', overlap=0, head_rot=7-2*i, face_x=.25)
    pip.to(T+.65+i*.3, .15, 'sine', overlap=0, head_rot=-6+2*i, face_x=-.25)
pip.to(T+1.4, .25, 'inout', head_rot=0, face_x=0, lean=0, torso_sy=1)
pip.to(T+.34, .22, 'out', squint=0, lid=0, brow_rot=16, brow_y=.75, smile=-.25, mouth_round=.2, mouth_open=.12, mouth_w=.6)
pip.look(T+.5, .1, .2, .1)
pip.track(bf, T+.75, T+1.2, 838, -1, head=.3)                         # eyes follow the butterfly out of his life
pip.blink(T+1.25, T+1.5)
pip.face(T+1.6, 'oops', dur=.2)
pip.to(T+1.7, .3, 'inout', head_rot=-6, lean=2, brow_y=.9)              # sheepish head tilt as she starts to laugh
pip.laugh(T+1.95, .65, beats=3, strength=.3)                            # a giggle catches in his shoulders before the big laugh
pip.look(T+1.62, .85, 0, .1)
pip.face(T+2.5, 'joy', dur=.2)
pip.laugh(T+2.55, 1.2, beats=5, strength=.7)
# Luma: flinch, then laughter
luma.to(T+.02, .1, 'out', overlap=.3, lean=-6, bend=-8, head_rot=-6, hip_dx=-6, torso_sy=1.05, arm_l_x=30, arm_l_y=-40, arm_r_x=44, arm_r_y=-46,
        squint=1, mouth_open=.2, mouth_w=.7)
luma.to(T+.5, .4, 'inout', lean=0, bend=0, head_rot=0, hip_dx=0, torso_sy=1, arm_l_x=-5, arm_l_y=83, arm_r_x=5, arm_r_y=83,
        hand_l_rot=0, hand_r_rot=0, arm_l_bend=1, arm_r_bend=-1, squint=0)
luma.set(T+.9, hand_l='closed', hand_r='closed')
luma.blink(T+.62)
luma.face(T+.7, 'awe', dur=.2)
luma.track(bf, T+.75, T+1.5, 612, 1)
luma.face(T+1.5, 'joy', dur=.16)
luma.look(T+1.5, .85, 0, .1, head=.3)
luma.to(T+1.55, .2, 'inout', face_x=.3, face_y=0, head_rot=0)
pip.face(T+2.1, 'happy', dur=.25)                                       # her laugh is catching
luma.laugh(T+1.6, 1.35, beats=7, strength=.9)
luma.to(T+1.7, .3, 'out', overlap=.3, bend=9, lean=6, arm_l_x=14, arm_l_y=48, arm_r_x=18, arm_r_y=-46, arm_r_bend=-.85)   # doubles over: hand on belly, wipes an eye
luma.to(T+2.55, .4, 'inout', overlap=.3, bend=0, lean=0, arm_l_x=-5, arm_l_y=83, arm_r_x=5, arm_r_y=83, arm_r_bend=-1)
luma.react(T+2.3, .85, 0, head=.4)                                      # looks at him as he starts laughing
luma.face(T+3.0, 'happy', dur=.25)
luma.track(bf, T+3.0, 6.4, 612, 1, head=.4)                             # then the butterfly pulls her eyes up: sets up s08

# ───────────────────────── s08 · close on Luma: now it's her turn ─────────────────────────
s = film.shot('s08', 4.4, 'valley', 'Primer plano de Luma. La mariposa se posa en su oreja; ella se queda quieta y sonríe.')
s.dof(6.5)
s.cam(0, 660, 528, 2.36).cam(4.4, 656, 520, 2.52, 'inout')
luma = s.actor('luma', x=612, y=GY, scale=SC)
luma.auto_blink(False)
for name, value in EXPRESSIONS['happy'].items():                        # the cut lands inside the laugh: smiling from frame 0, then it settles
    luma.key(0, name, value)
luma.key(0, 'smile', 1.1); luma.key(0, 'mouth_open', .7)
luma.to(.0, .5, 'out', overlap=0, mouth_open=.4, smile=1)
luma.laugh(.04, .55, beats=2, strength=.4)
bf = s.prop('butterfly', anchor={'actor': 'luma', 'point': 'tip_ear_r', 'dx': 0, 'dy': -2})
bf.path(0, 1.1, [(606, 352), (640, 372), (622, 400), (640, 415)], flutter=4.5, seed=6.3)
bf.flap(0, 1.05, rate=5.5)
bf.key(.75, 'attach', 0); bf.key(1.1, 'attach', 1, 'out')
bf.key(1.1, 'facing', 1, 'step')
bf.perch(1.1, 3.6, 1.3)
bf.key(4.0, 'attach', 1); bf.key(4.4, 'attach', 0, 'out')               # it lifts off at the end of the shot: s09 carries on
bf.key(4.06, 'x', 652); bf.key(4.06, 'y', 412)
bf.path(4.06, 5.0, [(652, 412), (690, 368), (724, 330)], flutter=3, seed=7.1)
bf.flap(3.9, 5.0, rate=7)
bf_exit = (bf.value('x', 4.4), bf.value('y', 4.4))
luma.track(bf, 0, .9, 612, 1, head=.4)
luma.pulse(1.08, .07, .02, .3, head_dy=2.2, head_rot=-2)
luma.look(1.1, .35, -1, .1, head=.3)
luma.face(1.2, 'still', dur=.14)
luma.to(1.06, .12, 'out', overlap=0, lean=-4, torso_sy=1.05)                # a breath in as it touches her
luma.to(1.2, .3, 'out', shoulder_l_dy=-8, shoulder_r_dy=-8, torso_sy=1.03, lean=-2, head_rot=-5, arm_l_x=-12, arm_r_x=12)   # frozen, head tilted away
luma.key(1.2, 'life', 1); luma.key(1.5, 'life', .2)
luma.look(2.2, .95, .05, .09)                                           # glance at Pip: "look!"
luma.to(2.3, .3, 'soft', smile=.8, mouth_w=.9, brow_rot=4, brow_y=.9, eye_open=1.1)
luma.look(3.0, .35, -1, .09)
luma.blink(3.4)
luma.laugh(2.55, .6, beats=2, strength=.2)                              # a suppressed giggle: the shoulders betray her
luma.face(3.5, 'soft', dur=.4)
luma.to(3.5, .5, 'inout', shoulder_l_dy=0, shoulder_r_dy=0, torso_sy=1, head_rot=0)
luma.face(3.95, 'awe', dur=.12)                                         # it stirs: she feels the wings lift
luma.track(bf, 4.05, 4.4, 612, 1, head=.5)

# ───────────────────────── s09 · farewell ─────────────────────────
s = film.shot('s09', 7.4, 'valley', 'General. La mariposa despega hacia el sol; Luma y Pip la despiden.')
s.dof([[0, 2.6], [3, 2.6], [6.5, 1.2, 'inout']])
s.cam(0, 716, 528, 1.62).cam(2.2, 716, 520, 1.6, 'inout').cam(6.6, 642, 378, 1.03, 'inout')
luma = s.actor('luma', x=612, y=GY, scale=SC, look_x=.35, look_y=-1)
pip = s.actor('pip', x=838, y=GY, scale=SC, facing=-1, look_x=.8, look_y=-.45)
luma.face(0, 'soft'); pip.face(0, 'happy')
bf = s.prop('butterfly', anchor={'actor': 'luma', 'point': 'tip_ear_r', 'dx': 0, 'dy': -2})
bf.key(0, 'attach', 0); bf.key(0, 'facing', 1, 'step')
bf.key(0, 'x', bf_exit[0]); bf.key(0, 'y', bf_exit[1])
bf.path(0, 7.0, [bf_exit, (700, 350), (760, 380), (800, 330), (735, 300), (770, 240), (850, 195), (SUN[0]-4, SUN[1]+14)],
        flutter=6, seed=7.7)
bf.flap(0, 7.2, rate=5.5)
bf.key(3.6, 'scale', 1); bf.key(7.0, 'scale', .32, 'in')
bf.key(6.2, 'opacity', 1); bf.key(7.0, 'opacity', 0, 'linear')
bf.key(3.2, 'shadow', 1); bf.key(4.2, 'shadow', 0, 'linear')
luma.face(.1, 'awe', dur=.2)
luma.track(bf, .1, 6.2, 612, 1)
pip.track(bf, .35, 3.7, 838, -1)
pip.track(bf, 3.85, 6.2, 838, 1)
pip.face(.6, 'awe', dur=.25)
luma.face(3.3, 'happy'); pip.face(3.6, 'happy')
land = luma.hop(3.5, height=20, air=.32)
luma.wave_off(land+.1, 'r', cycles=3, period=.36, out=86, up=-40)
pip.pulse(3.55, .1, .05, .3, hip_dy=4, head_dy=2)                       # her hop makes him bounce too
pip.turn_around(3.7, 1)
pip.wave_off(4.2, 'r', cycles=3, period=.34, out=86, up=-40)
luma.to(6.35, .4, 'inout', face_x=.3, face_y=0, head_rot=0)             # they look at each other
luma.look(6.3, .85, 0, .1)
pip.look(6.45, -.9, 0, .1)                                              # his eyes find her first...
pip.look(6.7, .85, 0, .1)
pip.turn_around(6.78, -1)                                               # ...then the body comes round
pip.to(7.02, .36, 'inout', face_x=.3, face_y=0, head_rot=0)
luma.face(6.4, 'soft'); pip.face(6.6, 'soft')
s.fade_out(1.0)

(root/'sets').mkdir(exist_ok=True)
(root/'sets/valley.json').write_text(json.dumps(valley(), ensure_ascii=False, indent=1), encoding='utf-8')
script = film.export(
    revision=0, story=STORY,
    style={'hold': 2, 'contour': .9, 'boil': .32, 'boil_hold': 3},   # drawn on twos, single outer line
    bible={
        'style': 'Cutout 2D con extremidades continuas, cara paramétrica, multiplano con profundidad de campo y luz de atardecer.',
        'story': STORY,
        'continuity': 'Luma a la izquierda mirando a la derecha; Pip a la derecha mirando a la izquierda. Suelo y=690, escala .66. Sin diálogo ni audio.',
    },
    characters={cid: f'characters/{cid}.json' for cid in rigs}, sets={'valley': 'sets/valley.json'})
# one scene (all the shots happen in the workshop); the cast keeps the values shared by every shot where the actor appears
script = group_scene(script, 'taller', 'valley', 'El taller al atardecer',
                     'Luma llega al taller de Pip; una mariposa se posa en la antena y luego en la oreja de Luma.')
script = save(root, json.loads(json.dumps(script)))     # validates, writes script.json and compiles film.json
target = root/'film.json'
compiled = json.loads(target.read_text(encoding='utf-8'))
total = sum(shot['duration'] for shot in compiled['shots'])
print(json.dumps({'script': str(root/'script.json'), 'film': str(target), 'shots': len(compiled['shots']), 'seconds': round(total, 3),
                  'kb': target.stat().st_size//1024}))
