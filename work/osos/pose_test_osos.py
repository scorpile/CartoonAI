"""Pose contact sheets for the bears: python work/osos/pose_test_osos.py [out_prefix]"""
import sys, time
sys.path.insert(0, '.')
import skia
from pathlib import Path
from celstudio.v2.stage import Stage
from celstudio.v2.direct import EXPRESSIONS
root = Path('projects/tres-osos')
out = sys.argv[1] if len(sys.argv) > 1 else 'work/osos/review/bears/poses'
def K(**v): return {k: [[0, x]] for k, x in v.items()}
POSES = {
 'front': dict(turn=0), 'happy': dict(turn=0, **EXPRESSIONS['happy']), '3q': dict(turn=1), '3q_surprise': dict(turn=1, **EXPRESSIONS['surprise'], look_x=.6),
 'profile': dict(turn=2), 'profile_happy': dict(turn=2, **EXPRESSIONS['happy']),
 'arms_up': dict(turn=0, **EXPRESSIONS['joy'], arm_l_x=-40, arm_l_y=-60, arm_r_x=44, arm_r_y=-60, arm_r_z=2, hand_l='open', hand_r='open'),
 'point': dict(turn=1, arm_l_x=62, arm_l_y=-8, arm_l_bend=-.6, hand_l='point', **EXPRESSIONS['awe'], look_x=.8),
 'profile_point': dict(turn=2, arm_l_x=62, arm_l_y=-8, arm_l_bend=-.6, hand_l='point', **EXPRESSIONS['happy']),
 'walk': dict(turn=2, foot_l_x=24, foot_r_x=-24, foot_r_y=-10, foot_r_rot=20, hip_dy=3, lean=5, arm_l_x=-26, arm_r_x=28, head_rot=-3, **EXPRESSIONS['happy']),
 'grip_down': dict(turn=0, hand_l='grip', hand_r='grip', arm_l_x=-22, arm_r_x=22, arm_l_y=50, arm_r_y=50, **EXPRESSIONS['happy']),
 'grip_up': dict(turn=1, hand_l='grip', arm_l_x=38, arm_l_y=-48, arm_l_bend=.7, hand_l_rot=-90, **EXPRESSIONS['happy']),
}
names = list(POSES)
bears = ('osito', 'mama_osa', 'papa_oso')
cols = 6
for part in range(2):
    sub = names[part*6:(part+1)*6]
    actors = []
    for row, cid in enumerate(bears):
        for i, nm in enumerate(sub):
            actors.append({'id': f'{cid}{i}', 'character': cid, 'auto_blink': False,
                           'channels': K(x=150+i*300, y=330+row*350, scale=.6, life=0, facing=1, **POSES[nm])})
    film = {'schema_version': 2, 'id': 't', 'title': 't', 'fps': 24, 'width': 1920, 'height': 1080, 'world': [1920, 1080],
            'characters': {c: f'characters/{c}.json' for c in bears},
            'sets': {'flat': {'color': '#e9c48f', 'layers': [], 'post': False,
                              'light': {'rim': {'dir': [.78, -.62], 'color': '#ffe0a6', 'opacity': .55, 'width': 3.2},
                                        'shade': {'dir': [-.75, .66], 'color': '#b7a3c4', 'opacity': .55, 'width': 6.0},
                                        'shadow': {'contact': {'width': 118, 'height': 20, 'opacity': .3}, 'cast': {}}}}},
            'shots': [{'id': 'a', 'duration': 1, 'set': 'flat', 'camera': {'drift': [[0, 0]]}, 'actors': actors}]}
    stage = Stage(film, root, 1920)
    t = time.time()
    image = stage.frame(film['shots'][0], 0)
    image.save(f'{out}_{part+1}.png', skia.kPNG)
    print(part, sub, round(time.time()-t, 1), 's')
