"""Variants of the raised fork: python work/osos/fork_test.py"""
import sys, skia
sys.path.insert(0, '.')
from pathlib import Path
from celstudio.v2.stage import Stage
root = Path('projects/tres-osos')
def K(**v): return {k: [[0, x]] for k, x in v.items()}
V = [dict(hand_l_rot=r, hand_r_rot=-r, arm_l_x=-44, arm_l_y=-66, arm_r_x=44, arm_r_y=-66) for r in (-60, -30, 0, 30, 60, 90)]
actors = []
for i, v in enumerate(V):
    actors.append({'id': f'p{i}', 'character': 'papa_oso', 'auto_blink': False,
                   'channels': K(x=140+i*200, y=380, scale=.6, life=0, facing=1, turn=0, hand_l='grip', hand_r='grip', item_l='tenedor', item_r='tenedor', arm_l_bend=.8, arm_r_bend=-.8, smile=1, **v)})
film = {'schema_version': 2, 'id': 't', 'title': 't', 'fps': 24, 'width': 1280, 'height': 720, 'world': [1280, 720],
        'characters': {'papa_oso': 'characters/papa_oso.json'},
        'sets': {'flat': {'color': '#e9c48f', 'layers': [], 'post': False}},
        'shots': [{'id': 'a', 'duration': 1, 'set': 'flat', 'camera': {'x': [[0, 640]], 'y': [[0, 360]], 'zoom': [[0, 1]]}, 'actors': actors}]}
Stage(film, root, 1280).frame(film['shots'][0], 0).save('work/osos/review/film/fork_test.png', skia.kPNG)
