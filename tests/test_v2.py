"""Engine v2: easing tracks, IK, deterministic frames from the v3 pilot film."""
import math
from pathlib import Path
import pytest

skia = pytest.importorskip('skia')
from celstudio.v2.anim import Track, EASES
from celstudio.v2.puppet import ik
from celstudio.v2.stage import Stage, load_film, frame_count

FILM = Path(__file__).resolve().parents[1]/'projects/taller-v3/film.json'


def test_track_easing_and_holds():
    track = Track([[0, 0], [1, 10, 'linear'], [2, 10], [3, 0, 'back']])
    assert track.at(-1) == 0 and track.at(.5) == 5 and track.at(1.5) == 10 and track.at(9) == 0
    assert min(track.at(2+i/50) for i in range(51)) < 0          # 'back' overshoots past the target
    assert Track([[0, 'a'], [1, 'b']]).at(.99) == 'a'             # discrete values step
    for name, ease in EASES.items():
        assert abs(ease(0)) < 1e-6 and abs(ease(1)-1) < 1e-6, name


def test_ik_reaches_target_and_stretches_only_when_needed():
    mid, end = ik((0, 0), (30, 40), 30, 30, 1)
    assert end == pytest.approx((30, 40))
    assert math.hypot(*mid) == pytest.approx(30)
    mid, end = ik((0, 0), (0, 200), 30, 30, 1)
    assert math.hypot(*end) == pytest.approx(60*1.18)             # clamped rubber-hose stretch


@pytest.mark.skipif(not FILM.exists(), reason='pilot film not built')
def test_pilot_frames_are_deterministic_and_complete():
    film, root = load_film(FILM)
    assert sum(frame_count(s, film['fps']) for s in film['shots']) == round(sum(s['duration'] for s in film['shots'])*film['fps'])
    shot = next(s for s in film['shots'] if s['id'] == 's07')
    first = Stage(film, root, 320).frame_array(shot, 2.6, 7)
    second = Stage(film, root, 320).frame_array(shot, 2.6, 7)   # fresh stage, random access
    assert first.shape == (180, 320, 4) and (first == second).all()
    assert first[..., :3].std() > 20 and first[-1].mean() > 20    # not blank, no dead bottom rows
    other = Stage(film, root, 320).frame_array(shot, 2.0, 7)
    assert (first != other).any()


# -- script.json -> film.json (project layer) --
from celstudio.v2 import project  # noqa: E402

PROJECT = Path(__file__).resolve().parents[1]/'projects/taller-v3'


@pytest.fixture
def temp_project(tmp_path):
    import shutil
    target = tmp_path/'taller'
    shutil.copytree(PROJECT, target, ignore=shutil.ignore_patterns('renders'))
    return target


@pytest.mark.skipif(not (PROJECT/'script.json').exists(), reason='pilot script not built')
def test_script_compiles_to_the_pilot_film():
    import json
    compiled = project.compile_script(project.load(PROJECT), PROJECT)
    assert json.loads(json.dumps(compiled)) == json.loads((PROJECT/'film.json').read_text(encoding='utf-8'))


def test_check_reports_unknown_verb_with_path(temp_project):
    script = project.load(temp_project)
    script['shots'][2]['actions'][4]['do'] = 'bailar'
    errors = project.check(script, temp_project)
    assert errors and errors[0]['path'] == 'shots[2].actions[4]' and 'bailar' in errors[0]['message']
    assert project.check(project.load(temp_project), temp_project) == []
    with pytest.raises(project.ScriptError) as info:
        project.compile_script(script, temp_project)
    assert info.value.path == 'shots[2].actions[4]'


def test_check_reports_bad_arguments(temp_project):
    script = project.load(temp_project)
    walk = next(a for a in script['shots'][0]['actions'] if a['do'] == 'walk')
    walk['t0'] = 'pronto'
    walk['velocidad'] = 3
    del walk['x1']
    messages = ' | '.join(e['message'] for e in project.check(script, temp_project))
    assert 'x1' in messages and 'velocidad' in messages and 't0' in messages
    script = project.load(temp_project)
    script['shots'][0]['actors'][0]['start']['no_existe'] = 1
    assert 'no_existe' in project.check(script, temp_project)[0]['message']


def test_catalogue_lists_walk_with_parameters():
    cat = project.catalogue()
    walk = next(v for v in cat['verbs']['actor'] if v['name'] == 'walk')
    params = {p['name']: p for p in walk['params']}
    assert params['t0']['required'] and params['step']['default'] == 46 and not walk['kwargs']
    assert any(v['name'] == 'to' and v['kwargs'] for v in cat['verbs']['actor'])
    assert {'path', 'flap', 'perch'} <= {v['name'] for v in cat['verbs']['prop']}
    assert {'cam', 'puff_burst'} <= {v['name'] for v in cat['verbs']['shot']}
    assert 'arm_l_x' in cat['channels'] and 'happy' in cat['expressions'] and 'inout' in cat['eases']


def test_save_bumps_revision_and_keeps_previous(temp_project):
    import json
    script = project.load(temp_project)
    old = script['revision']
    saved = project.save(temp_project, script, expect_revision=old)
    assert saved['revision'] == old+1 and project.load(temp_project)['revision'] == old+1
    assert json.loads((temp_project/'script.previous.json').read_text(encoding='utf-8'))['revision'] == old
    assert json.loads((temp_project/'film.json').read_text(encoding='utf-8'))['shots']
    with pytest.raises(project.ScriptError):
        project.save(temp_project, script, expect_revision=old)      # stale revision
