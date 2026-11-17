"""MCP server for Cel Studio: lets any MCP client (Claude Code, Codex, Claude Desktop...) read and edit projects, look at frames
and start renders. It only wraps `celstudio.v2.project`, `celstudio.v2.api.Service` and `celstudio.v2.stage`; it adds no logic
of its own, makes no network calls and calls no LLM.

Run it over stdio:  python -m celstudio.mcp [--projects DIR] [--lang es|en]
The `mcp` package is an optional dependency (requirements-mcp.txt); this module imports without it, `main()` needs it.

The tool functions below are plain Python functions (the tests call them directly); `build_server()` registers them.
Every project id is validated (letters, digits, `-`, `_`) and resolved inside the projects root, so nothing outside it is reachable.
"""
import argparse
import functools
import json
import os
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Optional

from .v2 import i18n, project
from .v2.api import Service
from .v2.project import ScriptError

REPO = Path(__file__).resolve().parents[1]
MAX_TILES = 30          # contact sheet: frames per call
MAX_SHEET_PIXELS = 4096*4096

_state = {'projects': None, 'lang': 'en', 'service': None}
_jobs = {}
_jobs_lock = threading.Lock()


# ---------------------------------------------------------------- configuration and helpers
def configure(projects=None, lang='en'):
    """Set the projects root (default: $CELSTUDIO_PROJECTS or <repo>/projects) and the language of messages (es|en)."""
    root = Path(projects or os.environ.get('CELSTUDIO_PROJECTS') or REPO/'projects').expanduser().resolve()
    if lang not in i18n.LANGS:
        raise ValueError(f'lang must be one of {", ".join(i18n.LANGS)}')
    _state.update(projects=root, lang=lang, service=Service(root))
    return root


def _svc():
    if _state['service'] is None:
        configure()
    return _state['service']


def _error(exc):
    """ValueError with the message of `exc` in the configured language (and the script path when there is one)."""
    text = i18n.render(exc, _state['lang'])
    path = getattr(exc, 'path', '') or (getattr(exc, 'payload', None) or {}).get('path', '')
    errors = (getattr(exc, 'payload', None) or {}).get('errors') or []
    text = f'{path}: {text}' if path else text
    if errors:
        text += '\n' + '\n'.join(f"- {e.get('path') or '(global)'}: {i18n.render(e.get('message', ''), _state['lang'])}" for e in errors[:20])
    return ValueError(text)


def _pid(project_id):
    """Project id of a film ("taller-v3") or an episode ("serie/ep01" or "serie/episodes/ep01") in the form the Service uses."""
    parts = [p for p in str(project_id).strip().strip('/').split('/') if p]
    if len(parts) == 2:
        parts.insert(1, 'episodes')
    return '/'.join(parts)


def _home(project_id):
    """Folder of a film or an episode; raises ValueError if it does not exist or leaves the projects root."""
    svc = _svc()
    try:
        pid = _pid(project_id)
        home = svc.home(pid)
    except (ScriptError, ValueError) as e:
        raise _error(e) from None
    if svc.projects not in home.resolve().parents:
        raise ValueError('project outside the projects root')
    return pid, home


def _series_dir(series_id):
    try:
        return _svc().series_dir(series_id)
    except ValueError as e:
        raise _error(e) from None


def _localized(value):
    return i18n.localize(value, _state['lang'])


def _image(data, fmt='jpeg'):
    """MCP image content (mcp 2.x: mcp.server.mcpserver; mcp 1.x: mcp.server.fastmcp)."""
    try:
        from mcp.server.mcpserver import Image
    except ImportError:
        from mcp.server.fastmcp import Image
    return Image(data=data, format=fmt)


def _ensure_film(home):
    """film.json up to date (compiled again when missing or older than the script or the series)."""
    film = home/'film.json'
    sources = [home/'script.json'] + ([project.series_root(home)/'series.json'] if project.series_root(home) else [])
    if not film.is_file() or film.stat().st_mtime < max(s.stat().st_mtime for s in sources):
        try:
            project.compile_project(home)
        except ScriptError as e:
            raise _error(e) from None


# ---------------------------------------------------------------- projects, series, episodes
def list_projects() -> dict:
    """List what exists under the projects root: standalone films and series (id, kind, title, episode/shot counts, seconds, revision)."""
    return {'projects_root': str(_svc().projects), 'projects': _localized(_svc().films_list())}


