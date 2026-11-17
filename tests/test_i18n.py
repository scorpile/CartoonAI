"""Spanish/English: catalogs with the same keys, localized API errors, and a syntax check of the web scripts."""
from pathlib import Path
import json
import re
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
import pytest

pytest.importorskip('skia')
from celstudio.v2 import i18n, project
from celstudio.server import Studio, handler, ThreadingHTTPServer

REPO = Path(__file__).resolve().parents[1]
PILOT = REPO/'projects/taller-v3'
PLACEHOLDER = re.compile(r'\{(\w+)(?:![rsa])?\}')


def web_catalog():
    text = (REPO/'web/studio.js').read_text(encoding='utf-8')
    block = text[text.index('const CATALOG = ')+len('const CATALOG = '):text.index('/* i18n:end */')].strip().rstrip(';')
    return json.loads(block)


def test_python_catalog_has_same_keys_and_placeholders():
    es, en = i18n.CATALOGS['es'], i18n.CATALOGS['en']
    assert set(es) == set(en)
    for key in es:
        assert sorted(PLACEHOLDER.findall(es[key])) == sorted(PLACEHOLDER.findall(en[key])), key
    used = set()
    for name in ('project.py', 'api.py'):
        used |= set(re.findall(r"msg\(\s*'([\w.]+)'", (REPO/'celstudio/v2'/name).read_text(encoding='utf-8')))
    assert used <= set(es), used-set(es)


def test_web_catalog_has_same_keys_and_placeholders():
    catalog = web_catalog()
    es, en = catalog['es'], catalog['en']
    assert set(es) == set(en)
    for key in es:
        assert sorted(PLACEHOLDER.findall(es[key])) == sorted(PLACEHOLDER.findall(en[key])), key
        assert es[key].count('|') == en[key].count('|'), key          # plural forms «singular|plural»
    code = (REPO/'web/studio.js').read_text(encoding='utf-8')
    code = code[:code.index('/* i18n:begin')]+code[code.index('/* i18n:end */'):]     # without the catalog itself
    code = re.sub(r'/\*.*?\*/', '', code, flags=re.S)
    html = (REPO/'web/studio.html').read_text(encoding='utf-8')
    used = set(re.findall(r"\bt\('([\w.]+)'", code)) | set(re.findall(r"\btp\('([\w.]+)'", code)) | set(re.findall(r"'(ui\.\w+)'", code))
    used |= set(re.findall(r'data-i18n(?:-\w+)?="([\w.]+)"', html))
    used -= {'ui.no_importable_'}
    assert used <= set(es), sorted(used-set(es))
    assert {f'ui.no_importable_{k}' for k in ('characters', 'sets', 'props')} <= set(es)


def test_messages_default_to_spanish_and_render_in_english():
    error = project.ScriptError(i18n.msg('p.falta_el_campo', key='fps'), 'fps')
    assert str(error) == 'Falta el campo «fps»'
    assert i18n.render(error, 'en') == 'Missing field «fps»'
    joined = i18n.join('; ', [i18n.msg('a.tiempo_no_valido'), i18n.msg('a.ancho_no_valido')], '…')
    assert joined == 'Tiempo no válido; Ancho no válido…' and joined.render('en') == 'Invalid time; Invalid width…'
    assert i18n.pick_lang({'lang': ['en']}) == 'en' and i18n.pick_lang({}) == 'es'
    assert i18n.pick_lang({}, 'en-US,en;q=0.9,es;q=0.5') == 'en' and i18n.pick_lang({}, 'es-MX,en;q=0.5') == 'es'
    assert i18n.pick_lang({'lang': ['fr']}, 'fr') == 'es'


def test_check_errors_keep_spanish_text_and_localize():
    script = project.load(PILOT)
    script['shots'][0]['actions'].append({'on': 'nadie', 'do': 'to'})
    errors = project.check(script, PILOT)
    bad = [e for e in errors if 'Destino desconocido' in e['message']]
    assert bad and bad[0]['path'].startswith('shots[0].actions[')
    assert 'Unknown target' in i18n.localize(bad, 'en')[0]['message']


@pytest.fixture(scope='module')
def app(tmp_path_factory):
    projects = tmp_path_factory.mktemp('projects')
    shutil.copytree(PILOT, projects/'taller-v3', ignore=shutil.ignore_patterns('renders', '*.previous.json'))
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler(Studio(projects)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_address[1]}/api/v2'

    def call(path, body=None):
        data = None if body is None else json.dumps(body).encode('utf-8')
        request = urllib.request.Request(base+path, data=data, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())
    yield call
    server.shutdown()
    server.server_close()


def test_api_error_in_spanish_by_default_and_english_with_lang(app):
    status, body = app('/films/taller-v3', {'script': 'no es un objeto'})
    assert status == 400 and body['error'] == 'El guion debe ser un objeto JSON'
    status, body = app('/films/taller-v3?lang=en', {'script': 'not an object'})
    assert status == 400 and body['error'] == 'The script must be a JSON object'
    status, body = app('/films/no-existe?lang=en')
    assert status == 400 and body['error'] == 'Film does not exist'
    status, body = app('/films/taller-v3/nada?lang=en')
    assert status == 404 and body['error'] == 'Route does not exist'
    status, body = app('/films/taller-v3/nada')
    assert status == 404 and body['error'] == 'Ruta inexistente'


def test_check_messages_localized_in_api(app):
    script = project.load(PILOT)
    script['shots'][0]['actions'].append({'on': 'nadie', 'do': 'to'})
    status, body = app('/films/taller-v3/check?lang=en', {'script': script})
    assert status == 200 and any('Unknown target' in e['message'] for e in body['errors'])
    status, body = app('/films/taller-v3/check', {'script': script})
    assert any('Destino desconocido' in e['message'] for e in body['errors'])


def test_web_scripts_pass_node_check():
    node = shutil.which('node')
    if node is None:
        pytest.skip('node is not installed')
    for script in sorted((REPO/'web').glob('*.js')):
        result = subprocess.run([node, '--check', str(script)], capture_output=True, text=True)
        assert result.returncode == 0, f'{script.name}: {result.stderr}'
