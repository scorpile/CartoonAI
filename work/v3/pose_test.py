"""Quick visual test of rigs: grid of poses on a flat backdrop."""
import sys, json, time
sys.path.insert(0, '.'); sys.path.insert(0, 'work/v3')
import skia
from pathlib import Path
from celstudio.v2.stage import Stage
from celstudio.v2.direct import EXPRESSIONS
root = Path('projects/taller-v3')
out = sys.argv[1]
def K(**v): return {k: [[0, x]] for k, x in v.items()}
poses = [
    dict(turn=0), dict(turn=1), dict(turn=1, **EXPRESSIONS['happy'], arm_l_x=-36, arm_l_y=-62, arm_l_bend=.9, hand_l='open', hand_l_rot=-20),
    dict(turn=1, **EXPRESSIONS['surprise'], hip_dy=-2, torso_sy=1.05, arm_l_x=-30, arm_l_y=40, arm_r_x=34, arm_r_y=30, look_x=.6),
    dict(turn=1, **EXPRESSIONS['joy'], lean=-6, head_rot=-8), dict(turn=1, hip_dy=22, lean=12, **EXPRESSIONS['focus'], look_x=.7, look_y=.5),
    dict(turn=1, **EXPRESSIONS['still'], look_y=-1, look_x=.2, arm_l_x=-14, arm_r_x=14), dict(turn=1, arm_l_x=60, arm_l_y=-10, arm_l_bend=-.6, hand_l='point', **EXPRESSIONS['awe'], look_x=.8, look_y=-.4),
    dict(turn=0, **EXPRESSIONS['smug']), dict(turn=1, lid=.5, **{k:v for k,v in EXPRESSIONS['worried'].items() if k!='lid'}),
    dict(turn=1, foot_l_x=18, foot_r_x=-26, foot_r_y=-10, foot_r_rot=20, hip_dy=3, lean=5, arm_l_x=-22, arm_r_x=24),
    dict(turn=1, lift=30, foot_l_rot=22, foot_r_rot=22, torso_sy=1.07, **EXPRESSIONS['happy'], arm_l_x=-40, arm_l_y=-40, arm_r_x=44, arm_r_y=-44, arm_r_z=2, arm_r_bend=.9, hand_l='open', hand_r='open'),
]
actors = []
for row, cid in enumerate(('luma', 'pip')):
    for i, pose in enumerate(poses):
        actors.append({'id': f'{cid}{i}', 'character': cid, 'auto_blink': False,
                       'channels': K(x=110+i*203, y=330+row*340, scale=.9, life=0, facing=1 if row == 0 else -1, **pose)})
film = {'schema_version': 2, 'id': 't', 'title': 't', 'fps': 24, 'width': 2560, 'height': 720*2560//1280*1, 'world': [2560, 720],
        'characters': {'luma': 'characters/luma.json', 'pip': 'characters/pip.json'},
        'sets': {'flat': {'color': '#e9c48f', 'layers': [], 'post': False,
                          'light': {'rim': {'dir': [.78, -.62], 'color': '#ffe0a6', 'opacity': .55, 'width': 3.2},
                                    'shade': {'dir': [-.75, .66], 'color': '#b7a3c4', 'opacity': .55, 'width': 6.0},
                                    'shadow': {'contact': {'width': 118, 'height': 20, 'opacity': .3}, 'cast': {}}}}},
        'shots': [{'id': 'a', 'duration': 1, 'set': 'flat', 'camera': {'drift': [[0, 0]]}, 'actors': actors}]}
stage = Stage(film, root, 2560)
t = time.time()
image = stage.frame(film['shots'][0], 0)
print('ms', round((time.time()-t)*1000))
image.save(out, skia.kJPEG, 90)
