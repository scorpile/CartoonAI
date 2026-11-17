"""Review helper: upper-body close-ups at chosen moments. usage: hands.py name cell cols s04:luma:5.0 ..."""
import sys, skia
sys.path.insert(0, '.')
from celstudio.v2.stage import Stage, load_film
name, cell, cols, picks = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), [a.split(':') for a in sys.argv[4:]]
film, root = load_film('projects/taller-v3/film.json')
st = Stage(film, root, 1920)
rows = (len(picks)+cols-1)//cols
surf = skia.Surface(cols*cell, rows*cell)
c = surf.getCanvas()
for i, (sid, actor, t) in enumerate(picks):
    shot = next(s for s in film['shots'] if s['id'] == sid)
    t = min(shot['duration']-.001, float(t))
    view = st.view(shot, t)
    v = st.performers(shot)[actor].values(t)
    sx, sy = view.to_screen(v['x'], v['y'])[:2]
    k = view.scale(1.0)*v['scale']
    src = skia.Rect.MakeLTRB(sx-150*k, sy-250*k, sx+150*k, sy+50*k)
    c.drawImageRect(st.frame(shot, t), src, skia.Rect.MakeXYWH((i % cols)*cell, (i//cols)*cell, cell, cell), skia.SamplingOptions(skia.FilterMode.kLinear))
surf.makeImageSnapshot().save(f'work/v3/review/{name}.jpg', skia.kJPEG, 88)
