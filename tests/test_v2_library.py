"""Library management of v2 films (new film, import, duplicate, new set/prop, remove). Temp project folders only."""
from pathlib import Path
import base64
import io
import json
import shutil
import pytest

pytest.importorskip('skia')
from PIL import Image
from celstudio.model import ContractError
from celstudio.v2 import project
from celstudio.v2.api import Service, V2Error
from celstudio.v2.stage import Stage

PILOT = Path(__file__).resolve().parents[1]/'projects/taller-v3'


@pytest.fixture
def svc(tmp_path):
    shutil.copytree(PILOT, tmp_path/'taller-v3', ignore=shutil.ignore_patterns('renders', '*.previous.json'))
    return Service(tmp_path)


def png(color='#336699', size=(64, 48)):
    out = io.BytesIO()
    Image.new('RGBA', size, color).save(out, 'PNG')
    return base64.b64encode(out.getvalue()).decode()


def render_first_frame(root, shot_id):
    film = project.compile_script(project.load(root), root)
    shot = next(s for s in film['shots'] if s['id'] == shot_id)
    frame = Stage(film, root, 160).frame_array(shot, 0.3, 7)
    assert frame.shape == (90, 160, 4) and frame[..., :3].std() > 3
    return frame


def test_new_film_is_valid_and_empty(svc):
    made = svc.create_film({'title': 'Mi película nueva'})
    assert made['id'] == 'mi-pelicula-nueva' and svc.create_film({'title': 'Mi película nueva'})['id'] == 'mi-pelicula-nueva-2'
    root = svc.projects/made['id']
    script = project.load(root)
    assert script['shots'] == [] and script['characters'] == {} and script['revision'] == 1
    assert project.check(script, root) == [] and project.compile_script(script, root)['shots'] == []
    assert json.loads((root/'film.json').read_text(encoding='utf-8'))['shots'] == []
    film = svc.film(made['id'])
    assert film['errors'] == [] and film['characters'] == {} and film['script']['title'] == 'Mi película nueva'
    assert {f['id'] for f in svc.films_list()} >= {'taller-v3', made['id']}
    with pytest.raises(ContractError):
        svc.start_render(None, made['id'], {})                  # nothing to render yet
    with pytest.raises(ContractError):
        svc.root('../fuera')


def test_import_into_a_new_film_then_scene_shot_and_frame(svc):
    pid = svc.create_film({'title': 'Otra historia'})['id']
    root = svc.projects/pid
    assert any(i['film'] == 'taller-v3' and i['kind'] == 'characters' and i['id'] == 'luma' for i in svc.importable(pid))
    assert not any(i['film'] == pid for i in svc.importable(pid))
    luma = svc.import_item(pid, {'film': 'taller-v3', 'kind': 'characters', 'id': 'luma'})
    valley = svc.import_item(pid, {'film': 'taller-v3', 'kind': 'sets', 'id': 'valley'})
    svc.import_item(pid, {'film': 'taller-v3', 'kind': 'props', 'id': 'butterfly'})
    assert luma['id'] == 'luma' and luma['revision'] == 2 and valley['library']['sets'] == {'valley': 'sets/valley.json'}
    # self-contained: every image of the copies exists under the new project and nothing points elsewhere
    rig = json.loads((root/'characters/luma.json').read_text(encoding='utf-8'))
    images = svc._images_of(root, rig)
    assert images and all(i.startswith('assets/luma/') for i in images) and all((root/i).is_file() for i in images)
    layers = json.loads((root/'sets/valley.json').read_text(encoding='utf-8'))['layers']
    assert all(layer['image'].startswith('assets/sets/valley/') and (root/layer['image']).is_file() for layer in layers)
    butterfly = project.load(root)['props']['butterfly']
    assert butterfly['sheet'].startswith('assets/props/butterfly/') and (root/butterfly['sheet']).is_file() and butterfly['id'] == 'butterfly'
    # the id collides: another copy gets a new id
    again = svc.import_item(pid, {'film': 'taller-v3', 'kind': 'characters', 'id': 'luma'})
    assert again['id'] == 'luma-2' and (root/'assets/luma-2').is_dir()
    renamed = svc.import_item(pid, {'film': 'taller-v3', 'kind': 'characters', 'id': 'pip', 'as': 'pepe'})
    assert renamed['id'] == 'pepe' and project.load(root)['characters']['pepe'] == 'characters/pepe.json'
    # scene + shot + one frame
    script = project.load(root)
    script['scenes'] = [{'id': 'campo', 'title': 'Campo', 'description': '', 'set': 'valley',
                         'cast': [{'id': 'luma', 'character': 'luma', 'start': {'x': 400, 'y': 690.0, 'scale': 0.66}}], 'props': []}]
    script['shots'] = [{'id': 'a1', 'scene': 'campo', 'duration': 1.0, 'description': '', 'actors': [{'id': 'luma'}], 'props': [],
                        'actions': [{'on': 'luma', 'do': 'face', 't': 0.2, 'name': 'happy'}]}]
    saved = project.save(root, script, expect_revision=script['revision'])
    assert saved['revision'] == script['revision']+1
    render_first_frame(root, 'a1')
    # path safety
    for bad in ({'film': pid}, {'film': '../x'}, {'film': 'taller-v3', 'id': 'nadie'}, {'film': 'nada', 'id': 'luma'}):
        with pytest.raises(ContractError):
            svc.import_item(pid, {'kind': 'characters', 'id': 'luma', **bad})
    with pytest.raises(ContractError):
        svc.import_item(pid, {'film': 'taller-v3', 'kind': 'raro', 'id': 'luma'})


