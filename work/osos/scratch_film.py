"""Scratch film to check the tres-osos sets with a taller character (Pip). Not the real film.
Usage: python work/osos/scratch_film.py   -> work/osos/scratch/film.json (sets synced from projects/tres-osos)."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SC = Path(__file__).resolve().parent/'scratch'
TRES = ROOT/'projects/tres-osos'
TALLER = ROOT/'projects/taller-v3'


def sync():
    SC.mkdir(exist_ok=True)
    for sub in ('assets/pip',):
        if not (SC/sub).exists():
            shutil.copytree(TALLER/sub, SC/sub)
    (SC/'characters').mkdir(exist_ok=True)
    shutil.copy(TALLER/'characters/pip.json', SC/'characters/pip.json')
    for sub in ('assets/sets', 'assets/props'):
        if (SC/sub).exists():
            shutil.rmtree(SC/sub)
        shutil.copytree(TRES/sub, SC/sub)


def actor(aid, x, y, scale, facing=1, extra=None):
    ch = {'x': [[0, x, 'smooth']], 'y': [[0, y, 'smooth']], 'scale': [[0, scale, 'smooth']], 'facing': [[0, facing, 'smooth']]}
    for k, v in (extra or {}).items():
        ch[k] = [[0, v, 'smooth']]
    return {'id': aid, 'character': 'pip', 'channels': ch}


def build(shots):
    sync()
    sets = {n: json.loads((TRES/f'sets/{n}.json').read_text(encoding='utf-8')) for n in ('bosque', 'dormitorio') if (TRES/f'sets/{n}.json').exists()}
    film = {'schema_version': 2, 'id': 'osos-scratch', 'title': 'scratch', 'fps': 24, 'width': 1920, 'height': 1080,
            'world': [1280, 720], 'characters': {'pip': 'characters/pip.json'}, 'sets': sets,
            'style': {'hold': 1, 'contour': 0.9, 'boil': 0, 'boil_hold': 3}, 'bible': {}, 'shots': shots}
    (SC/'film.json').write_text(json.dumps(film, indent=1), encoding='utf-8')


def shot(sid, set_, actors, cam=(640, 360, 1.0), dur=2.0):
    x, y, z = cam
    return {'id': sid, 'duration': dur, 'set': set_, 'camera': {'x': [[0, x, 'smooth']], 'y': [[0, y, 'smooth']], 'zoom': [[0, z, 'smooth']]},
            'actors': actors, 'props': [], 'overlays': [], 'dof': 0}


if __name__ == '__main__':
    import sys
    cfg = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    build([shot(s['id'], s['set'], [actor(**a) for a in s.get('actors', [])], tuple(s.get('cam', (640, 360, 1.0)))) for s in cfg])
