import sys
sys.path.insert(0, '.')
import skia
from PIL import Image
from pathlib import Path
from celstudio.v2.stage import Stage
root = Path('projects/tres-osos')
tiles = []
for cid in ('osito', 'mama_osa', 'papa_oso'):
    for turn in (0, 1, 2):
        film = {'schema_version': 2, 'id': 't', 'title': 't', 'fps': 24, 'width': 700, 'height': 700, 'world': [700, 700],
                'characters': {cid: f'characters/{cid}.json'},
                'sets': {'flat': {'color': '#e9c48f', 'layers': [], 'post': False, 'light': {}}},
                'shots': [{'id': 'a', 'duration': 2, 'set': 'flat', 'camera': {'drift': [[0, 0]]}, 'actors': [
                    {'id': 'a', 'character': cid, 'auto_blink': False, 'channels': {'x': [[0, 350]], 'y': [[0, 690]], 'scale': [[0, 1.6]], 'life': [[0, 0]], 'turn': [[0, turn]],
                     'hip_dy': [[0, 0], [.2, 0], [.3, 30], [.45, 0], [.6, 10]], 'head_dy': [[0, 0], [.3, 14], [.45, -6], [.6, 0]], 'face_x': [[0, 0], [.5, .8]]}}]}]}
        stage = Stage(film, root, 700)
        tiles.append(Image.fromarray(stage.frame(film['shots'][0], .42).toarray()).convert('RGB').crop((50, 120, 650, 520)).resize((300, 200)))
out = Image.new('RGB', (900, 600))
for i, t in enumerate(tiles):
    out.paste(t, ((i % 3)*300, (i//3)*200))
out.save('work/osos/review/bears/ears.png')