def get_series(series_id: str) -> dict:
    """Series metadata (title, notes, bible, style, fps, size, references, revision), its episodes and library counts."""
    _series_dir(series_id)
    return _localized(_svc().series(series_id))


def list_episodes(series_id: str) -> list:
    """Episodes of a series: id, title, scenes, shots, seconds, revision. Project id of an episode is "<series>/<episode>"."""
    return _localized(project.episode_info(_series_dir(series_id)))


def create_series(series_id: str, title: str = '') -> dict:
    """Create an empty series (shared library, no episodes). `series_id` uses letters, digits, '-' and '_'."""
    try:
        with _svc().lock:
            project.create_series(_svc().projects, series_id, title)
    except ValueError as e:
        raise _error(e) from None
    return {'series': series_id}


def create_episode(series_id: str, episode_id: str, title: str = '') -> dict:
    """Create an empty episode in a series. Returns its project id ("<series>/<episode>") for the other tools."""
    root = _series_dir(series_id)
    try:
        with _svc().lock:
            project.create_episode(root, episode_id, title)
    except ValueError as e:
        raise _error(e) from None
    return {'project_id': f'{series_id}/{episode_id}'}


# ---------------------------------------------------------------- script
def get_script(project_id: str, shot_id: Optional[str] = None, summary: bool = False) -> dict:
    """Script of a film or an episode (for an episode: the effective script, with the series library merged in).
    Returns {revision, script, errors}. Pass `summary=True` for a compact outline (scenes, shots with duration and action count)
    or `shot_id` for one shot only. Keep `revision`: save_script needs it."""
    _, home = _home(project_id)
    try:
        script = project.load(home)
    except ScriptError as e:
        raise _error(e) from None
    out = {'revision': script.get('revision', 0)}
    if summary:
        out['summary'] = {'title': script.get('title'), 'fps': script.get('fps'), 'size': [script.get('width'), script.get('height')],
                          'characters': sorted(script.get('characters') or {}), 'sets': sorted(script.get('sets') or {}),
                          'props': sorted(script.get('props') or {}),
                          'scenes': [{'id': s.get('id'), 'set': s.get('set'), 'cast': [c.get('id') for c in s.get('cast', [])]}
                                     for s in script.get('scenes', []) if isinstance(s, dict)],
                          'shots': [{'id': s.get('id'), 'scene': s.get('scene'), 'duration': s.get('duration'),
                                     'actions': len(s.get('actions', [])), 'description': s.get('description', '')}
                                    for s in script.get('shots', []) if isinstance(s, dict)]}
    elif shot_id:
        shot = next((s for s in script.get('shots', []) if isinstance(s, dict) and s.get('id') == shot_id), None)
        if shot is None:
            raise ValueError(f'unknown shot {shot_id!r}; shots: {[s.get("id") for s in script.get("shots", []) if isinstance(s, dict)]}')
        out['shot'] = shot
    else:
        out['script'] = script
    out['errors'] = _localized(project.check(script, home))
    return out


def check_script(project_id: str, script: Optional[dict[str, Any]] = None) -> dict:
    """Validate a script without saving. Without `script`, the saved one is checked. Returns {ok, errors: [{path, message}], warnings}.
    Paths look like "shots[2].actions[14]". Passing validation does not mean the result looks good: render a frame."""
    _, home = _home(project_id)
    try:
        if script is None:
            script = project.load(home)
        errors = project.check(script, home)
        warnings = project.warnings(script, home)
    except ScriptError as e:
        raise _error(e) from None
    return {'ok': not errors, 'errors': _localized(errors), 'warnings': _localized(warnings)}


def save_script(project_id: str, script: dict[str, Any], expected_revision: int) -> dict:
    """Validate, save and compile a script (film.json). `expected_revision` must be the revision you read with get_script; if a human
    saved in between, the call fails with a revision conflict instead of overwriting their edits (read again and merge).
    The script `id` cannot change. For an episode pass the effective script returned by get_script."""
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int):
        raise ValueError('expected_revision must be an integer (the revision returned by get_script)')
    pid, _ = _home(project_id)
    try:
        saved = _svc().save(pid, dict(script, revision=expected_revision))['script']
    except ValueError as e:
        raise _error(e) from None
    shots = [s for s in saved.get('shots', []) if isinstance(s, dict)]
    return {'saved': True, 'revision': saved['revision'], 'shots': len(shots),
            'seconds': round(sum(s.get('duration', 0) for s in shots if isinstance(s.get('duration'), (int, float))), 3)}


