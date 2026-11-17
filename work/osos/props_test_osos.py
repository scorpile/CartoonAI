"""Bib (wear) in front / 3q / profile and fork in the grip paw."""
import sys
sys.path.insert(0, '.')
import skia
from PIL import Image
from pathlib import Path
from celstudio.v2.stage import Stage
from celstudio.v2.direct import EXPRESSIONS
root = Path('projects/tres-osos')
def K(**v): return {k: [[0, x]] for k, x in v.items()}
cases = [dict(turn=0, wear='babero'), dict(turn=1, wear='babero'), dict(turn=2, wear='babero'),
         dict(turn=1, item_l='tenedor', hand_l='grip', arm_l_x=62, arm_l_y=-30, arm_l_bend=.6, wear='babero'),
         dict(turn=0, item_l='tenedor', hand_l='grip', item_r='tenedor', hand_r='grip', arm_l_x=-50, arm_l_y=-70, arm_r_x=50, arm_r_y=-70, arm_l_bend=.8, arm_r_bend=.8, wear='babero', **EXPRESSIONS['happy'])]
for cid in ('osito', 'mama_osa', 'papa_oso'):
    actors = [{'id': f'a{i}', 'character': cid, 'auto_blink': False, 'channels': K(x=190+i*380, y=1000, scale=1.45, life=0, **c)} for i, c in enumerate(cases)]
    film = {'schema_version': 2, 'id': 't', 'title': 't', 'fps': 24, 'width': 1920, 'height': 1080, 'world': [1920, 1080],
            'characters': {cid: f'characters/{cid}.json'},
            'sets': {'flat': {'color': '#e9c48f', 'layers': [], 'post': False, 'light': {}}},
            'shots': [{'id': 'a', 'duration': 1, 'set': 'flat', 'camera': {'drift': [[0, 0]]}, 'actors': actors}]}
    stage = Stage(film, root, 1920)
    stage.frame(film['shots'][0], 0).save(f'work/osos/review/bears/props_{cid}.png', skia.kPNG)
    Image.open(f'work/osos/review/bears/props_{cid}.png').crop((0, 440, 1920, 1040)).save(f'work/osos/review/bears/props_{cid}_c.png')
