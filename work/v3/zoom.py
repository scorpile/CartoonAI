"""Review helper: 2x crop around an actor's upper body. usage: zoom.py name shot actor t"""
import sys, skia
sys.path.insert(0, '.')
from celstudio.v2.stage import Stage, load_film
name, sid, actor, t = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4])
film, root = load_film('projects/taller-v3/film.json')
st = Stage(film, root, 3840)
shot = next(s for s in film['shots'] if s['id'] == sid)
view = st.view(shot, t)
v = st.performers(shot)[actor].values(t)
sx, sy = view.to_screen(v['x'], v['y'])[:2]
k = view.scale(1.0)*v['scale']
src = skia.IRect.MakeLTRB(int(sx-40*k), int(sy-215*k), int(sx+190*k), int(sy-95*k))
st.frame(shot, t).makeSubset(src).save(f'work/v3/review/{name}.jpg', skia.kJPEG, 90)
