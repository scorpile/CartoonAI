"""MCP server tools, called directly as functions (no protocol). Temporary projects only; skipped without the optional `mcp` package."""
import json
import shutil
import time
from pathlib import Path
import pytest

pytest.importorskip('skia')
pytest.importorskip('mcp')
from celstudio import mcp_server as m
from celstudio.v2 import project

REPO = Path(__file__).resolve().parents[1]
JPEG = bytes([0xff, 0xd8, 0xff])
SHOT = {'id': 's01', 'scene': 'room', 'duration': 1.0, 'actors': [], 'props': [],
        'actions': [{'on': 'shot', 'do': 'cam', 't': 0, 'x': 640, 'y': 360, 'zoom': 1.0}]}


@pytest.fixture()
def projects(tmp_path):
    m.configure(tmp_path, 'en')
    root = project.create_series(tmp_path, 'demo', 'Demo')
    (root/'sets'/'flat.json').write_text(json.dumps({'color': '#e9c48f', 'ground_y': 690.0, 'layers': [], 'post': False}), encoding='utf-8')
    shutil.copyfile(REPO/'projects/tres-osos/characters/papa_oso.json', root/'characters'/'papa_oso.json')
    series = project.load_series(root)
    series['library']['sets']['flat'] = 'sets/flat.json'
    series['library']['characters']['papa'] = 'characters/papa_oso.json'
    project.save_series(root, series, validate=False)
    m.create_episode('demo', 'ep01', 'Pilot')
    return tmp_path


def episode_with_shot():
    got = m.get_script('demo/ep01')
    script = got['script']
    script['scenes'] = [{'id': 'room', 'set': 'flat', 'cast': [], 'props': []}]
    script['shots'] = [json.loads(json.dumps(SHOT))]
    return got['revision'], script


def test_projects_and_episodes(projects):
    listed = m.list_projects()['projects']
    assert [p['id'] for p in listed] == ['demo'] and listed[0]['kind'] == 'series'
    assert m.get_series('demo')['series']['title'] == 'Demo'
    assert [e['id'] for e in m.list_episodes('demo')] == ['ep01']
    assert m.create_series('other', 'Other') == {'series': 'other'}
    assert m.create_episode('other', 'ep02')['project_id'] == 'other/ep02'
    with pytest.raises(ValueError):
        m.create_series('demo')                      # already exists


def test_paths_stay_inside_the_projects_root(projects):
    for bad in ('../x', '..', 'demo/../../x', 'demo/episodes/../../..', 'C:/x', '/etc', 'demo\\ep01', 'a/b/c/d'):
        with pytest.raises(ValueError):
            m.get_script(bad)
    with pytest.raises(ValueError):
        m.create_series('../escape')
    with pytest.raises(ValueError):
        m.get_series('../demo')


def test_script_check_save_and_conflict(projects):
    revision, script = episode_with_shot()
    assert m.check_script('demo/ep01', script)['ok']
    script['shots'][0]['actions'].append({'on': 'nobody', 'do': 'wave', 't0': 0, 't1': 1})
    bad = m.check_script('demo/ep01', script)
    assert not bad['ok'] and bad['errors'][0]['path'].startswith('shots[0].actions[')
    with pytest.raises(ValueError):
        m.save_script('demo/ep01', script, revision)            # invalid: nothing saved
    assert m.get_script('demo/ep01')['revision'] == revision
    script['shots'][0]['actions'].pop()
    saved = m.save_script('demo/ep01', script, revision)
    assert saved['saved'] and saved['revision'] == revision+1 and saved['shots'] == 1
    assert (projects/'demo/episodes/ep01/film.json').is_file()
    with pytest.raises(ValueError, match='(?i)revision'):
        m.save_script('demo/ep01', script, revision)            # stale revision: a human saved in between
    with pytest.raises(ValueError):
        m.save_script('demo/ep01', script, True)
    stored = json.loads((projects/'demo/episodes/ep01/script.json').read_text(encoding='utf-8'))
    assert 'sets' not in stored                                  # the series library is not copied into the episode


