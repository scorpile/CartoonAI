"""Engine v2 web API, against a temporary copy of the taller-v3 pilot (the real project is never touched)."""
from pathlib import Path
import base64
import io
import json
import shutil
import threading
import time
import urllib.error
import urllib.request
import pytest

pytest.importorskip('skia')
from PIL import Image
from celstudio.server import Studio, handler, ThreadingHTTPServer

PILOT = Path(__file__).resolve().parents[1]/'projects/taller-v3'


@pytest.fixture(scope='module')
def app(tmp_path_factory):
    projects = tmp_path_factory.mktemp('projects')
    shutil.copytree(PILOT, projects/'taller-v3', ignore=shutil.ignore_patterns('renders', '*.previous.json'))
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler(Studio(projects)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_address[1]}'

    def call(path, body=None, raw=False):
        """GET/POST under /api/v2/films, or an absolute URL. Returns (status, content type, json or bytes)."""
        data = None if body is None else json.dumps(body).encode('utf-8')
        url = path if path.startswith('http') else base+'/api/v2/films'+path
        request = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request) as response:
                payload = response.read()
                return response.status, response.headers['Content-Type'], (payload if raw else json.loads(payload))
        except urllib.error.HTTPError as error:
            return error.code, error.headers['Content-Type'], json.loads(error.read())
    call.base, call.root = base, projects/'taller-v3'
    yield call
    server.shutdown()
    server.server_close()


def get(url):
    with urllib.request.urlopen(url) as response:
        return response.status, response.headers['Content-Type'], response.read()


def script_of(app):
    return json.loads((app.root/'script.json').read_text(encoding='utf-8'))


def test_pages_and_routes(app):
    _, kind, studio = get(app.base+'/')
    assert kind.startswith('text/html') and b'studio.js' in studio
    for name, mime in (('studio.js', 'javascript'), ('studio.css', 'css')):
        assert mime in get(f'{app.base}/{name}')[1]
    for gone in ('/clasico', '/app.js', '/api/projects'):
        with pytest.raises(urllib.error.HTTPError) as err:
            get(app.base+gone)
        assert err.value.code == 404


def test_list_and_get_film(app):
    status, _, films = app('')
    assert status == 200 and films[0]['id'] == 'taller-v3' and films[0]['shots'] > 3 and films[0]['seconds'] > 10
    _, _, film = app('/taller-v3')
    assert film['errors'] == [] and set(film['characters']) == {'luma', 'pip'} and 'valley' in film['sets']
    assert 'walk' in [v['name'] for v in film['catalogue']['verbs']['actor']]
    assert film['script']['shots'][0]['id']
    assert app('/nope')[0] == 400


def test_check_does_not_write(app):
    script = script_of(app)
    before = (app.root/'script.json').read_bytes()
    assert app('/taller-v3/check', {'script': script})[2] == {'errors': []}
    script['shots'][0]['actions'].append({'on': 'luma', 'do': 'walk', 't0': 'x'})
    errors = app('/taller-v3/check', {'script': script})[2]['errors']
    assert errors and errors[0]['path'].startswith('shots[0].actions[')
    assert (app.root/'script.json').read_bytes() == before


def test_frame_preview_and_pose_are_jpeg(app):
    script = script_of(app)
    shot = script['shots'][0]['id']
    for url in (f'/taller-v3/frame?shot={shot}&t=1.0&w=320', '/taller-v3/pose?character=luma&turn=1&expression=happy&w=200'):
        status, kind, data = app(url, raw=True)
        assert status == 200 and kind == 'image/jpeg' and data[:2] == b'\xff\xd8'
    status, kind, data = app('/taller-v3/preview', {'script': script, 'shot': shot, 't': 0.5, 'w': 320}, raw=True)
    assert status == 200 and kind == 'image/jpeg' and Image.open(io.BytesIO(data)).width == 320
    assert app(f'/taller-v3/frame?shot={shot}&t=1&w=99999')[0] == 400
    assert app('/taller-v3/frame?shot=zzz&t=1')[0] == 400
    assert app('/taller-v3/pose?character=nadie')[0] == 400


