"""Review helper: motion strips / key frames. usage: strip.py name shot t0 count [step] [cols] [width]"""
import sys, skia
sys.path.insert(0, '.')
from celstudio.v2.stage import Stage, load_film
name, sid, t0, n = sys.argv[1], sys.argv[2], float(sys.argv[3]), int(sys.argv[4])
step = float(sys.argv[5]) if len(sys.argv) > 5 else 1/12
cols = int(sys.argv[6]) if len(sys.argv) > 6 else 8
width = int(sys.argv[7]) if len(sys.argv) > 7 else 480
film, root = load_film('projects/taller-v3/film.json')
st = Stage(film, root, width)
shot = next(s for s in film['shots'] if s['id'] == sid)
h = st.height
rows = (n+cols-1)//cols
surf = skia.Surface(cols*width, rows*h)
c = surf.getCanvas()
for i in range(n):
    c.drawImage(st.frame(shot, min(shot['duration']-.001, t0+i*step)), (i % cols)*width, (i//cols)*h)
surf.makeImageSnapshot().save(f'work/v3/review/{name}.jpg', skia.kJPEG, 85)
