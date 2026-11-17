"""Review helper: chosen moments of several shots. usage: shots.py name width cols s04:5.0 s06:0.9 ..."""
import sys, skia
sys.path.insert(0, '.')
from celstudio.v2.stage import Stage, load_film
name, width, cols, picks = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), [a.split(':') for a in sys.argv[4:]]
film, root = load_film('projects/taller-v3/film.json')
st = Stage(film, root, width)
rows = (len(picks)+cols-1)//cols
surf = skia.Surface(cols*width, rows*st.height)
c = surf.getCanvas()
for i, (sid, t) in enumerate(picks):
    shot = next(s for s in film['shots'] if s['id'] == sid)
    c.drawImage(st.frame(shot, min(shot['duration']-.001, float(t))), (i % cols)*width, (i//cols)*st.height)
surf.makeImageSnapshot().save(f'work/v3/review/{name}.jpg', skia.kJPEG, 86)
