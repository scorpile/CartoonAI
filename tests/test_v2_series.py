"""Series -> episodes: one shared library, scripts per episode. Temporary copies only (the real projects are never touched)."""
from pathlib import Path
import json
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import pytest

pytest.importorskip('skia')
from celstudio.v2 import project
from celstudio.v2.stage import Stage, load_film
from celstudio.server import Studio, handler, ThreadingHTTPServer

PILOT = Path(__file__).resolve().parents[1]/'projects/taller-v3'
REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def app(tmp_path_factory):
    projects = tmp_path_factory.mktemp('projects')
    shutil.copytree(PILOT, projects/'taller-v3', ignore=shutil.ignore_patterns('renders', '*.previous.json'))
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler(Studio(projects)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_address[1]}/api/v2'

    def call(path, body=None, raw=False):
        data = None if body is None else json.dumps(body).encode('utf-8')
        request = urllib.request.Request(base+path, data=data, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request) as response:
                payload = response.read()
                return response.status, (payload if raw else json.loads(payload))
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())
    call.projects = projects
    yield call
    server.shutdown()
    server.server_close()


def ok(result):
    assert result[0] in (200, 201), result
    return result[1]


def test_series_api_end_to_end(app):
    projects = app.projects
    made = ok(app('/series', {'title': 'Serie de prueba', 'id': 'serie'}))
    assert made['id'] == 'serie'
    root = projects/'serie'
    series = json.loads((root/'series.json').read_text(encoding='utf-8'))
    assert series['kind'] == 'series' and series['library'] == {'characters': {}, 'sets': {}, 'props': {}}
    assert (root/'episodes').is_dir() and app('/series', {'id': 'serie'})[0] == 400

    # series library: import from the standalone film (files copied, paths rewritten, nothing in taller-v3 changes)
    before = (projects/'taller-v3'/'script.json').read_bytes()
    for kind, name in (('characters', 'luma'), ('characters', 'pip'), ('sets', 'valley'), ('props', 'puff')):
        ok(app('/series/serie/library/import', {'film': 'taller-v3', 'kind': kind, 'id': name}))
    assert (projects/'taller-v3'/'script.json').read_bytes() == before
    assert app('/series/serie/library/import', {'film': 'serie', 'kind': 'sets', 'id': 'valley'})[0] == 400
    lib = ok(app('/series/serie'))
    assert lib['counts'] == {'characters': 2, 'sets': 1, 'props': 1}

    # two episodes sharing the library
    assert ok(app('/series/serie/episodes', {'title': 'Uno'}))['id'] == 'ep01'
    assert ok(app('/series/serie/episodes', {'title': 'Dos'}))['pid'] == 'serie/episodes/ep02'
    assert app('/series/serie/episodes', {'id': 'ep01'})[0] == 400
    ep1 = ok(app('/films/serie/episodes/ep01'))
    assert set(ep1['script']['characters']) == {'luma', 'pip'} and ep1['errors'] == [] and ep1['series']['id'] == 'serie'
    script = ep1['script']
    script['scenes'] = [{'id': 'a', 'title': 'A', 'description': '', 'set': 'valley',
                         'cast': [{'id': 'luma', 'character': 'luma', 'start': {'x': 600, 'y': 690.0, 'scale': 0.6}},
                                  {'id': 'pip', 'character': 'pip', 'start': {'x': 800, 'y': 690.0, 'scale': 0.6}}], 'props': []}]
    script['shots'] = [{'id': 's1', 'scene': 'a', 'duration': 1.0, 'description': '', 'actors': [{'id': 'luma'}, {'id': 'pip'}],
                        'props': [], 'actions': [{'on': 'luma', 'do': 'to', 't': 0.2, 'dur': 0.4, 'smile': 0.8}]}]
    saved = ok(app('/films/serie/episodes/ep01', {'script': script}))['script']
    assert saved['revision'] == 2
    stored = json.loads((root/'episodes/ep01/script.json').read_text(encoding='utf-8'))
    assert 'characters' not in stored and 'sets' not in stored and 'library' not in stored     # library stays in series.json
    ep2 = ok(app('/films/serie/episodes/ep02'))['script']
    ep2['scenes'] = [{'id': 'b', 'title': 'B', 'description': '', 'set': 'valley',
                      'cast': [{'id': 'luma', 'character': 'luma', 'start': {'x': 600, 'y': 690.0, 'scale': 0.6}}], 'props': []}]
    ep2['shots'] = [{'id': 't1', 'scene': 'b', 'duration': 1.0, 'actors': [{'id': 'luma'}], 'actions': []}]
    ok(app('/films/serie/episodes/ep02', {'script': ep2}))

    # compiled film names its asset root; the renderer draws it unchanged
    film = json.loads((root/'episodes/ep01/film.json').read_text(encoding='utf-8'))
    assert film['root'] == '../..' and set(film['characters']) == {'luma', 'pip'}
    loaded, assets = load_film(root/'episodes/ep01/film.json')
    assert assets.resolve() == root.resolve()
    Stage(loaded, assets, 160).frame(loaded['shots'][0], 0.5, 12)
    status, jpeg = app('/films/serie/episodes/ep01/frame?shot=s1&t=0.5&w=160', raw=True)
    assert status == 200 and jpeg[:2] == b'\xff\xd8'
    assert ok(app('/films/serie/episodes/ep01/pose?character=luma&w=160', raw=True)) [:2] == b'\xff\xd8'

    # usage across episodes and the catalogue
    cat = ok(app('/series/serie/library?kind=characters'))
    by_id = {i['id']: i for i in cat['items']}
    assert set(by_id['luma']['episodes']) == {'ep01', 'ep02'} and set(by_id['pip']['episodes']) == {'ep01'}
    assert ok(app('/series/serie/library?q=pi'))['total'] == 1 and ok(app('/series/serie/library?used=0'))['total'] == 1   # only puff is unused
    usage = ok(app('/series/serie/usage?kind=characters&id=luma'))
    assert {u['episode'] for u in usage['usages']} == {'ep01', 'ep02'}
    assert set(project.series_usage(root)['sets']['valley']) == {'ep01', 'ep02'}

    # removal is refused while any episode uses it; unused items can go (JSON to papelera/)
    status, error = app('/series/serie/library/remove', {'kind': 'characters', 'id': 'pip'})
    assert status == 400 and 'ep01' in error['error'] and error['usages']
    status, _ = app('/films/serie/episodes/ep02/library/remove', {'kind': 'characters', 'id': 'luma'})
    assert status == 400
    removed = ok(app('/series/serie/library/remove', {'kind': 'props', 'id': 'puff'}))
    assert 'puff' not in removed['library']['props']

    # scene import between episodes: nothing is written, ids are renamed on clash
    result = ok(app('/films/serie/episodes/ep02/scenes/import', {'episode': 'ep01', 'scene': 'a'}))
    assert result['scene']['id'] == 'a' and [s['id'] for s in result['shots']] == ['s1'] and result['shots'][0]['scene'] == 'a'
    again = ok(app('/films/serie/episodes/ep01/scenes/import', {'episode': 'ep01', 'scene': 'a'}))
    assert again['scene']['id'] == 'a-2' and again['shots'][0]['id'] == 's1-2'

    # episodes: duplicate, rename, delete with confirmation (moved to papelera, never lost)
    dup = ok(app('/series/serie/episodes/ep01/duplicate', {'as': 'ep03'}))
    assert dup['pid'] == 'serie/episodes/ep03' and (root/'episodes/ep03/film.json').is_file()
    assert ok(app('/series/serie/episodes/ep03/rename', {'title': 'Tres'}))['title'] == 'Tres'
    assert app('/series/serie/episodes/ep03/delete', {})[0] == 400
    ok(app('/series/serie/episodes/ep03/delete', {'confirm': 'ep03'}))
    assert not (root/'episodes/ep03').exists() and list((root/'papelera/episodes').glob('ep03-*'))

    # listing: series and standalone films side by side
    kinds = {f['id']: f['kind'] for f in ok(app('/films'))}
    assert kinds == {'serie': 'series', 'taller-v3': 'film'}
    assert ok(app('/films'))[0]['episodes'] == 2
    assert app('/films/serie')[0] == 400            # a series is not a film
    assert ok(app('/series/serie'))['episodes'][0]['title'] == 'Uno'