def test_preview_uses_unsaved_script(app):
    script = script_of(app)
    shot = script['shots'][0]['id']
    base = app('/taller-v3/preview', {'script': script, 'shot': shot, 't': 0.2, 'w': 240}, raw=True)[2]
    script['shots'][0]['actors'][0]['start']['scale'] = 0.3
    changed = app('/taller-v3/preview', {'script': script, 'shot': shot, 't': 0.2, 'w': 240}, raw=True)[2]
    assert base != changed
    script['shots'][0]['actions'].append({'on': 'luma', 'do': 'nope', 't': 0})
    status, _, error = app('/taller-v3/preview', {'script': script, 'shot': shot, 't': 0, 'w': 240})
    assert status == 400 and error['path'] and error['errors']


def test_save_bumps_revision_and_keeps_film(app):
    script = app('/taller-v3')[2]['script']
    compiled = (app.root/'film.json').read_bytes()
    status, _, saved = app('/taller-v3', {'script': script})
    assert status == 200 and saved['script']['revision'] == script['revision']+1 and saved['errors'] == []
    assert (app.root/'film.json').read_bytes() == compiled
    assert script_of(app) == saved['script']
    stale = app('/taller-v3', {'script': script})            # same old revision: conflict
    assert stale[0] == 400 and 'revisi' in stale[2]['error'].lower()
    saved['script']['title'] = 'Otro título'
    assert app('/taller-v3', {'script': saved['script']})[0] == 200


def test_browser_style_roundtrip_keeps_file_identical(app):
    """JSON.stringify writes 690.0 as 690; saving an unedited script must still only change `revision`."""
    def jsify(value):
        if isinstance(value, dict):
            return {k: jsify(v) for k, v in value.items()}
        if isinstance(value, list):
            return [jsify(v) for v in value]
        return int(value) if isinstance(value, float) and value == int(value) else value
    before = (app.root/'script.json').read_text(encoding='utf-8')
    script = script_of(app)
    assert '.0,' in before or '.0\n' in before            # the pilot does contain integral floats
    status, _, saved = app('/taller-v3', {'script': jsify(script)})
    assert status == 200
    after = (app.root/'script.json').read_text(encoding='utf-8')
    assert after.replace(f'"revision": {saved["script"]["revision"]}', f'"revision": {script["revision"]}') == before


def test_broken_script_returns_path(app):
    script = script_of(app)
    before = (app.root/'script.json').read_bytes()
    script['shots'][1]['actions'][0]['do'] = 'inexistente'
    status, _, error = app('/taller-v3', {'script': script})
    assert status == 400 and error['path'] == 'shots[1].actions[0]' and error['errors']
    assert (app.root/'script.json').read_bytes() == before


def test_character_save_validates(app):
    path = app.root/'characters/pip.json'
    original = json.loads(path.read_text(encoding='utf-8'))
    for garbage in ({}, {'name': 'x'}, dict(original, head='no')):
        status, _, error = app('/taller-v3/characters/pip', garbage)
        assert status == 400 and error['error']
    assert json.loads(path.read_text(encoding='utf-8')) == original
    assert app('/taller-v3/characters/otro', original)[0] == 400
    changed = json.loads(json.dumps(original))
    changed['colors']['skin'] = '#aa8844'
    assert app('/taller-v3/characters/pip', changed)[0] == 200
    assert json.loads(path.read_text(encoding='utf-8'))['colors']['skin'] == '#aa8844'
    assert json.loads((app.root/'characters/pip.previous.json').read_text(encoding='utf-8')) == original
    assert json.loads((app.root/'film.json').read_text(encoding='utf-8'))['schema_version'] == 2