def test_duplicate_set_variant_is_independent(svc):
    root = svc.projects/'taller-v3'
    made = svc.duplicate_item('taller-v3', {'kind': 'sets', 'id': 'valley', 'as': 'valle-noche'})
    assert made['id'] == 'valle-noche' and made['data']['layers']
    spec = made['data']
    assert all(layer['image'].startswith('assets/sets/valle-noche/') and (root/layer['image']).is_file() for layer in spec['layers'])
    assert (root/'assets/set/sky.png').is_file()                          # the original is untouched
    spec['color'] = '#101830'
    spec['layers'] = spec['layers'][:2]
    svc.save_set('taller-v3', 'valle-noche', spec)
    assert json.loads((root/'sets/valley.json').read_text(encoding='utf-8'))['color'] != '#101830'
    assert svc.duplicate_item('taller-v3', {'kind': 'sets', 'id': 'valley'})['id'] == 'valley-copia'
    assert svc.duplicate_item('taller-v3', {'kind': 'sets', 'id': 'valley'})['id'] == 'valley-copia-2'
    twin = svc.duplicate_item('taller-v3', {'kind': 'characters', 'id': 'pip', 'as': 'pip-b'})
    assert project.load(root)['characters']['pip-b'] == 'characters/pip-b.json' and twin['data']['name']
    with pytest.raises(ContractError):
        svc.duplicate_item('taller-v3', {'kind': 'sets', 'id': 'valley', 'as': 'valle-noche'})
    # a scene can use the variant
    script = project.load(root)
    script['scenes'].append({'id': 'noche', 'title': '', 'description': '', 'set': 'valle-noche',
                             'cast': [{'id': 'pip-b', 'character': 'pip-b', 'start': {'x': 500, 'y': 690.0, 'scale': 0.6}}], 'props': []})
    script['shots'].append({'id': 'n1', 'scene': 'noche', 'duration': 1.0, 'actors': [{'id': 'pip-b'}], 'props': [], 'actions': []})
    project.save(root, script, expect_revision=script['revision'])
    render_first_frame(root, 'n1')