def test_episode_local_items_and_check(tmp_path):
    shutil.copytree(PILOT, tmp_path/'t', ignore=shutil.ignore_patterns('renders', '*.previous.json'))
    root = project.convert_series(tmp_path/'t')
    home = root/'episodes/ep01'
    assert project.series_root(home) == root
    raw = project.load_raw(home)
    raw['characters'] = {'luma-local': 'characters/luma.json', 'pip': 'characters/pip.json'}    # one new, one that shadows
    (home/'script.json').write_text(json.dumps(raw), encoding='utf-8')
    script = project.load(home)
    assert {'luma', 'pip', 'luma-local'} <= set(script['characters'])
    assert project.check(script, home) == []
    assert [w['path'] for w in project.warnings(script, home)] == ['characters.pip']
    saved = project.save(home, script)
    assert set(project.load_raw(home)['characters']) == {'luma-local', 'pip'}      # series items do not leak into the episode
    assert saved['revision'] >= 1


def test_convert_series_keeps_the_film(tmp_path):
    shutil.copytree(PILOT, tmp_path/'t', ignore=shutil.ignore_patterns('renders', '*.previous.json'))
    original = json.loads((tmp_path/'t/film.json').read_text(encoding='utf-8'))
    root = project.convert_series(tmp_path/'t')
    assert not (root/'script.json').exists() and (root/'series.json').is_file()
    series = project.load_series(root)
    assert set(series['library']['characters']) == {'luma', 'pip'}
    film = json.loads((root/'episodes/ep01/film.json').read_text(encoding='utf-8'))
    assert film.pop('root') == '../..'
    film['id'] = original['id']
    assert film['shots'] == original['shots'] and film['sets'] == original['sets']
    with pytest.raises(project.ScriptError):
        project.convert_series(root)


