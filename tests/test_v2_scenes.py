"""Scenes in the v2 format: library -> scene -> shot (expansion, validation, intercut films). Temp copies only."""
from pathlib import Path
import copy
import json
import shutil
import pytest

pytest.importorskip('skia')
from celstudio.v2 import project
from celstudio.v2.stage import Stage

PILOT = Path(__file__).resolve().parents[1]/'projects/taller-v3'


def plain(value):
    return json.loads(json.dumps(value))


@pytest.fixture
def root(tmp_path):
    target = tmp_path/'taller'
    shutil.copytree(PILOT, target, ignore=shutil.ignore_patterns('renders', '*.previous.json'))
    return target


def two_scene_script(root):
    """Scene 1 on `valley` with both characters; scene 2 on a tweaked copy of the set with only Pip; shots intercut."""
    spec = json.loads((root/'sets/valley.json').read_text(encoding='utf-8'))
    spec['color'] = '#20283a'
    spec['layers'] = spec['layers'][:2]
    (root/'sets/dusk.json').write_text(json.dumps(spec), encoding='utf-8')
    script = project.load(root)
    script['sets']['dusk'] = 'sets/dusk.json'
    script['scenes'].append({'id': 'noche', 'title': 'Noche', 'description': '', 'set': 'dusk',
                             'cast': [{'id': 'pip', 'character': 'pip', 'start': {'x': 600, 'y': 690.0, 'scale': 0.5}}], 'props': []})
    day = script['shots']
    night = [{'id': f'n0{i}', 'scene': 'noche', 'duration': 1.0, 'description': '', 'actors': [{'id': 'pip', 'start': {'facing': -1}}],
              'props': [], 'actions': [{'on': 'pip', 'do': 'to', 't': 0.2, 'dur': 0.4, 'smile': 0.9}]} for i in (1, 2)]
    script['shots'] = [day[0], night[0], day[1], night[1]]
    return script


def test_pilot_uses_scenes_and_compiles_to_the_same_film():
    script = project.load(PILOT)
    assert [s['id'] for s in script['scenes']] == ['taller'] and all(s['scene'] == 'taller' and 'set' not in s for s in script['shots'])
    assert plain(project.compile_script(script, PILOT)) == json.loads((PILOT/'film.json').read_text(encoding='utf-8'))


def test_expansion_is_equivalent_and_invertible(root):
    script = project.load(root)
    flat = project.expand(script)
    assert all(s['set'] == 'valley' and 'scene' not in s for s in flat['shots'])
    assert {a['id'] for a in flat['shots'][3]['actors']} == {'luma', 'pip'} and flat['shots'][3]['actors'][0]['character']
    assert plain(project.compile_script(flat, root)) == plain(project.compile_script(script, root))
    assert plain(project.check(flat, root)) == []
    back = project.group_scene(flat, 'taller', 'valley', script['scenes'][0]['title'], script['scenes'][0]['description'])
    assert plain(back) == plain(script)                                   # recording the flat form again gives the scenes form
    assert project.expand(flat) == flat                                   # without scenes nothing changes


def test_shot_values_win_over_scene_values(root):
    script = project.load(root)
    script['scenes'][0]['props'][0]['spec'] = {'upp': 0.2, 'layer': 'front'}
    shot = script['shots'][3]                                              # s04: luma, pip and the butterfly
    shot['actors'][0]['start']['scale'] = 0.5
    shot['props'][0]['spec'] = {'upp': 0.3}
    flat = project.expand(script)['shots'][3]
    luma = next(a for a in flat['actors'] if a['id'] == 'luma')
    assert luma['start']['scale'] == 0.5 and luma['start']['y'] == 690.0 and luma['character'] == 'luma'
    assert flat['props'][0]['spec'] == {'upp': 0.3, 'layer': 'front'}
    assert plain(project.check(script, root)) == []


def test_puff_burst_needs_no_scene_listing(root):
    script = project.load(root)
    assert 'puff' not in [p['id'] for p in script['scenes'][0]['props']]
    script['shots'][0]['actions'].append({'on': 'shot', 'do': 'puff_burst', 't': 1, 'x': 400, 'y': 690})
    assert project.check(script, root) == []


def test_two_scene_film_intercut_compiles_and_renders(root):
    script = two_scene_script(root)
    assert project.check(script, root) == []
    film = project.compile_script(script, root)
    assert [(s['id'], s['set']) for s in film['shots']] == [('s01', 'valley'), ('n01', 'dusk'), ('s02', 'valley'), ('n02', 'dusk')]
    night = film['shots'][1]
    assert [a['id'] for a in night['actors']] == ['pip']
    assert [a['id'] for a in film['shots'][0]['actors']] == ['pip', 'luma']
    assert night['actors'][0]['channels']['x'][0][1] == 600 and night['actors'][0]['channels']['facing'][0][1] == -1
    stage = Stage(film, root, 160)
    frames = [stage.frame_array(film['shots'][i], 0.5, 12) for i in (0, 1)]
    assert frames[0].shape == frames[1].shape and (frames[0] != frames[1]).any()
    saved = project.save(root, script, expect_revision=script['revision'])
    assert saved['revision'] == script['revision']+1 and len(json.loads((root/'film.json').read_text(encoding='utf-8'))['shots']) == 4


