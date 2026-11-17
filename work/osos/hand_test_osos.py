"""Close-ups: each bear, arm reaching forward in 3q, one hand pose per figure (closed, open, point, grip)."""
import sys
sys.path.insert(0, '.')
import skia
from pathlib import Path
from celstudio.v2.stage import Stage
from celstudio.v2.direct import EXPRESSIONS
root = Path('projects/tres-osos')
def K(**v): return {k: [[0, x]] for k, x in v.items()}
for cid in ('osito', 'mama_osa', 'papa_oso'):
    actors = []
    for i, (hand, extra) in enumerate((('closed', {}), ('open', {}), ('point', {}), ('grip', {}))):
        actors.append({'id': f'a{i}', 'character': cid, 'auto_blink': False,
                       'channels': K(x=250+i*480, y=1000, scale=1.5, life=0, turn=1, hand_l=hand, hand_r=hand, arm_l_x=70, arm_l_y=-12, arm_l_bend=.5,
                                     arm_r_x=-14, arm_r_y=60, **EXPRESSIONS['happy'])})
    film = {'schema_version': 2, 'id': 't', 'title': 't', 'fps': 24, 'width': 1920, 'height': 1080, 'world': [1920, 1080],
            'characters': {cid: f'characters/{cid}.json'},
            'sets': {'flat': {'color': '#e9c48f', 'layers': [], 'post': False, 'light': {}}},
            'shots': [{'id': 'a', 'duration': 1, 'set': 'flat', 'camera': {'drift': [[0, 0]]}, 'actors': actors}]}
    stage = Stage(film, root, 1920)
    stage.frame(film['shots'][0], 0).save(f'work/osos/review/bears/hands_{cid}.png', skia.kPNG)
