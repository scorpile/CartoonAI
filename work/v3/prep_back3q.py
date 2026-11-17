"""Corta y mide la vista tres cuartos de espaldas (cabeza y torso) de work/v3/art/fx/<id>-back3q.png.

Escribe assets/<id>/head_back3q.png, torso_back3q.png y añade las claves `head_back3q` y `torso_back3q` a
assets/<id>/rig.json (no toca nada más). Determinista. Uso: python work/v3/prep_back3q.py
"""
import json, os, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import prep_parts as pp
import prep_profile as pr

ART = os.path.join(pp.ROOT, 'work', 'v3', 'art', 'fx')
PAD = pp.PAD


def process_head(cid, cell, m, od):
    cell = pr.recolor(cell, cid)
    a = cell[..., 3]
    sp, (ox, oy) = pp.save_crop(cell, os.path.join(od, 'head_back3q.png'))
    sk, apps = pp.appendages(a, cid)
    neck = pp.neck_point(a, sk)
    h3 = m['heads']['3q']
    k = (h3['skull_bbox'][3] - h3['skull_bbox'][1]) / (sk[3] - sk[1] + 1)
    P = lambda p: [p[0] - ox + .5, p[1] - oy + .5]
    skull = [sk[0] - ox, sk[1] - oy, sk[2] - ox + 1, sk[3] - oy + 1]
    cx, cy = (skull[0] + skull[2]) / 2, (skull[1] + skull[3]) / 2
    w, h = skull[2] - skull[0], skull[3] - skull[1]
    return dict(file='head_back3q.png', size=[sp.shape[1], sp.shape[0]], neck=pp.R(P(neck)), skull_bbox=pp.R(skull),
                face_bbox=pp.R([cx - .25 * w, cy - .2 * h, cx + .25 * w, cy + .2 * h]),     # nominal: a back view draws no face
                appendages=[dict(name=ap['name'], base=pp.R(P(ap['base'])), tip=pp.R(P(ap['tip']))) for ap in apps],
                upp_over_3q=pp.R(k, 4))


def process_torso(cid, cell, m, od):
    cell = pr.recolor(cell, cid)
    sp, _ = pp.save_crop(cell, os.path.join(od, 'torso_back3q.png'))
    a = sp[..., 3] > 128
    H, W = a.shape
    x0, y0, x1, y1 = pp.bbox_of(a)
    k = (m['torso']['size'][1] - 2 * PAD) / (y1 - y0 + 1)
    xs_b = np.where(a[y1 - 6])[0]
    waist = [(xs_b.min() + xs_b.max() + 1) / 2, y1 + 1.0]
    ny = y0 + .09 * (y1 - y0)
    xs_t = np.where(a[int(ny)])[0]
    neck = [(xs_t.min() + xs_t.max() + 1) / 2, ny]
    sy = int(y0 + .30 * (y1 - y0))
    xs_s = np.where(a[sy])[0]
    shoulder = [(xs_s.min() + xs_s.max() + 1) / 2, float(sy)]
    return dict(file='torso_back3q.png', size=[W, H], neck=pp.R(neck), shoulder=pp.R(shoulder), waist=pp.R(waist),
                upp_over_front=pp.R(k, 4))


def main():
    for cid in ('luma', 'pip'):
        od = os.path.join(pp.OUT, cid)
        path = os.path.join(od, 'rig.json')
        m = json.load(open(path, encoding='utf-8'))
        arr = np.array(Image.open(os.path.join(ART, f'{cid}-back3q.png')).convert('RGBA'))
        hc, tc = pr.split_sheet(arr)
        m['head_back3q'] = process_head(cid, hc, m, od)
        m['torso_back3q'] = process_torso(cid, tc, m, od)
        json.dump(m, open(path, 'w', encoding='utf-8'), indent=1)
        print(cid, m['head_back3q'], m['torso_back3q'])


if __name__ == '__main__':
    main()
