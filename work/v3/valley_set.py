"""Multiplane placement of the generated valley layers (world 1280x720). Pure data."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[2]/'projects/taller-v3'
GROUND_Y = 690.0
SUN = (936.0, 137.0)


def placed(box, upp, left, top):
    x0, y0, x1, y1 = box
    return {'x': left+(x0+x1)/2*upp, 'y': top+(y0+y1)/2*upp, 'w': (x1-x0)*upp}


def valley():
    measure = json.loads((root/'assets/set/set-measure.json').read_text(encoding='utf-8'))
    layers = [
        {'id': 'sky', 'image': 'assets/set/sky.png', 'depth': .03, 'x': 640, 'y': 360, 'w': 1340, 'blur': .5},
    ]
    sky_upp, sky_left, sky_top = 1340/1672, 640-670, 360-1340*941/1672/2
    for i, cloud in enumerate(measure['clouds']):
        item = placed(cloud['box'], sky_upp, sky_left, sky_top)
        layers.append({'id': f'cloud{i}', 'image': cloud['file'], 'depth': .07, **item, 'blur': .8,
                       'drift': {'vx': 5.5+1.7*i, 'wrap': [-420, 1700]}})
    layers += [
        {'id': 'far', 'image': 'assets/set/far.png', 'depth': .14, 'x': 640, 'y': 352, 'w': 1390, 'blur': 1.0},
        {'id': 'mid', 'image': 'assets/set/mid.png', 'depth': .38, 'x': 640, 'y': 372, 'w': 1420, 'blur': .75},
        {'id': 'main', 'image': 'assets/set/main.png', 'depth': 1.0, 'x': 600, 'y': 338, 'w': 1500, 'blur': .22},
    ]
    fg_upp, fg_left, fg_top = 1460/1672, 640-730, 372-1460*941/1672/2
    anchors = [(-.5, -.5), (-.5, .5), (.5, .5)]
    for i, part in enumerate(measure['fg']):
        item = placed(part['box'], fg_upp, fg_left, fg_top)
        item['y'] += 48 if i else -30      # keep the cut edges of the sprites outside every framing
        ax, ay = anchors[i]
        height = item['w']*(part['box'][3]-part['box'][1])/(part['box'][2]-part['box'][0])
        layers.append({'id': f'fg{i}', 'image': part['file'], 'depth': 1.75, **item, 'blur': 1.25, 'front': True,
                       'sway': {'deg': 1.3 if i else .8, 'period': 4.6+i*.9, 'phase': .21*i, 'anchor': [ax*item['w'], ay*height]}})
    return {
        'color': '#f3c98c', 'ground_y': GROUND_Y, 'layers': layers,
        'lights': [
            {'x': SUN[0], 'y': SUN[1], 'depth': .03, 'radius': 250, 'color': '#ffd27a', 'opacity': .15, 'pulse': .07, 'period': 5.5},
            {'x': 1015, 'y': 278, 'depth': 1.0, 'radius': 105, 'color': '#ffc866', 'opacity': .42, 'pulse': .12, 'period': 2.3, 'flicker': 3.1},
        ],
        'smoke': [{'x': 1163, 'y': 66, 'depth': 1.0, 'rate': .8, 'rise': 30, 'life': 5.0, 'size': 11, 'drift': -9, 'opacity': .8}],
        'particles': [
            {'kind': 'motes', 'count': 46, 'area': [-100, 150, 1400, 700], 'depth': 1.3, 'color': '#ffe2a8', 'size': 2.6, 'opacity': .5},
            {'kind': 'leaves', 'count': 2, 'area': [-100, -40, 1380, 700], 'depth': 1.2, 'opacity': .95, 'speed': .8},
        ],
        'rays': [{'x': SUN[0], 'y': SUN[1], 'depth': .1, 'count': 6, 'length': 880, 'spread_deg': 62, 'direction_deg': 128,
                  'color': '#ffe6ad', 'opacity': .085}],
        'light': {
            'ambient': {'color': '#ffc58a', 'amount': .11},
            'rim': {'dir': [.78, -.62], 'color': '#ffe2a6', 'opacity': .62, 'width': 3.0},
            'shade': {'dir': [-.75, .66], 'color': '#b094b8', 'opacity': .55, 'width': 5.5},
            'shadow': {'contact': {'width': 118, 'height': 20, 'opacity': .40, 'color': '#4a3020'},
                       'cast': {'shear': .62, 'squash': .30, 'opacity': .20, 'blur': 4.5, 'color': '#4a3020'}},
        },
        'post': {'bloom': {'threshold': .80, 'sigma': .012, 'strength': .16},
                 'grade': {'contrast': 1.05, 'saturation': 1.08, 'temperature': .015, 'lift': [0, 0, 0], 'gain': [1, 1, 1]},
                 'vignette': {'strength': .2, 'radius': .82}, 'grain': {'amount': .022}},
    }