def first_error(root, script):
    errors = project.check(script, root)
    assert errors
    return errors[0]


def test_scene_errors_have_paths_and_spanish_messages(root):
    script = project.load(root)
    s = copy.deepcopy(script)
    s['shots'][3]['scene'] = 'nada'
    e = first_error(root, s)
    assert e['path'] == 'shots[3].scene' and 'nada' in e['message']

    s = copy.deepcopy(script)
    s['shots'][2]['actors'].append({'id': 'fantasma'})
    e = first_error(root, s)
    assert e['path'] == 'shots[2].actors[1].id' and 'añádelo al reparto de la escena' in e['message']

    s = copy.deepcopy(script)
    s['shots'][0]['props'].append({'id': 'puff'})
    e = first_error(root, s)
    assert e['path'] == 'shots[0].props[0].id' and 'utilería de la escena' in e['message']

    s = copy.deepcopy(script)
    s['shots'][0]['set'] = 'valley'
    assert first_error(root, s)['path'] == 'shots[0].set'

    s = copy.deepcopy(script)
    s['scenes'][0]['cast'][1]['start']['no_existe'] = 1
    assert first_error(root, s)['path'] == 'scenes[0].cast[1].start.no_existe'

    s = copy.deepcopy(script)
    s['scenes'][0]['cast'][1]['character'] = 'nadie'
    assert first_error(root, s)['path'] == 'scenes[0].cast[1].character'

    s = copy.deepcopy(script)
    s['scenes'][0]['props'][0]['prop'] = 'nada'
    assert first_error(root, s)['path'] == 'scenes[0].props[0].prop'

    s = copy.deepcopy(script)
    s['scenes'][0]['set'] = 'nada'
    assert first_error(root, s)['path'] == 'scenes[0].set'
    del s['scenes'][0]['set']
    e = first_error(root, s)
    assert e['path'] == 'scenes[0].set' and 'necesita' in e['message']

    s = copy.deepcopy(script)
    s['shots'][1]['actors'][0]['character'] = 'luma'
    assert first_error(root, s)['path'] == 'shots[1].actors[0].character'


def test_duplicate_ids(root):
    script = project.load(root)
    s = copy.deepcopy(script)
    s['scenes'].append(copy.deepcopy(s['scenes'][0]))
    assert first_error(root, s)['path'] == 'scenes[1].id'
    s = copy.deepcopy(script)
    s['scenes'][0]['cast'].append({'id': 'pip', 'character': 'pip'})
    assert first_error(root, s)['path'] == 'scenes[0].cast[2].id'
    s = copy.deepcopy(script)
    s['scenes'][0]['cast'].append({'id': 'butterfly', 'character': 'pip'})        # cast and props share one namespace
    assert first_error(root, s)['path'] == 'scenes[0].props[0].id'
    s = copy.deepcopy(script)
    s['shots'][1]['actors'].append(copy.deepcopy(s['shots'][1]['actors'][0]))
    assert first_error(root, s)['path'] == 'shots[1].actors[1].id'
    s = copy.deepcopy(script)
    s['shots'][1]['id'] = 's01'
    assert first_error(root, s)['path'] == 'shots[1].id'


def test_several_instances_of_one_character(root):
    script = project.load(root)
    script['scenes'][0]['cast'].append({'id': 'pip2', 'character': 'pip', 'start': {'x': 300, 'y': 690.0, 'scale': 0.4}})
    script['shots'][1]['actors'].append({'id': 'pip2'})
    assert project.check(script, root) == []
    film = project.compile_script(script, root)
    assert [a['id'] for a in film['shots'][1]['actors']] == ['pip', 'pip2']
    assert film['shots'][1]['actors'][1]['character'] == 'pip'


def test_usage_lists_scenes_and_shots(root):
    script = project.load(root)
    paths = {u['path'] for u in project.usage(script, 'characters', 'luma')}
    assert 'scenes[0].cast[1]' in paths and not any(p.startswith('shots') for p in paths)
    assert [u['path'] for u in project.usage(script, 'sets', 'valley')] == ['scenes[0].set']
    assert [u['path'].split('.')[0] for u in project.usage(script, 'props', 'puff')] == ['shots[6]']      # puff_burst in s07
    assert project.usage(script, 'props', 'butterfly')[0]['path'] == 'scenes[0].props[0]'
    assert project.usage(project.expand(script), 'sets', 'valley')[0]['path'] == 'shots[0].set'
