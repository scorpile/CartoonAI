"""Split generated set layers into sprites (connected components) and measure landmarks. Texture import only."""
from pathlib import Path
import json
import numpy as np
from PIL import Image
from scipy import ndimage

root = Path(__file__).resolve().parents[2]/'projects/taller-v3/assets'
out = root/'set/parts'
out.mkdir(parents=True, exist_ok=True)
info = {}


def components(name, minimum=4000, merge=18):
    image = Image.open(root/f'set/{name}.png').convert('RGBA')
    alpha = np.array(image)[..., 3] > 24
    grown = ndimage.binary_dilation(alpha, iterations=merge)
    labels, count = ndimage.label(grown)
    items = []
    for index, box in enumerate(ndimage.find_objects(labels), 1):
        mask = (labels[box] == index) & alpha[box]
        if mask.sum() < minimum:
            continue
        y, x = box
        pad = 4
        x0, y0, x1, y1 = max(0, x.start-pad), max(0, y.start-pad), min(image.width, x.stop+pad), min(image.height, y.stop+pad)
        crop = np.array(image.crop((x0, y0, x1, y1)))
        keep = ndimage.binary_dilation(labels[y0:y1, x0:x1] == index, iterations=2)
        crop[~keep] = 0
        items.append(((x0, y0, x1, y1), Image.fromarray(crop)))
    items.sort(key=lambda item: item[0][0])
    result = []
    for i, (box, sprite) in enumerate(items):
        filename = f'{name}-{i}.png'
        sprite.save(out/filename)
        result.append({'file': f'assets/set/parts/{filename}', 'box': box})
    return result


info['clouds'] = components('clouds')
info['fg'] = components('fg')
main = np.array(Image.open(root/'set/main.png').convert('RGBA'))
alpha = main[..., 3] > 128
rows = alpha.mean(axis=1)
info['main'] = {'size': [main.shape[1], main.shape[0]],
                'ground_top_left': int(np.argmax(alpha[:, 60])), 'ground_top_mid': int(np.argmax(alpha[:, main.shape[1]//3])),
                'house_bbox_cols': [int(np.argmax(alpha[:int(main.shape[0]*.6)].any(axis=0))), int(main.shape[1]-np.argmax(alpha[:int(main.shape[0]*.6)].any(axis=0)[::-1]))],
                'house_top': int(np.argmax(alpha.any(axis=1)))}
sky = np.array(Image.open(root/'set/sky.png').convert('RGB')).astype(float)
bright = sky.sum(axis=2)
ys, xs = np.where(bright > np.percentile(bright, 99.3))
info['sun'] = {'c': [float(xs.mean()), float(ys.mean())], 'r': float((xs.max()-xs.min()+ys.max()-ys.min())/4)}
for name in ('far', 'mid'):
    a = np.array(Image.open(root/f'set/{name}.png').convert('RGBA'))[..., 3] > 128
    info[name] = {'top': int(np.argmax(a.any(axis=1))), 'top_left': int(np.argmax(a[:, 40])), 'top_right': int(np.argmax(a[:, -40]))}
# butterfly + puff cells
for name in ('butterfly-sheet', 'puff-sheet'):
    image = Image.open(root/f'props/{name}.png').convert('RGBA')
    a = np.array(image)[..., 3] > 24
    labels, count = ndimage.label(ndimage.binary_dilation(a, iterations=10))
    boxes = []
    for index, box in enumerate(ndimage.find_objects(labels), 1):
        if ((labels[box] == index) & a[box]).sum() > 2500:
            y, x = box
            boxes.append([x.start, y.start, x.stop, y.stop])
    boxes.sort()
    info[name] = boxes
(root/'set/set-measure.json').write_text(json.dumps(info, indent=1), encoding='utf-8')
print(json.dumps(info))
