"""Review helper: chosen moments. usage: shots_osos.py name width cols s01:1.0 s02:2.5 ...  (-> work/osos/review/film/name.jpg)
or strips: shots_osos.py name width cols strip:s02:t0:count:step"""
import sys, skia
sys.path.insert(0, '.')
from celstudio.v2.stage import Stage, load_film
name, width, cols, args = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4:]
picks = []
for a in args:
    p = a.split(':')
    if p[0] == 'strip':
        sid, t0, n, step = p[1], float(p[2]), int(p[3]), float(p[4])
        picks += [(sid, t0+i*step) for i in range(n)]
    else:
        picks.append((p[0], float(p[1])))
film, root = load_film('projects/tres-osos/film.json')
st = Stage(film, root, width)
rows = (len(picks)+cols-1)//cols
surf = skia.Surface(cols*width, rows*st.height)
c = surf.getCanvas()
font = skia.Font(skia.Typeface('Arial'), 16)
paint = skia.Paint(Color=skia.ColorWHITE)
for i, (sid, t) in enumerate(picks):
    shot = next(s for s in film['shots'] if s['id'] == sid)
    tt = min(shot['duration']-.001, t)
    x, y = (i % cols)*width, (i//cols)*st.height
    c.drawImage(st.frame(shot, tt), x, y)
    c.drawString(f'{sid} {tt:.2f}', x+6, y+18, font, paint)
surf.makeImageSnapshot().save(f'work/osos/review/film/{name}.jpg', skia.kJPEG, 85)
