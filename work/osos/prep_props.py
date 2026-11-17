"""Cut the Codex prop sheets into trimmed sprites, repack into equal cells with a shared pivot and write work/osos/props.json.
Texture import only (no drawing)."""
import json
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT/'work/osos/art/props'
OUT = ROOT/'projects/tres-osos/assets/props'


def sprites(path, count, minimum=6000):
    image = Image.open(path).convert('RGBA')
    arr = np.array(image)
    arr[arr[..., 3] < 40] = 0
    alpha = arr[..., 3] > 0
    grown = ndimage.binary_dilation(alpha, iterations=14)
    labels, n = ndimage.label(grown)
    items = []
    for i, box in enumerate(ndimage.find_objects(labels), 1):
        keep = (labels[box] == i) & alpha[box]
        if keep.sum() < minimum:
            continue
        crop = arr[box].copy()
        crop[~ndimage.binary_dilation(labels[box] == i, iterations=1) | (crop[..., 3] == 0)] = 0
        a = crop[..., 3] > 0
        ys, xs = np.where(a)
        crop = crop[ys.min():ys.max()+1, xs.min():xs.max()+1]
        items.append((box[1].start, Image.fromarray(crop)))
    items.sort(key=lambda t: t[0])
    assert len(items) == count, (path, len(items))
    return [s for _, s in items]


def pack(images, anchors, cell):
    """Put each image into a cell of size `cell` so that its anchor lands on the common pivot. Returns sheet, pivot."""
    ax = max(a[0] for a in anchors)
    ay = max(a[1] for a in anchors)
    right = max(im.width-a[0] for im, a in zip(images, anchors))
    below = max(im.height-a[1] for im, a in zip(images, anchors))
    cw, ch = int(ax+right+20), int(ay+below+20)
    pivot = (int(ax+10), int(ay+10))
    sheet = Image.new('RGBA', (cw*len(images), ch), (0, 0, 0, 0))
    cells = []
    for i, (im, a) in enumerate(zip(images, anchors)):
        sheet.paste(im, (i*cw+pivot[0]-int(a[0]), pivot[1]-int(a[1])), im)
        cells.append([i*cw, 0, (i+1)*cw, ch])
    return sheet, pivot, cells


def top_anchor(im, drop=0):
    a = np.array(im)[..., 3] > 0
    rows = np.where(a.any(axis=1))[0]
    top = rows[0]
    xs = np.where(a[top:top+8].any(axis=0))[0]
    return ((xs.min()+xs.max())/2, top+drop)


def handle_anchor(im):
    """Centre of the wooden handle (tan fill): where a fist grips the fork."""
    arr = np.array(im).astype(int)
    r, g, b, al = arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3]
    tan = (al > 200) & (r > 170) & (r < 235) & (g > 110) & (g < 170) & (b > 50) & (b < 110)
    ys, xs = np.where(tan)
    return (float(xs.mean()), float(ys.mean())), int(tan.sum())


def main():
    meta = {}
    # ---- babero ----
    d = OUT/'babero'
    d.mkdir(parents=True, exist_ok=True)
    bibs = sprites(ART/'babero-sheet.png', 4)
    names = ['babero_mano', 'babero_puesto', 'babero_perfil', 'babero_3q']
    drops = [40, 0, 0, 0]
    anchors = []
    for im, n, dp in zip(bibs, names, drops):
        im.save(d/f'{n}.png')
        anchors.append(top_anchor(im, dp))
    sheet, pivot, cells = pack(bibs, anchors, None)
    sheet.save(d/'babero-sheet.png')
    meta['babero'] = {'files': {n: {'file': f'assets/props/babero/{n}.png', 'size': list(im.size),
                                    'pivot': [round(a[0]), round(a[1])]} for n, im, a in zip(names, bibs, anchors)},
                      'sheet': 'assets/props/babero/babero-sheet.png', 'cells': cells, 'pivot': list(pivot)}
    # ---- tenedor ----
    d = OUT/'tenedor'
    d.mkdir(parents=True, exist_ok=True)
    forks = sprites(ART/'tenedor-sheet.png', 2)
    anchors, counts = [], []
    for im in forks:
        a, c = handle_anchor(im)
        anchors.append(a)
        counts.append(c)
    forks[0].save(d/'tenedor.png')
    forks[1].save(d/'tenedor_inclinado.png')
    sheet, pivot, cells = pack(forks, anchors, None)
    sheet.save(d/'tenedor-sheet.png')
    meta['tenedor'] = {'files': {'tenedor': {'file': 'assets/props/tenedor/tenedor.png', 'size': list(forks[0].size),
                                             'pivot': [round(anchors[0][0]), round(anchors[0][1])]},
                                 'tenedor_inclinado': {'file': 'assets/props/tenedor/tenedor_inclinado.png', 'size': list(forks[1].size),
                                                       'pivot': [round(anchors[1][0]), round(anchors[1][1])]}},
                       'sheet': 'assets/props/tenedor/tenedor-sheet.png', 'cells': cells, 'pivot': list(pivot),
                       'handle_pixels': counts}
    # ---- library entries in the format of the taller script ----
    meta['library'] = {
        'babero': {'sheet': meta['babero']['sheet'], 'cells': meta['babero']['cells'], 'pivot': meta['babero']['pivot'],
                   'upp': 0.12, 'layer': 'front',
                   'frames': {'mano': 0, 'puesto': 1, 'perfil': 2, 'tres_cuartos': 3}},
        'tenedor': {'sheet': meta['tenedor']['sheet'], 'cells': meta['tenedor']['cells'], 'pivot': meta['tenedor']['pivot'],
                    'upp': 0.085, 'layer': 'front', 'frames': {'vertical': 0, 'inclinado': 1}},
    }
    meta['notes'] = ('pivot de hoja: babero = borde del cuello (arriba, centro; en la celda 0 el nudo de las cintas); '
                     'tenedor = centro del mango donde cierra el puno. upp orientativo (unidades de mundo por pixel), a ajustar en plano. '
                     'Archivos sueltos para items/wear del rig: pivot en pixeles del PNG recortado.')
    (ROOT/'work/osos/props.json').write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(meta, indent=1)[:2500])


main()