def apply_actions(project_id: str, shot_id: str, actions: list[dict[str, Any]], mode: str = 'append',
                  expected_revision: Optional[int] = None) -> dict:
    """Add or replace the ordered actions of ONE shot, then validate, save and compile. mode: 'append' (add to the end) or
    'replace' (replace the whole list). Each action is an object such as {"on": "luma", "do": "wave", "t0": 1.0, "t1": 2.5}
    (see list_verbs). If anything is invalid nothing is saved and the error names the path. Pass `expected_revision`
    (from get_script) to detect concurrent edits."""
    if mode not in ('append', 'replace'):
        raise ValueError("mode must be 'append' or 'replace'")
    if not isinstance(actions, list) or not all(isinstance(a, dict) for a in actions):
        raise ValueError('actions must be a list of objects')
    pid, home = _home(project_id)
    with _svc().lock:
        try:
            script = project.load(home)
            shot = next((s for s in script.get('shots', []) if isinstance(s, dict) and s.get('id') == shot_id), None)
            if shot is None:
                raise ValueError(f'unknown shot {shot_id!r}')
            shot['actions'] = (list(shot.get('actions', [])) if mode == 'append' else []) + actions
            current = script.get('revision', 0)
            saved = project.save(home, script, expect_revision=current if expected_revision is None else expected_revision)
        except ScriptError as e:
            err = _error(e)
            try:
                errors = project.check(script, home)
            except Exception:
                errors = []
            raise _error_with(err, errors) from None
        except ValueError as e:
            raise _error(e) from None
    shot = next(s for s in saved['shots'] if s.get('id') == shot_id)
    return {'saved': True, 'revision': saved['revision'], 'actions_in_shot': len(shot['actions'])}


def _error_with(err, errors):
    lines = [f"- {e['path'] or '(global)'}: {i18n.render(e['message'], _state['lang'])}" for e in errors[:20]]
    return ValueError(str(err) + ('\n' + '\n'.join(lines) if lines else ''))


# ---------------------------------------------------------------- library and catalogue
def library(series_id: str, query: str = '', kind: Optional[str] = None, used: Optional[bool] = None,
            episode: Optional[str] = None, limit: int = 100) -> dict:
    """Search the series library (characters, sets, props) with usage. `query` matches id and name; `kind` is
    'characters', 'sets' or 'props'; `used` keeps used/unused items; `episode` keeps items that episode uses.
    Returns {items: [{kind, id, name, file, episodes, uses}], total, counts}."""
    if kind not in (None, 'characters', 'sets', 'props'):
        raise ValueError("kind must be 'characters', 'sets' or 'props'")
    root = _series_dir(series_id)
    return project.library_catalogue(root, query, kind, used, episode, max(1, min(int(limit), 500)), 0)


def character_info(project_id: str, character_id: str) -> dict:
    """What a character rig offers: head views, hand poses (and whether a back-of-hand exists), held items, wearable garments,
    boots, torso views, appendages, default channels and the channels you can animate. `project_id` may be a series id,
    an episode ("serie/ep01") or a film. If the art you need is missing, say so instead of inventing it."""
    svc = _svc()
    try:
        root, script = svc.context(_pid(project_id))
        rig = json.loads(svc.declared(root, 'characters', character_id, script).read_text(encoding='utf-8'))
    except (ScriptError, ValueError, OSError) as e:
        raise _error(e) from None
    head = rig.get('head', {}) if isinstance(rig.get('head'), dict) else {}
    hands = rig.get('hands', {}) if isinstance(rig.get('hands'), dict) else {}
    torso = rig.get('torso', {}) if isinstance(rig.get('torso'), dict) else {}
    cat = project.catalogue()
    return {'id': character_id, 'name': rig.get('name', ''), 'colors': rig.get('colors', {}),
            'head_views': sorted(head), 'torso_views': ['front'] + (['profile'] if 'profile' in torso else []),
            'appendages': {v: [a.get('name') for a in d['appendages'] if isinstance(a, dict)] for v, d in head.items()
                           if isinstance(d, dict) and isinstance(d.get('appendages'), list)},
            'hands': {n: {'back_of_hand': isinstance(h, dict) and 'back' in h} for n, h in hands.items()},
            'boots': sorted(rig.get('boots', {})), 'items': sorted(rig.get('items', {})), 'wear': {
                n: sorted(v) for n, v in (rig.get('wear') or {}).items() if isinstance(v, dict)},
            'defaults': rig.get('defaults', {}), 'channels': sorted(cat['channels']), 'expressions': cat['expressions']}


