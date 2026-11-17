"""Render test poses of Ricitos with the real engine and save contact sheets in work/osos/review/ricitos/.
usage: python work/osos/pose_ricitos.py <sheet-name> [character]
Sheets: lying (asleep / breathing extremes / eye / hands), close (zoom 2.5), upright (debug)
"""
import sys
import time
from pathlib import Path
import skia
from PIL import Image
sys.path.insert(0, '.')
from celstudio.v2.stage import Stage

root = Path('projects/tres-osos')
OUT = Path('work/osos/review/ricitos')
OUT.mkdir(parents=True, exist_ok=True)
W, H = 1280, 720


def K(**v):
    return {k: [[0, x]] for k, x in v.items()}


def mock_bed():
    """A flat mock pillow + blanket only for judging (no art): drawn by the test, not part of the deliverable."""
    return None


def frame(pose, t=0.0, zoom=1.0, cam=(430, 330), character='ricitos', width=1280, x=470, y=400, drift=False, extra_actors=None):
    film = {'schema_version': 2, 'id': 't', 'title': 't', 'fps': 24, 'width': width, 'height': width*9//16, 'world': [W, H],
            'characters': {character: f'characters/{character}.json'},
            'sets': {'flat': {'color': '#c9a97c', 'layers': [], 'post': False,
                              'light': {'rim': {'dir': [.78, -.62], 'color': '#ffe0a6', 'opacity': .35, 'width': 3.2},
                                        'shade': {'dir': [-.75, .66], 'color': '#b7a3c4', 'opacity': .35, 'width': 6.0}}}},
            'shots': [{'id': 'a', 'duration': 8, 'set': 'flat', 'camera': {'x': [[0, cam[0]]], 'y': [[0, cam[1]]], 'zoom': [[0, zoom]], 'drift': [[0, 0]]},
                       'actors': [{'id': 'r', 'character': character, 'auto_blink': False, 'channels': {**K(x=x, y=y), **{k: (v if isinstance(v, list) else [[0, v]]) for k, v in pose.items()}}}]}]}
    stage = Stage(film, root, width)
    return stage.frame(film['shots'][0], t)


def sheet(cells, name, cols=3, scale=.5):
    imgs = []
    for label, image in cells:
        arr = image.toarray(colorType=skia.kRGBA_8888_ColorType)
        imgs.append(Image.fromarray(arr).convert('RGB'))
    w, h = imgs[0].size
    w2, h2 = int(w*scale), int(h*scale)
    rows = (len(imgs)+cols-1)//cols
    out = Image.new('RGB', (w2*cols, h2*rows), 'white')
    from PIL import ImageDraw
    for i, im in enumerate(imgs):
        out.paste(im.resize((w2, h2), Image.LANCZOS), ((i % cols)*w2, (i//cols)*h2))
        ImageDraw.Draw(out).text(((i % cols)*w2+6, (i//cols)*h2+4), cells[i][0], fill=(0, 0, 0))
    out.save(OUT/f'{name}.png')
    print('saved', OUT/f'{name}.png', out.size)


if __name__ == '__main__':
    name = sys.argv[1]
    character = sys.argv[2] if len(sys.argv) > 2 else 'ricitos'
    t0 = time.time()
    if name == 'upright':
        cells = [('front rot0', frame(dict(rot=0, head_rot=0, life=0, turn=0), character=character, y=560, cam=(470, 480), zoom=2.4)),
                 ('3q rot0', frame(dict(rot=0, head_rot=0, life=0, turn=1), character=character, y=560, cam=(470, 480), zoom=2.4)),
                 ('open eyes smile', frame(dict(rot=0, head_rot=0, life=0, lid=0, smile=1, hand_l='open', arm_l_x=-40, arm_l_y=20), character=character, y=560, cam=(470, 480), zoom=2.4))]
        cells = [(l, im) for l, im in cells]
        sheet(cells, 'upright_'+character)
    if name == 'lying':
        cam = dict(cam=(330, 360), zoom=2.0, y=420, x=470)
        cells = [('asleep 3q', frame(dict(turn=1), character=character, **cam)),
                 ('asleep front', frame(dict(turn=0, head_rot=60), character=character, **cam)),
                 ('t=.78', frame(dict(turn=1), t=.78, character=character, **cam)),
                 ('t=1.55', frame(dict(turn=1), t=1.55, character=character, **cam)),
                 ('hands chest', frame(dict(turn=1, arm_l_x=-14, arm_l_y=24, arm_r_x=14, arm_r_y=26, hand_l='curled', hand_r='closed'), character=character, **cam)),
                 ('hand under cheek', frame(dict(turn=1, arm_l_x=-30, arm_l_y=-40, arm_l_bend=.9, hand_l='open', arm_r_x=10, arm_r_y=40), character=character, **cam))]
        sheet(cells, 'lying_'+character, cols=3, scale=.5)
    print('s', round(time.time()-t0, 1))