def test_get_script_views(projects):
    revision, script = episode_with_shot()
    m.save_script('demo/ep01', script, revision)
    outline = m.get_script('demo/ep01', summary=True)['summary']
    assert outline['shots'][0]['id'] == 's01' and outline['shots'][0]['actions'] == 1
    assert m.get_script('demo/ep01', shot_id='s01')['shot']['id'] == 's01'
    with pytest.raises(ValueError):
        m.get_script('demo/ep01', shot_id='nope')


def test_apply_actions(projects):
    revision, script = episode_with_shot()
    revision = m.save_script('demo/ep01', script, revision)['revision']
    out = m.apply_actions('demo/ep01', 's01', [{'on': 'shot', 'do': 'fade_in', 'dur': .5}], expected_revision=revision)
    assert out['actions_in_shot'] == 2
    with pytest.raises(ValueError):
        m.apply_actions('demo/ep01', 's01', [{'on': 'ghost', 'do': 'wave', 't0': 0, 't1': 1}])
    assert len(m.get_script('demo/ep01', shot_id='s01')['shot']['actions']) == 2     # the invalid one was not saved
    with pytest.raises(ValueError, match='(?i)revision'):
        m.apply_actions('demo/ep01', 's01', [], expected_revision=revision)
    assert m.apply_actions('demo/ep01', 's01', [], mode='replace')['actions_in_shot'] == 0
    with pytest.raises(ValueError):
        m.apply_actions('demo/ep01', 's01', [], mode='explode')


def test_library_character_and_verbs(projects):
    found = m.library('demo', 'papa')
    assert found['total'] == 1 and found['items'][0]['id'] == 'papa' and found['items'][0]['uses'] == 0
    assert m.library('demo', kind='sets')['counts']['sets'] == 1
    with pytest.raises(ValueError):
        m.library('demo', kind='nope')
    info = m.character_info('demo', 'papa')
    assert {'front', '3q', 'profile'} <= set(info['head_views']) and 'tenedor' in info['items'] and 'babero' in info['wear']
    assert 'smile' in info['channels']
    with pytest.raises(ValueError):
        m.character_info('demo', 'missing')
    verbs = m.list_verbs()
    assert {'actor', 'prop', 'shot'} <= set(verbs['verbs']) and any(v['name'] == 'walk' for v in verbs['verbs']['actor'])
    assert set(m.list_verbs('shot')['verbs']) == {'shot'}


def test_images(projects):
    revision, script = episode_with_shot()
    m.save_script('demo/ep01', script, revision)
    frame = m.render_frame('demo/ep01', 's01', 0.5, 320)
    assert frame.data[:3] == JPEG and frame._mime_type == 'image/jpeg'
    sheet = m.contact_sheet('demo/ep01', ['s01'], columns=2, width=200, frames_per_shot=2)
    assert sheet.data[:3] == JPEG
    with pytest.raises(ValueError):
        m.render_frame('demo/ep01', 'nope', 0, 320)
    with pytest.raises(ValueError):
        m.render_frame('demo/ep01', 's01', 0, 99999)
    with pytest.raises(ValueError):
        m.contact_sheet('demo/ep01', ['nope'])


def test_render_job(projects):
    revision, script = episode_with_shot()
    m.save_script('demo/ep01', script, revision)
    with pytest.raises(ValueError):
        m.render_status('missing')
    if shutil.which('ffmpeg') is None:
        pytest.skip('FFmpeg not installed')
    with pytest.raises(ValueError):
        m.render_video('demo/ep01', 'nope')
    job = m.render_video('demo/ep01', width=320)
    for _ in range(240):
        status = m.render_status(job['job_id'])
        if status['status'] != 'running':
            break
        time.sleep(.5)
    assert status['status'] == 'done', status
    assert status['file_exists'] and Path(status['file']).parent == projects/'demo/episodes/ep01/renders'


def test_spanish_messages(projects):
    m.configure(projects, 'es')
    try:
        with pytest.raises(ValueError, match='existe'):
            m.create_series('demo')
    finally:
        m.configure(projects, 'en')


def test_server_registers_every_tool(projects):
    import asyncio
    result = m.build_server().list_tools()
    result = asyncio.run(result) if asyncio.iscoroutine(result) else result
    names = {t.name for t in getattr(result, 'tools', result)}
    assert names == {f.__name__ for f in m.TOOLS}