def test_set_save_validates(app):
    path = app.root/'sets/valley.json'
    original = json.loads(path.read_text(encoding='utf-8'))
    broken = json.loads(json.dumps(original))
    broken['layers'][0]['image'] = 'assets/set/no-existe.png'
    assert app('/taller-v3/sets/valley', broken)[0] == 400
    assert json.loads(path.read_text(encoding='utf-8')) == original
    original['ground_y'] = 691.0
    assert app('/taller-v3/sets/valley', original)[0] == 200
    assert (app.root/'sets/valley.previous.json').exists()


def test_upload_reference(app):
    image = io.BytesIO()
    Image.new('RGB', (8, 8), '#336699').save(image, 'PNG')
    revision = script_of(app)['revision']
    status, _, result = app('/taller-v3/upload', {'name': 'ref.png', 'kind': 'estilo', 'notes': 'n',
                                                   'data': base64.b64encode(image.getvalue()).decode()})
    assert status == 200 and result['revision'] == revision+1
    assert script_of(app)['references'][-1]['file'] == result['file'] and (app.root/result['file']).is_file()
    assert get(f'{app.base}/files/taller-v3/{result["file"]}')[0] == 200
    text = app('/taller-v3/upload', {'name': 'nota.md', 'kind': 'guion', 'data': base64.b64encode('hola'.encode()).decode()})
    assert text[0] == 200 and text[2]['file'].endswith('.txt')
    assert app('/taller-v3/upload', {'name': 'x.png', 'kind': 'estilo', 'data': base64.b64encode(b'no').decode()})[0] == 400
    assert app('/taller-v3/upload', {'name': 'x.png', 'kind': 'raro', 'data': ''})[0] == 400


def test_render_job_single_short_shot(app):
    if not shutil.which('ffmpeg'):
        pytest.skip('sin ffmpeg')
    shortest = min(script_of(app)['shots'], key=lambda s: s['duration'])['id']
    status, _, job = app('/taller-v3/render', {'shot': shortest, 'width': 160})
    assert status == 202
    for _ in range(300):
        _, _, job = app(f'{app.base}/api/jobs/{job["id"]}')
        if job['status'] not in ('queued', 'running'):
            break
        time.sleep(.5)
    assert job['status'] == 'completed', job
    assert get(app.base+job['result']['url'])[0] == 200
    assert job['id'] in job['result']['file']
    assert not list((app.root/'renders').glob('*.parts'))
    assert app('/taller-v3/render', {'shot': '../x'})[0] == 400


def test_library_routes_over_http(app):
    status, _, made = app('', {'title': 'Película de prueba'})
    assert status == 201 and made['id'] == 'pelicula-de-prueba'
    pid = made['id']
    assert app(f'/{pid}')[2]['script']['shots'] == []
    _, _, items = app(f'/{pid}/importable')
    assert {'film': 'taller-v3', 'title': items[0]['title'], 'kind': 'characters', 'id': 'luma'} in items
    status, _, imported = app(f'/{pid}/library/import', {'film': 'taller-v3', 'kind': 'characters', 'id': 'luma'})
    assert status == 200 and imported['id'] == 'luma' and imported['library']['characters'] == {'luma': 'characters/luma.json'}
    assert imported['revision'] == 2 and imported['data']['name']
    assert get(f'{app.base}/files/{pid}/assets/luma/torso.png')[0] == 200      # copied images are served from the new film
    status, _, error = app(f'/{pid}/library/import', {'film': pid, 'kind': 'characters', 'id': 'luma'})
    assert status == 400 and error['error']
    assert app(f'/{pid}/library/duplicate', {'kind': 'characters', 'id': 'luma', 'as': 'luma-b'})[0] == 200
    assert app(f'/{pid}/library/set', {'id': 'patio'})[0] == 200
    assert app(f'/{pid}/library/remove', {'kind': 'sets', 'id': 'patio'})[0] == 200
    status, _, error = app(f'/{pid}/render', {})
    assert status == 400 and 'planos' in error['error']
    assert app(f'/{pid}/library/nada', {})[0] == 404
    shutil.rmtree(app.root.parent/pid)