def test_new_set_with_uploaded_layer_and_new_prop(svc):
    pid = svc.create_film({'title': 'Vacía'})['id']
    root = svc.projects/pid
    svc.import_item(pid, {'film': 'taller-v3', 'kind': 'characters', 'id': 'pip'})
    made = svc.create_set(pid, {'id': 'patio', 'color': '#88aacc'})
    assert made['data']['layers'] == [] and made['data']['color'] == '#88aacc' and (root/'sets/patio.json').is_file()
    with pytest.raises(ContractError):
        svc.create_set(pid, {'id': 'patio'})
    layer = svc.upload(pid, {'category': 'set_layer', 'target': 'patio', 'name': 'Fondo grande.PNG', 'data': png('#ccaa66', (320, 180))})
    assert layer['file'].startswith('assets/sets/patio/fondo-grande-') and (root/layer['file']).is_file()
    spec = made['data']
    spec['layers'].append({'id': 'fondo', 'image': layer['file'], 'x': 640, 'y': 360, 'w': 1280, 'depth': 0.1})
    svc.save_set(pid, 'patio', spec)
    sheet = svc.upload(pid, {'category': 'prop_sheet', 'target': 'pelota', 'name': 'pelota.png', 'data': png('#cc3333', (40, 40))})
    prop = svc.add_prop(pid, {'id': 'pelota', 'spec': {'sheet': sheet['file'], 'upp': 0.5}})
    assert prop['library']['props']['pelota']['cells'] == [[0, 0, 40, 40]] and prop['library']['props']['pelota']['upp'] == 0.5
    script = project.load(root)
    script['scenes'] = [{'id': 'p', 'title': '', 'description': '', 'set': 'patio',
                         'cast': [{'id': 'pip', 'character': 'pip', 'start': {'x': 600, 'y': 690.0, 'scale': 0.6}}],
                         'props': [{'id': 'pelota', 'prop': 'pelota', 'spec': {}}]}]
    script['shots'] = [{'id': 'p1', 'scene': 'p', 'duration': 1.0, 'actors': [{'id': 'pip'}], 'props': [{'id': 'pelota', 'spec': {}}],
                        'actions': [{'on': 'pelota', 'do': 'key', 't': 0, 'channel': 'x', 'value': 300},
                                    {'on': 'pelota', 'do': 'key', 't': 0, 'channel': 'y', 'value': 500}]}]
    project.save(root, script, expect_revision=script['revision'])
    render_first_frame(root, 'p1')
    for bad in ({'category': 'otra', 'target': 'x'}, {'category': 'set_layer', 'target': 'no-existe'}, {'category': 'set_layer'}):
        with pytest.raises(ContractError):
            svc.upload(pid, {'name': 'a.png', 'data': png(), **bad})
    with pytest.raises(ContractError):
        svc.upload(pid, {'category': 'set_layer', 'target': 'patio', 'name': 'a.png', 'data': base64.b64encode(b'no').decode()})
    with pytest.raises(ContractError):
        svc.add_prop(pid, {'id': 'otra', 'spec': {'sheet': 'assets/no-existe.png'}})


def test_remove_is_refused_while_used_and_never_deletes_files(svc):
    root = svc.projects/'taller-v3'
    for kind, name in (('characters', 'luma'), ('sets', 'valley'), ('props', 'butterfly'), ('props', 'puff')):
        with pytest.raises(V2Error) as info:
            svc.remove_item('taller-v3', {'kind': kind, 'id': name})
        assert 'No se puede quitar' in str(info.value) and info.value.payload['usages']
    assert 'luma' in project.load(root)['characters'] and (root/'characters/luma.json').is_file()
    twin = svc.duplicate_item('taller-v3', {'kind': 'characters', 'id': 'luma', 'as': 'luma-b'})
    # the browser holds an unsaved scene that uses it: refused too
    unsaved = project.load(root)
    unsaved['scenes'][0]['cast'].append({'id': 'luma-b', 'character': 'luma-b'})
    with pytest.raises(V2Error) as info:
        svc.remove_item('taller-v3', {'kind': 'characters', 'id': 'luma-b', 'script': unsaved})
    assert 'luma-b' in str(info.value) and 'luma-b' in project.load(root)['characters']
    before = project.load(root)['revision']
    result = svc.remove_item('taller-v3', {'kind': 'characters', 'id': 'luma-b'})
    assert result['revision'] == before+1 and 'luma-b' not in result['library']['characters'] and result['moved'] == 'papelera/characters/luma-b.json'
    assert (root/'papelera/characters/luma-b.json').is_file() and not (root/'characters/luma-b.json').exists()
    assert (root/'assets/luma-b').is_dir()                                # images are kept
    assert project.check(project.load(root), root) == []
    extra = svc.duplicate_item('taller-v3', {'kind': 'props', 'id': 'butterfly', 'as': 'mariposa-2'})
    assert 'mariposa-2' in extra['library']['props']
    assert svc.remove_item('taller-v3', {'kind': 'props', 'id': 'mariposa-2'})['moved'] is None
    with pytest.raises(ContractError):
        svc.remove_item('taller-v3', {'kind': 'props', 'id': 'mariposa-2'})
