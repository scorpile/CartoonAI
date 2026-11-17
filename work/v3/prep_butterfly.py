"""Corta work/v3/art/fx/butterfly-poses.png (abierta, media, cerrada de canto, posada) en cuatro celdas iguales de
assets/props/butterfly-poses-sheet.png con el tórax en el mismo punto de cada celda (el pivote del prop es global).
Determinista. Uso: python work/v3/prep_butterfly.py"""
import os
from PIL import Image
ROOT = os.path.join(os.path.dirname(__file__), '..', '..')
SRC = os.path.join(ROOT, 'work', 'v3', 'art', 'fx', 'butterfly-poses.png')
OUT = os.path.join(ROOT, 'projects', 'taller-v3', 'assets', 'props', 'butterfly-poses-sheet.png')
CELL, PIVOT = 640, (330, 330)
# centro del torax en la hoja generada, y ventana de recorte (x0, x1) que contiene solo ese dibujo
THORAX = [(294, 384), (924, 425), (1401, 430), (1935, 430)]
SPANS = [(0, 560), (680, 1130), (1280, 1620), (1690, 2172)]
im = Image.open(SRC).convert('RGBA')
sheet = Image.new('RGBA', (CELL * 4, CELL), (0, 0, 0, 0))
for i, ((tx, ty), (a, b)) in enumerate(zip(THORAX, SPANS)):
    part = Image.new('RGBA', im.size, (0, 0, 0, 0))
    part.paste(im.crop((a, 0, b, im.height)), (a, 0))
    ox, oy = i * CELL + PIVOT[0] - tx, PIVOT[1] - ty
    sheet.alpha_composite(part, (max(0, ox), max(0, oy)), (max(0, -ox), max(0, -oy)))
sheet.save(OUT)
print([[i * CELL, 0, (i + 1) * CELL, CELL] for i in range(4)], list(PIVOT))