def list_verbs(kind: Optional[str] = None) -> dict:
    """Animation verbs and their parameters, generated from the engine. `kind`: 'actor' (acts on a character, "on": its id),
    'prop' or 'shot' ("on": "shot", for camera and fades). Also lists expression names and easing names.
    Each verb: {name, doc, params: [{name, required|default|varargs}]}. Times are in seconds from the start of the shot."""
    cat = project.catalogue()
    if kind is not None and kind not in cat['verbs']:
        raise ValueError(f"kind must be one of {', '.join(cat['verbs'])}")
    return {'verbs': {k: v for k, v in cat['verbs'].items() if kind in (None, k)}, 'expressions': cat['expressions'], 'eases': cat['eases']}


# ---------------------------------------------------------------- images
def render_frame(project_id: str, shot_id: str, time: float = 0.0, width: int = 960):
    """Render one frame of a shot (at `time` seconds into the shot) and return it as an image. Deterministic: same input, same pixels.
    `width` 160-1280 (default 960). The compiled film is refreshed first if the script changed."""
    pid, home = _home(project_id)
    _ensure_film(home)
    svc = _svc()
    try:
        return _image(svc.frame(pid, shot_id, time, width))
    except (ScriptError, ValueError, OSError) as e:
        raise _error(e) from None