def test_pruned_compile_ignores_unused_library(tmp_path):
    shutil.copytree(PILOT, tmp_path/'t', ignore=shutil.ignore_patterns('renders', '*.previous.json'))
    root = project.convert_series(tmp_path/'t')
    series = project.load_series(root)
    series['library']['characters']['ghost'] = 'characters/missing.json'      # a broken item that no episode uses
    (root/'series.json').write_text(json.dumps(series), encoding='utf-8')
    home = root/'episodes/ep01'
    assert project.check(project.load(home), home) == []
    assert 'ghost' not in project.compile_script(project.load(home), home)['characters']
    with pytest.raises(project.ScriptError):
        project.save_series(root, series)                                       # but the library itself is validated


def test_standalone_film_is_unchanged(app):
    film = ok(app('/films/taller-v3'))
    assert 'series' not in film and film['errors'] == []
    compiled = json.loads((PILOT/'film.json').read_text(encoding='utf-8'))
    assert 'root' not in compiled
    assert project.series_root(PILOT) is None and project.asset_root(PILOT) == PILOT


def test_cli(tmp_path):
    def run(*args):
        return subprocess.run([sys.executable, '-m', 'celstudio.v2', *args], cwd=tmp_path, capture_output=True, text=True,
                              env={**__import__('os').environ, 'PYTHONPATH': str(REPO)})
    (tmp_path/'projects').mkdir()
    assert run('new-series', 'mi-serie', '--title', 'Mi serie').returncode == 0
    assert run('new-series', 'mi-serie').returncode != 0
    assert run('new-episode', 'mi-serie', 'ep01').returncode == 0
    done = run('compile', 'projects/mi-serie/episodes/ep01/script.json')
    assert done.returncode == 0 and json.loads(done.stdout)['shots'] == 0
    assert (tmp_path/'projects/mi-serie/episodes/ep01/film.json').is_file()
    assert run('compile', 'projects/mi-serie/episodes/ep01').returncode == 0


def test_layer_order_and_actor_order_pass_through(tmp_path):
    shutil.copytree(PILOT, tmp_path/'t', ignore=shutil.ignore_patterns('renders', '*.previous.json'))
    root = tmp_path/'t'
    script = project.load(root)
    layer = json.loads((root/'sets/valley.json').read_text(encoding='utf-8'))['layers'][0]['id']
    script['shots'][0]['layer_order'] = {layer: 2}
    script['shots'][0]['actors'][0]['order'] = 3
    film = project.compile_script(script, root)
    assert film['shots'][0]['layer_order'] == {layer: 2} and film['shots'][0]['actors'][0]['order'] == 3
    script['shots'][0]['layer_order'] = {'nope': 1}
    assert project.check(script, root)[0]['path'] == 'shots[0].layer_order.nope'
