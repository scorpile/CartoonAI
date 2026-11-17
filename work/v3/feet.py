"""Review helper: close-up strip of one actor's legs. usage: feet.py name shot actor t0 count [step] [cols] [cell]"""
import sys, skia
sys.path.insert(0, '.')
from celstudio.v2.stage import Stage, load_film
name, sid, actor, t0, n = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), int(sys.argv[5])
step = float(sys.argv[6]) if len(sys.argv) > 6 else 1/24
cols = int(sys.argv[7]) if len(sys.argv) > 7 else 8
cell = int(sys.argv[8]) if len(sys.argv) > 8 else 240
film, root = load_film('projects/taller-v3/film.json')
st = Stage(film, root, 1920)
shot = next(s for s in film['shots'] if s['id'] == sid)
rows = (n+cols-1)//cols
surf = skia.Surface(cols*cell, rows*cell)
c = surf.getCanvas()
for i in range(n):
    t = min(shot['duration']-.001, t0+i*step)
    view = st.view(shot, t)
    v = st.performers(shot)[actor].values(t)
    sx, sy = view.to_screen(v['x'], v['y'])[:2]
    half = 105*view.scale(1.0)*v['scale']
    src = skia.Rect.MakeLTRB(sx-half, sy-half*1.55, sx+half, sy+half*.45)
    dst = skia.Rect.MakeXYWH((i % cols)*cell, (i//cols)*cell, cell, cell)
    c.drawImageRect(st.frame(shot, t), src, dst, skia.SamplingOptions(skia.FilterMode.kLinear))
surf.makeImageSnapshot().save(f'work/v3/review/{name}.jpg', skia.kJPEG, 88)