def contact_sheet(project_id: str, shot_ids: Optional[list[str]] = None, columns: int = 3, width: int = 320, frames_per_shot: int = 3):
    """Contact sheet: `frames_per_shot` evenly spaced frames of each selected shot (all shots if `shot_ids` is empty), labelled with
    shot id and time, as one image. Use it to review staging and motion before approving a shot. Limited to 30 frames per call."""
    from .v2.stage import contact_sheet as sheet, load_film
    import skia
    _, home = _home(project_id)
    _ensure_film(home)
    if not 160 <= width <= 960 or not 1 <= columns <= 8 or not 1 <= frames_per_shot <= 12:
        raise ValueError('width must be 160-960, columns 1-8, frames_per_shot 1-12')
    try:
        film, root = load_film(home/'film.json')
        known = [s['id'] for s in film['shots']]
        wanted = list(shot_ids or [])
        missing = [s for s in wanted if s not in known]
        if missing:
            raise ValueError(f'unknown shots {missing}; shots: {known}')
        tiles = (len(wanted) or len(known))*frames_per_shot
        height = film['height']*width/film['width']
        if tiles > MAX_TILES or columns*width*(-(-tiles//columns))*height > MAX_SHEET_PIXELS:
            raise ValueError(f'too many frames ({tiles}); select fewer shots or lower frames_per_shot (max {MAX_TILES})')
        with _svc().render_lock:
            image = sheet(film, root, wanted or None, columns, width, 0.0, frames_per_shot)
            data = bytes(image.encodeToData(skia.kJPEG, 85))
    except (ScriptError, OSError) as e:
        raise _error(e) from None
    return _image(data)


# ---------------------------------------------------------------- video (long running)
def render_video(project_id: str, shot_id: Optional[str] = None, width: Optional[int] = None) -> dict:
    """Start rendering an MP4 in the background (all shots, or one `shot_id`; `width` 160-3840, default the film's own). Returns a
    `job_id` right away: poll render_status. Needs FFmpeg. The file goes to the project's renders/ folder."""
    from .v2.stage import render_film
    pid, home = _home(project_id)
    if shutil.which('ffmpeg') is None:
        raise ValueError('FFmpeg was not found on PATH (see docs/en/INSTALL.md)')
    if width is not None and (isinstance(width, bool) or not isinstance(width, int) or not 160 <= width <= 3840):
        raise ValueError('width must be an integer between 160 and 3840')
    try:
        script = project.load(home)
        ids = [s.get('id') for s in script.get('shots', []) if isinstance(s, dict)]
        if shot_id is not None and shot_id not in ids:
            raise ValueError(f'unknown shot {shot_id!r}; shots: {ids}')
        if not ids:
            raise ValueError('the script has no shots')
        project.compile_project(home)           # fail now, with a clear message, rather than inside the job
    except ValueError as e:
        raise _error(e) from None
    jid = uuid.uuid4().hex[:8]
    destination = home/'renders'/f'{jid}-{shot_id or "pelicula"}.mp4'
    job = {'job_id': jid, 'project_id': project_id, 'shot': shot_id, 'status': 'running', 'done': 0, 'total': len(ids) if shot_id is None else 1,
           'message': '', 'file': str(destination), 'relative_file': destination.relative_to(_svc().projects).as_posix(),
           'started': time.time(), 'seconds': None}
    with _jobs_lock:
        _jobs[jid] = job

    def progress(done, total, message):
        job.update(done=done, total=total, message=message)

    def work():
        try:
            (home/'renders').mkdir(exist_ok=True)
            result = render_film(home/'film.json', destination, width, [shot_id] if shot_id else None, None, None, 20, progress)
            job.update(status='done', seconds=result['seconds'], frames=result['frames'], done=job['total'])
        except BaseException as e:               # the job must always end in a state the client can read
            job.update(status='error', error=str(i18n.render(e, _state['lang'])) or type(e).__name__)
        finally:
            parts = destination.with_name(destination.stem+'.parts')
            shutil.rmtree(parts, ignore_errors=True)
            job['finished'] = time.time()
    threading.Thread(target=work, name=f'render-{jid}', daemon=True).start()
    return {'job_id': jid, 'status': 'running', 'file': job['file']}


def render_status(job_id: str) -> dict:
    """State of a render started with render_video: status (running|done|error), progress (shots done/total), output file, error."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise ValueError(f'unknown job {job_id!r}; known jobs: {sorted(_jobs)}')
    out = {k: v for k, v in job.items() if k not in ('started', 'finished')}
    out['elapsed_s'] = round((job.get('finished') or time.time()) - job['started'], 1)
    out['file_exists'] = Path(job['file']).is_file()
    return out


TOOLS = (list_projects, get_series, list_episodes, create_series, create_episode, get_script, check_script, save_script, apply_actions,
         library, character_info, list_verbs, render_frame, contact_sheet, render_video, render_status)

INSTRUCTIONS = (
    'Cel Studio: 2D cut-out animation as data. A film is a script.json (library -> scenes -> shots -> ordered actions) rendered '
    'deterministically; art is generated once per resource, never per frame. Workflow: list_projects, get_script(summary=True), '
    'list_verbs and character_info before writing actions, check_script, save_script (with expected_revision) or apply_actions, '
    'then render_frame / contact_sheet to look at the result. Project ids: "<film>" or "<series>/<episode>". '
    'If the catalogue cannot express an action, list the missing art, pose or rig instead of inventing paths.')


def build_server():
    """FastMCP-style server with every tool registered (needs the optional `mcp` package)."""
    try:
        from mcp.server.mcpserver import MCPServer as Server
    except ImportError:
        try:
            from mcp.server.fastmcp import FastMCP as Server
        except ImportError:
            raise SystemExit('The MCP server needs the optional "mcp" package: python -m pip install -r requirements-mcp.txt') from None
    try:
        from mcp.server.mcpserver.exceptions import ToolError
    except ImportError:
        from mcp.server.fastmcp.exceptions import ToolError
    server = Server('cel-studio', instructions=INSTRUCTIONS)
    for fn in TOOLS:
        server.tool()(_reporting(fn, ToolError))
    return server


def _reporting(fn, tool_error):
    """Wrap a tool so that its ValueError (bad input, validation, conflict) reaches the client as a readable tool error
    (the SDK hides the text of unexpected exceptions)."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ValueError as error:
            raise tool_error(str(error)) from None
    return wrapper


def main(argv=None):
    parser = argparse.ArgumentParser(prog='python -m celstudio.mcp', description='Cel Studio MCP server (stdio).')
    parser.add_argument('--projects', help='projects root (default: $CELSTUDIO_PROJECTS or <repo>/projects)')
    parser.add_argument('--lang', choices=i18n.LANGS, default='en', help='language of messages (default: en)')
    args = parser.parse_args(argv)
    configure(args.projects, args.lang)
    build_server().run('stdio')
