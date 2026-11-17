"""Rendered height (ground to top of head incl. ears/cap) and width of each bear, front view, at scale 1."""
import sys
sys.path.insert(0, '.')
import numpy as np, skia
from pathlib import Path
from celstudio.v2.stage import Stage
root = Path('projects/tres-osos')
res = {}
for cid in ('osito', 'mama_osa', 'papa_oso'):
    for turn in (0, 2):
        film = {'schema_version': 2, 'id': 't', 'title': 't', 'fps': 24, 'width': 1000, 'height': 1000, 'world': [1000, 1000],
                'characters': {cid: f'characters/{cid}.json'},
                'sets': {'flat': {'color': '#00ff00', 'layers': [], 'post': False, 'light': {}}},
                'shots': [{'id': 'a', 'duration': 1, 'set': 'flat', 'camera': {'drift': [[0, 0]]},
                           'actors': [{'id': 'a', 'character': cid, 'auto_blink': False,
                                       'channels': {'x': [[0, 500]], 'y': [[0, 900]], 'scale': [[0, 1]], 'life': [[0, 0]], 'turn': [[0, turn]]}}]}]}
        stage = Stage(film, root, 1000)
        img = stage.frame(film['shots'][0], 0)
        arr = img.toarray()[..., :3]
        mask = (np.abs(arr[..., 0].astype(int)-0) > 30) | (np.abs(arr[..., 1].astype(int)-255) > 30) | (np.abs(arr[..., 2].astype(int)-0) > 30)
        ys, xs = np.where(mask)
        print(cid, 'turn', turn, 'height', 900-ys.min(), 'width', xs.max()-xs.min())
