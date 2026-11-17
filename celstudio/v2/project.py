"""Project layer: script.json (declarative screenplay, source of truth) -> film.json (compiled keyframes).

Pure and deterministic: no engine code runs here except the authoring verbs of direct.py.
"""
import copy
import inspect
import json
import math
import os
import shutil
import time
from pathlib import Path
from .anim import EASES
from .i18n import join as join_msgs, msg
from .direct import EXPRESSIONS, Film, Prop, Shot, Take, call_verb
from .puppet import DEFAULTS

VERB_CLASSES = {'actor': Take, 'prop': Prop, 'shot': Shot}
TIME_PARAMS = ('t', 't0', 't1')
EASE_PARAMS = ('ease', 'back')
RIG_CHANNELS = ('arm_l_x', 'arm_l_y', 'arm_r_x', 'arm_r_y', 'foot_l_x', 'foot_r_x')   # derived from the rig in Take.__init__


class ScriptError(ValueError):
    """Invalid script. `path` locates the problem (e.g. "shots[2].actions[14]"), '' when global."""

    def __init__(self, message, path=''):
        super().__init__(message)
        self.path = path


LIBRARY = ('characters', 'sets', 'props')
INHERITED = ('fps', 'width', 'height', 'style', 'bible')   # an episode that lacks them takes the series' values


def _read_json(path, what):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        raise ScriptError(msg('p.no_existe_en', name=Path(path).name, parent=Path(path).parent)) from None
    except json.JSONDecodeError as e:
        raise ScriptError(msg('p.no_es_json_valido', name=Path(path).name, e=e)) from None


def normalize(path):
    """Project folder of `path`, which may be the folder itself or its script.json / film.json."""
    path = Path(path)
    return path.parent if path.name in ('script.json', 'film.json') else path


def series_root(home):
    """Series folder when `home` is an episode folder (projects/<serie>/episodes/<ep>), else None."""
    home = Path(home)
    root = home.parent.parent
    return root if home.parent.name == 'episodes' and (root/'series.json').is_file() else None


def asset_root(home):
    """Folder that every asset path of the project is relative to: the series root for an episode, else `home`."""
    return series_root(home) or Path(home)


def is_series(root):
    return (Path(root)/'series.json').is_file()


def load_series(root):
    return _read_json(Path(root)/'series.json', 'la serie')


def library_of(series):
    lib = series.get('library', {})
    return {k: (lib.get(k) if isinstance(lib.get(k), dict) else {}) for k in LIBRARY}


def effective(series, script):
    """Script of an episode as the compiler sees it: the series library plus the episode's own local items (local wins),
    the series references before the episode's, and the series' defaults for fps, size, style and bible."""
    out = dict(script)
    lib = library_of(series)
    for kind in LIBRARY:
        local = script.get(kind, {})
        out[kind] = {**lib[kind], **(local if isinstance(local, dict) else {})}
    own = script.get('references', [])
    inherited = series.get('references', [])
    own = own if isinstance(own, list) else []
    taken = {r.get('id') for r in inherited if isinstance(r, dict)}
    out['references'] = list(inherited)+[r for r in own if not (isinstance(r, dict) and r.get('id') in taken)]
    for key in INHERITED:
        if key not in out and key in series:
            out[key] = copy.deepcopy(series[key])
    return out


def _strip(series, script, stored):
    """Inverse of `effective` for saving: only the episode's own items go to the episode's script.json."""
    out = dict(script)
    lib = library_of(series)
    for kind in LIBRARY:
        own = stored.get(kind, {}) if isinstance(stored.get(kind, {}), dict) else {}
        local = {k: v for k, v in (script.get(kind) or {}).items() if k not in lib[kind] or k in own}
        if local:
            out[kind] = local
        else:
            out.pop(kind, None)
    taken = {r.get('id') for r in series.get('references', []) if isinstance(r, dict)}
    out['references'] = [r for r in script.get('references', []) if not (isinstance(r, dict) and r.get('id') in taken)]
    for key in INHERITED:
        if key not in stored and key in series and out.get(key) == series[key]:
            out.pop(key, None)
    return out


def load(root):
    """Script of a project folder. For an episode it is the effective script (series library merged in)."""
    root = normalize(root)
    script = _read_json(root/'script.json', '')
    sroot = series_root(root)
    if sroot is not None and isinstance(script, dict):
        return effective(load_series(sroot), script)
    return script


def load_raw(root):
    """script.json exactly as stored (an episode without the series library)."""
    return _read_json(normalize(root)/'script.json', '')


def warnings(script, root):
    """Non-fatal notes: episode-local items that shadow an item of the series library."""
    sroot = series_root(root)
    if sroot is None:
        return []
    try:
        raw, lib = load_raw(root), library_of(load_series(sroot))
    except ScriptError:
        return []
    return [{'path': f'{kind}.{k}', 'message': msg('p.es_local_del_capitulo_y', k=k)}
            for kind in LIBRARY for k in (raw.get(kind) or {}) if k in lib[kind]]


def verbs_of(cls):
    return {name: fn for name, fn in inspect.getmembers(cls, inspect.isfunction) if getattr(fn, 'verb', False)}


def _params(fn):
    return list(inspect.signature(fn).parameters.values())[1:]


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _read(root, rel, path, errors, what):
    """Parsed JSON of a project file, or None after recording an error."""
    if not isinstance(rel, str) or not rel:
        errors.append(ScriptError(msg('p.la_ruta_de_debe_ser', what=what), path))
        return None
    file = (root/rel).resolve()
    if root.resolve() not in file.parents:
        errors.append(ScriptError(msg('p.la_ruta_de_sale_del', what=what, rel=rel), path))
    elif not file.is_file():
        errors.append(ScriptError(msg('p.falta_el_archivo_de', what=what, rel=rel), path))
    else:
        try:
            return json.loads(file.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            errors.append(ScriptError(msg('p.el_archivo_no_es_json', rel=rel, e=e), path))
    return None


def _asset(root, rel, path, errors):
    if isinstance(rel, str) and not (root/rel).is_file():
        errors.append(ScriptError(msg('p.falta_la_imagen', rel=rel), path))


def _check_args(kind, name, fn, action, path, target, shot_props, errors):
    """Validate one action's arguments without running it. Returns True when it is safe to replay."""
    start = len(errors)
    params = _params(fn)
    named = {p.name: p for p in params if p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)}
    var = next((p for p in params if p.kind is p.VAR_POSITIONAL), None)
    takes_kwargs = any(p.kind is p.VAR_KEYWORD for p in params)
    args = {k: v for k, v in action.items() if k not in ('on', 'do')}
    for p in named.values():
        if p.default is p.empty and p.name not in args:
            errors.append(ScriptError(msg('p.falta_el_argumento_obligatorio_de', name=p.name, name2=name), path))
    extras = [k for k in args if k not in named and not (var and k == var.name)]
    if extras and not takes_kwargs:
        for k in extras:
            errors.append(ScriptError(msg('p.argumento_inesperado_en', k=k, name=name), f'{path}.{k}'))
    if var and var.name in args and not isinstance(args[var.name], list):
        errors.append(ScriptError(msg('p.debe_ser_una_lista', name=var.name), f'{path}.{var.name}'))
    for k in TIME_PARAMS:
        if k in named and k in args and not _number(args[k]):
            errors.append(ScriptError(msg('p.el_tiempo_debe_ser_un', k=k, a=args[k]), f'{path}.{k}'))
    if var and isinstance(args.get(var.name), list):
        for n, v in enumerate(args[var.name]):
            if var.name == 'times' and not _number(v):
                errors.append(ScriptError(msg('p.el_tiempo_debe_ser_un_2', v=v), f'{path}.{var.name}[{n}]'))
    for k in EASE_PARAMS:
        if k in named and isinstance(args.get(k), str) and args[k] not in EASES:
            errors.append(ScriptError(msg('p.curva_desconocida_usa_una_de', a=args[k], a2=", ".join(EASES)), f'{path}.{k}'))
    if kind == 'actor':
        channels = target.defaults
        if name == 'key' and isinstance(args.get('channel'), str) and args['channel'] not in channels:
            errors.append(ScriptError(msg('p.canal_desconocido', channel=args["channel"]), f'{path}.channel'))
        if takes_kwargs:
            for k in extras:
                if k not in channels:
                    errors.append(ScriptError(msg('p.canal_desconocido_2', k=k), f'{path}.{k}'))
        if name == 'face' and isinstance(args.get('name'), str) and args['name'] not in EXPRESSIONS:
            errors.append(ScriptError(msg('p.expresion_desconocida_usa_una_de', name=args["name"], a=", ".join(EXPRESSIONS)), f'{path}.name'))
        if name == 'track' and isinstance(args.get('prop'), str) and args['prop'] not in shot_props:
            errors.append(ScriptError(msg('p.prop_desconocido_en_este_plano', prop=args["prop"]), f'{path}.prop'))
    return len(errors) == start


# ---- escenas: biblioteca -> escena -> plano ----
def _expand(script, errors, rigs=None):
    """Flat form of `script` (every shot with `set`, full `actors` and `props`); problems are appended to `errors`.
    A script without `scenes` and without shots that carry `scene` is returned as is. `rigs` (id -> rig) enables the
    channel check of the cast `start` values."""
    scenes, shots = script.get('scenes', []), script['shots']
    if 'scenes' not in script and not any(isinstance(s, dict) and 'scene' in s for s in shots):
        return script
    if not isinstance(scenes, list):
        errors.append(ScriptError(msg('p.scenes_debe_ser_una_lista'), 'scenes'))
        return script
    characters, sets, library = (script.get(k, {}) for k in ('characters', 'sets', 'props'))
    index = {}
    for i, scene in enumerate(scenes):
        sp = f'scenes[{i}]'
        if not isinstance(scene, dict):
            errors.append(ScriptError(msg('p.la_escena_debe_ser_un'), sp))
            continue
        sid = scene.get('id')
        if not isinstance(sid, str) or not sid:
            errors.append(ScriptError(msg('p.la_escena_necesita_un_id'), f'{sp}.id'))
            continue
        if sid in index:
            errors.append(ScriptError(msg('p.id_de_escena_duplicado', sid=sid), f'{sp}.id'))
            continue
        if scene.get('set') is None:
            errors.append(ScriptError(msg('p.la_escena_necesita_un_set', sid=sid), f'{sp}.set'))
        elif scene['set'] not in sets:
            errors.append(ScriptError(msg('p.escenario_desconocido_en_la_escena', set=scene["set"], sid=sid), f'{sp}.set'))
        entry = index[sid] = {'scene': scene, 'cast': {}, 'props': {}}
        names = set()

        def claim(item_id, path):
            if not isinstance(item_id, str) or not item_id or item_id == 'shot':
                errors.append(ScriptError(msg('p.id_no_valido', item_id=item_id), f'{path}.id'))
            elif item_id in names:
                errors.append(ScriptError(msg('p.id_duplicado_en_la_escena', sid=sid, item_id=item_id), f'{path}.id'))
            else:
                names.add(item_id)
                return True
            return False
        lists = {}
        for section in ('cast', 'props'):
            lists[section] = scene.get(section, [])
            if not isinstance(lists[section], list):
                errors.append(ScriptError(msg('p.debe_ser_una_lista_2', section=section), f'{sp}.{section}'))
                lists[section] = []
        for j, member in enumerate(lists['cast']):
            cp = f'{sp}.cast[{j}]'
            if not isinstance(member, dict):
                errors.append(ScriptError(msg('p.el_miembro_del_reparto_debe'), cp))
                continue
            if not claim(member.get('id'), cp):
                continue
            cid = member.get('character') or member['id']
            if cid not in characters:
                errors.append(ScriptError(msg('p.personaje_desconocido_no_esta_en', cid=cid), f'{cp}.character'))
            st = member.get('start', {})
            if not isinstance(st, dict):
                errors.append(ScriptError(msg('p.start_debe_ser_un_objeto'), f'{cp}.start'))
            elif cid in (rigs or {}):
                known = set(DEFAULTS) | set(RIG_CHANNELS) | set(rigs[cid].get('defaults', {}))
                for k in st:
                    if k not in known:
                        errors.append(ScriptError(msg('p.canal_desconocido_en_start', k=k), f'{cp}.start.{k}'))
            entry['cast'][member['id']] = member
        for j, prop in enumerate(lists['props']):
            pp = f'{sp}.props[{j}]'
            if not isinstance(prop, dict):
                errors.append(ScriptError(msg('p.la_utileria_debe_ser_un'), pp))
                continue
            if not claim(prop.get('id'), pp):
                continue
            lib = prop.get('prop') or prop['id']
            if lib not in library:
                errors.append(ScriptError(msg('p.prop_desconocido_no_esta_en', lib=lib), f'{pp}.prop'))
            spec = prop.get('spec', {})
            if not isinstance(spec, dict) or 'id' in spec:
                errors.append(ScriptError(msg('p.spec_debe_ser_un_objeto'), f'{pp}.spec'))
            entry['props'][prop['id']] = prop

    out = []
    for i, shot in enumerate(shots):
        if not isinstance(shot, dict) or 'scene' not in shot:
            out.append(shot)
            continue
        sp = f'shots[{i}]'
        entry = index.get(shot['scene']) if isinstance(shot['scene'], str) else None
        if entry is None:
            errors.append(ScriptError(msg('p.escena_desconocida', scene=shot["scene"]), f'{sp}.scene'))
            continue
        scene = entry['scene']
        if 'set' in shot:
            errors.append(ScriptError(msg('p.un_plano_de_una_escena', id=scene["id"]), f'{sp}.set'))
            continue
        flat = {k: v for k, v in shot.items() if k != 'scene'}
        flat['set'] = scene.get('set')
        for section, label, members in (('actors', msg('w.actor'), entry['cast']), ('props', msg('w.prop'), entry['props'])):
            items, rebuilt = shot.get(section, []), []
            if not isinstance(items, list):
                errors.append(ScriptError(msg('p.debe_ser_una_lista_3', section=section), f'{sp}.{section}'))
                continue
            key, own = ('start', 'character') if section == 'actors' else ('spec', 'prop')
            for j, item in enumerate(items):
                ip = f'{sp}.{section}[{j}]'
                if not isinstance(item, dict):
                    errors.append(ScriptError(msg('p.el_debe_ser_un_objeto', label=label), ip))
                    continue
                base = members.get(item.get('id')) if isinstance(item.get('id'), str) else None
                if base is None:
                    fix = msg('p.fix_cast') if section == 'actors' else msg('p.fix_props')
                    place = msg('p.place_cast') if section == 'actors' else msg('p.place_props')
                    errors.append(ScriptError(msg('p.no_esta_en_de_la', a=item.get("id"), place=place, id=scene["id"], fix=fix), f'{ip}.id'))
                    continue
                mine = item.get(key, {})
                if not isinstance(mine, dict):
                    errors.append(ScriptError(msg('p.debe_ser_un_objeto_3', key=key), f'{ip}.{key}'))
                    continue
                inherited = base.get(own) or base['id']
                if item.get(own) not in (None, inherited):
                    errors.append(ScriptError(msg('p.lo_fija_la_escena_no', own=own, id=scene["id"], inherited=inherited), f'{ip}.{own}'))
                    continue
                shared = base.get(key, {}) if isinstance(base.get(key, {}), dict) else {}
                merged = {k: v for k, v in base.items() if k != key}
                merged.update({k: v for k, v in item.items() if k != key})
                merged[own], merged[key] = inherited, {**shared, **mine}
                rebuilt.append(merged)
            flat[section] = rebuilt
        out.append(flat)
    return {k: v for k, v in dict(script, shots=out).items() if k != 'scenes'}


def expand(script):
    """Flat form of a script with scenes: every shot gets its `set` and the full `actors` / `props` (shot values win
    over the scene's, which win over the library's). Raises ScriptError on the first problem."""
    if not isinstance(script, dict) or not isinstance(script.get('shots'), list):
        raise ScriptError(msg('p.el_guion_debe_tener_una'), 'shots')
    errors = []
    flat = _expand(copy.deepcopy(script), errors)
    if errors:
        raise errors[0]
    return flat


def _same(a, b):
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def group_scene(script, scene_id, set_name, title='', description=''):
    """Inverse of `expand` for a flat script: moves the shots that use `set_name` into one new scene. The cast and the
    props of the scene are those the shots use; each cast `start` (prop `spec`) keeps only the values that are identical
    in every shot where that item appears; the shots keep the rest."""
    members = [s for s in script['shots'] if s.get('set') == set_name and 'scene' not in s]
    tables = {'actors': {}, 'props': {}}
    kinds = {'actors': ('character', 'start'), 'props': ('prop', 'spec')}
    for shot in members:
        for section, table in tables.items():
            own, key = kinds[section]
            for item in shot.get(section, []):
                entry = table.setdefault(item['id'], {'own': item.get(own) or item['id'], 'values': []})
                if (item.get(own) or item['id']) != entry['own']:
                    raise ScriptError(msg('p.usa_varios_valores_de_en', id=item["id"], own=own, set_name=set_name))
                entry['values'].append(item.get(key, {}))
    shared = {}
    for section, table in tables.items():
        shared[section] = {}
        for item_id, entry in table.items():
            first = entry['values'][0]
            shared[section][item_id] = {k: v for k, v in first.items() if all(k in o and _same(v, o[k]) for o in entry['values'])}
    scene = {'id': scene_id, 'title': title, 'description': description, 'set': set_name}
    for section, name in (('actors', 'cast'), ('props', 'props')):
        own, key = kinds[section]
        scene[name] = [{'id': i, own: e['own'], key: shared[section][i]} for i, e in tables[section].items()]
    shots = []
    for shot in script['shots']:
        if shot not in members:
            shots.append(shot)
            continue
        grouped = {}
        for k, v in shot.items():
            if k == 'set':
                grouped['scene'] = scene_id
            elif k in kinds:
                own, key = kinds[k]
                grouped[k] = []
                for item in v:
                    rest = {a: b for a, b in item.get(key, {}).items() if a not in shared[k][item['id']]}
                    extra = {a: b for a, b in item.items() if a not in ('id', own, key)}
                    grouped[k].append({'id': item['id'], **({key: rest} if rest else {}), **extra})
            else:
                grouped[k] = v
        shots.append(grouped)
    out = {}
    for k, v in script.items():
        if k == 'shots':
            out['scenes'] = list(script.get('scenes', [])) + [scene]
            out['shots'] = shots
        elif k != 'scenes':
            out[k] = v
    return out


def usage(script, kind, name):
    """Where a library item (`kind`: characters, sets or props) is referenced: [{'path', 'message'}]. Reads the script as
    written (scenes, and shots outside scenes); `puff_burst` uses the prop `puff` without listing it."""
    found = []
    section, own = {'characters': ('cast', 'character'), 'props': ('props', 'prop')}.get(kind, (None, None))

    def members(owner, key, path, message):
        items = owner.get(key, [])
        for j, item in enumerate(items if isinstance(items, list) else []):
            if isinstance(item, dict) and (item.get(own) or item.get('id')) == name:
                found.append({'path': f'{path}.{key}[{j}]', 'message': message})

    def bursts(shot, path):
        if kind == 'props' and name == 'puff':
            for j, a in enumerate(shot.get('actions', [])):
                if isinstance(a, dict) and a.get('do') == 'puff_burst':
                    found.append({'path': f'{path}.actions[{j}]', 'message': msg('p.use_burst_shot', id=shot.get('id'))})
    for i, scene in enumerate(script.get('scenes', [])):
        if not isinstance(scene, dict):
            continue
        sid = scene.get('id')
        if kind == 'sets' and scene.get('set') == name:
            found.append({'path': f'scenes[{i}].set', 'message': msg('p.use_scene_set', id=sid)})
        elif section:
            members(scene, section, f'scenes[{i}]', msg('p.use_scene_cast' if kind == 'characters' else 'p.use_scene_props', id=sid))
    for i, shot in enumerate(script.get('shots', [])):
        if not isinstance(shot, dict):
            continue
        if kind == 'sets' and shot.get('set') == name:
            found.append({'path': f'shots[{i}].set', 'message': msg('p.use_shot_set', id=shot.get('id'))})
        elif section and 'scene' not in shot:
            members(shot, 'actors' if kind == 'characters' else 'props', f'shots[{i}]', msg('p.use_shot_member', id=shot.get('id')))
        bursts(shot, f'shots[{i}]')
    return found


def _build(script, root):
    """Compile; returns (film dict or None, [ScriptError]). Keeps going after errors to report as many as possible."""
    root, errors = Path(root), []
    if not isinstance(script, dict):
        return None, [ScriptError(msg('p.el_guion_debe_ser_un'))]
    script = copy.deepcopy(script)
    if script.get('kind') != 'script' or script.get('schema_version') != 2:
        errors.append(ScriptError(msg('p.se_requiere_kind_script_y')))
    for key in ('id', 'fps', 'width', 'height', 'shots'):
        if key not in script:
            errors.append(ScriptError(msg('p.falta_el_campo', key=key), key))
    if errors:
        return None, errors
    if not (isinstance(script['fps'], int) and script['fps'] > 0):
        return None, [ScriptError(msg('p.fps_debe_ser_un_entero'), 'fps')]
    for section in ('characters', 'sets', 'props'):
        if not isinstance(script.get(section, {}), dict):
            return None, [ScriptError(msg('p.debe_ser_un_objeto_2', section=section), section)]
    if not isinstance(script['shots'], list):
        return None, [ScriptError(msg('p.shots_debe_ser_una_lista'), 'shots')]

    rigs, sets = {}, {}
    for cid, rel in script.get('characters', {}).items():
        data = _read(root, rel, f'characters.{cid}', errors, msg('p.what_character', cid=cid))
        if data is not None:
            rigs[cid] = data
    for name, rel in script.get('sets', {}).items():
        data = _read(root, rel, f'sets.{name}', errors, msg('p.what_set', name=name))
        if data is not None:
            sets[name] = data
            for i, layer in enumerate(data.get('layers', [])):
                _asset(root, layer.get('image'), f'sets.{name}.layers[{i}].image', errors)
    library = script.get('props', {})
    for name, spec in library.items():
        if not isinstance(spec, dict):
            errors.append(ScriptError(msg('p.el_prop_debe_ser_un', name=name), f'props.{name}'))
        else:
            _asset(root, spec.get('sheet'), f'props.{name}.sheet', errors)

    before = len(errors)
    script = _expand(script, errors, rigs)
    if len(errors) > before:
        return None, errors

    film = Film(script['id'], script.get('title', ''), rigs, script['fps'], script['width'], script['height'], library)
    film.spec['characters'] = dict(script.get('characters', {}))
    film.spec['sets'] = sets
    for key in ('style', 'bible'):
        if key in script:
            film.spec[key] = script[key]
    seen_shots = set()
    for i, sd in enumerate(script['shots']):
        sp = f'shots[{i}]'
        if not isinstance(sd, dict):
            errors.append(ScriptError(msg('p.el_plano_debe_ser_un'), sp))
            continue
        sid, dur, set_name = sd.get('id'), sd.get('duration'), sd.get('set')
        bad = len(errors)
        if not isinstance(sid, str) or not sid:
            errors.append(ScriptError(msg('p.el_plano_necesita_un_id'), f'{sp}.id'))
        elif sid in seen_shots:
            errors.append(ScriptError(msg('p.id_de_plano_duplicado', sid=sid), f'{sp}.id'))
        seen_shots.add(sid)
        if not _number(dur) or dur <= 0:
            errors.append(ScriptError(msg('p.la_duracion_debe_ser_un', dur=dur), f'{sp}.duration'))
        if set_name not in script.get('sets', {}):
            errors.append(ScriptError(msg('p.escenario_desconocido', set_name=set_name), f'{sp}.set'))
        if len(errors) > bad:
            continue
        shot = film.shot(sid, dur, set_name, sd.get('description', ''))
        if 'layer_order' in sd:
            lo, lp = sd['layer_order'], f'{sp}.layer_order'
            layer_ids = {l.get('id') for l in sets.get(set_name, {}).get('layers', []) if isinstance(l, dict)}
            if not isinstance(lo, dict):
                errors.append(ScriptError(msg('p.layer_order_debe_ser_un'), lp))
            else:
                for k, v in lo.items():
                    if k not in layer_ids:
                        errors.append(ScriptError(msg('p.no_es_una_capa_del', k=k, set_name=set_name), f'{lp}.{k}'))
                    elif not _number(v):
                        errors.append(ScriptError(msg('p.el_orden_de_la_capa', k=k, v=v), f'{lp}.{k}'))
                if not any(e.path.startswith(lp) for e in errors):
                    shot.spec['layer_order'] = dict(lo)
        names, broken = {'shot': shot}, set()

        def claim(item_id, path):
            if not isinstance(item_id, str) or not item_id or item_id == 'shot':
                errors.append(ScriptError(msg('p.id_no_valido', item_id=item_id), f'{path}.id'))
            elif item_id in names:
                errors.append(ScriptError(msg('p.id_duplicado_en_el_plano', item_id=item_id), f'{path}.id'))
            else:
                return True
            return False
        for j, a in enumerate(sd.get('actors', [])):
            ap = f'{sp}.actors[{j}]'
            try:
                aid = a.get('id')
                cid = a.get('character') or aid
                start = a.get('start', {})
                if not claim(aid, ap):
                    continue
                if cid not in script.get('characters', {}):
                    errors.append(ScriptError(msg('p.personaje_desconocido', cid=cid), f'{ap}.character'))
                    broken.add(aid)
                    continue
                if cid not in rigs:
                    broken.add(aid)
                    continue
                if not isinstance(start, dict):
                    errors.append(ScriptError(msg('p.start_debe_ser_un_objeto'), f'{ap}.start'))
                    broken.add(aid)
                    continue
                known = set(DEFAULTS) | set(RIG_CHANNELS) | set(rigs[cid].get('defaults', {}))
                unknown = [k for k in start if k not in known]
                for k in unknown:
                    errors.append(ScriptError(msg('p.canal_desconocido_en_start', k=k), f'{ap}.start.{k}'))
                if unknown:
                    broken.add(aid)
                    continue
                names[aid] = shot.actor(aid, cid, **start)
                if 'order' in a:
                    if _number(a['order']):
                        names[aid].spec['order'] = a['order']
                    else:
                        errors.append(ScriptError(msg('p.order_debe_ser_un_numero', order=a["order"]), f'{ap}.order'))
            except Exception as e:
                errors.append(ScriptError(msg('p.no_se_pudo_crear_el', e=e), ap))
        for j, p in enumerate(sd.get('props', [])):
            pp = f'{sp}.props[{j}]'
            try:
                pid, lib = p.get('id'), p.get('prop')
                if not claim(pid, pp):
                    continue
                if lib not in library:
                    errors.append(ScriptError(msg('p.prop_desconocido_no_esta_en', lib=lib), f'{pp}.prop'))
                    broken.add(pid)
                    continue
                spec = p.get('spec', {})
                if not isinstance(spec, dict) or 'id' in spec:
                    errors.append(ScriptError(msg('p.spec_debe_ser_un_objeto'), f'{pp}.spec'))
                    broken.add(pid)
                    continue
                _asset(root, spec.get('sheet'), f'{pp}.spec.sheet', errors)
                names[pid] = shot.prop(lib, pid, **spec)
            except Exception as e:
                errors.append(ScriptError(msg('p.no_se_pudo_crear_el_2', e=e), pp))
        for j, a in enumerate(sd.get('actions', [])):
            xp = f'{sp}.actions[{j}]'
            if not isinstance(a, dict):
                errors.append(ScriptError(msg('p.la_accion_debe_ser_un'), xp))
                continue
            on, do = a.get('on'), a.get('do')
            if on in broken:
                continue
            if on not in names:
                errors.append(ScriptError(msg('p.destino_desconocido_debe_ser_shot', on=on), xp))
                continue
            target = names[on]
            kind = 'shot' if target is shot else 'actor' if isinstance(target, Take) else 'prop'
            available = verbs_of(VERB_CLASSES[kind])
            if do not in available:
                errors.append(ScriptError(msg('p.verbo_desconocido_para', do=do, kind=kind, on=on), xp))
                continue
            shot_props = {k for k, v in names.items() if isinstance(v, Prop)}
            if not _check_args(kind, do, available[do], a, xp, target, shot_props, errors):
                continue
            try:
                call_verb(target, do, {k: v for k, v in a.items() if k not in ('on', 'do')})
            except Exception as e:
                errors.append(ScriptError(msg('p.fallo_sobre', do=do, on=on, e=e), xp))
    return (None if errors else film.spec), errors


def usage_table(script):
    """Every library item the script uses, in one pass: {kind: {id: {'scenes': [scene ids], 'shots': [shot ids]}}}.
    Shots of a scene count for the characters and props of that scene's cast (resolved through the instance ids)."""
    table = {k: {} for k in LIBRARY}

    def add(kind, name, where, label):
        if isinstance(name, str) and name:
            ids = table[kind].setdefault(name, {'scenes': [], 'shots': []})[where]
            if label not in ids:
                ids.append(label)

    def items(owner, key):
        value = owner.get(key, [])
        return [m for m in value if isinstance(m, dict)] if isinstance(value, list) else []

    scenes = {}
    for scene in [s for s in (script.get('scenes') or []) if isinstance(s, dict)]:
        sid = scene.get('id')
        scenes[sid] = scene
        add('sets', scene.get('set'), 'scenes', sid)
        for section, kind, own in (('cast', 'characters', 'character'), ('props', 'props', 'prop')):
            for m in items(scene, section):
                add(kind, m.get(own) or m.get('id'), 'scenes', sid)
    for shot in [s for s in (script.get('shots') or []) if isinstance(s, dict)]:
        label = shot.get('id')
        scene = scenes.get(shot.get('scene'))
        add('sets', shot.get('set') if scene is None else scene.get('set'), 'shots', label)
        for section, kind, own, cast in (('actors', 'characters', 'character', 'cast'), ('props', 'props', 'prop', 'props')):
            base = {m.get('id'): m for m in items(scene or {}, cast)}
            for item in items(shot, section):
                inherited = base.get(item.get('id'), {})
                add(kind, item.get(own) or inherited.get(own) or item.get('id'), 'shots', label)
        if any(isinstance(a, dict) and a.get('do') == 'puff_burst' for a in (shot.get('actions') or [])):
            add('props', 'puff', 'shots', label)
    return table


def _prune(script):
    """Script limited to the library items it uses: an episode of a series with hundreds of items only compiles its own."""
    used = usage_table(script)
    out = dict(script)
    for kind in LIBRARY:
        if isinstance(script.get(kind), dict):
            out[kind] = {k: v for k, v in script[kind].items() if k in used[kind]}
    return out


def _compile_input(script, root):
    """(script, asset root) to hand to `_build`: episodes are pruned and resolved against the series root."""
    if series_root(root) is not None and isinstance(script, dict) and isinstance(script.get('shots'), list):
        try:
            return _prune(script), asset_root(root)
        except Exception:
            pass
    return script, asset_root(root)


def _with_root(film, home):
    """Compiled films of an episode say where the assets are, relative to their own folder."""
    if film is not None and series_root(home) is not None:
        film['root'] = Path(os.path.relpath(series_root(home), home)).as_posix()
    return film


def compile_script(script, root):
    """`root` is the project folder (for an episode, the episode folder: assets resolve against the series root)."""
    prepared, assets = _compile_input(script, root)
    film, errors = _build(prepared, assets)
    if errors:
        raise errors[0]
    return _with_root(film, Path(root))


def check(script, root):
    try:
        prepared, assets = _compile_input(script, root)
        film, errors = _build(prepared, assets)
    except Exception as e:
        return [{'path': '', 'message': msg('p.error_inesperado_al_validar', e=e)}]
    return [{'path': e.path, 'message': e.args[0]} for e in errors]    # args[0] keeps the message id (see i18n.py)


def write_film(root, film):
    target = Path(root)/'film.json'
    target.write_text(json.dumps(film, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    return target


def compile_project(root):
    """Compile <root>/script.json (a film or an episode) to <root>/film.json. Returns (film, path)."""
    root = normalize(root)
    script = load(root)
    errors = check(script, root)
    if errors:
        raise ScriptError(join_msgs('\n', [msg('p.path_message', path=e['path'] or msg('w.global'), message=e['message']) for e in errors]), errors[0]['path'])
    film = compile_script(script, root)
    return film, write_film(root, film)


def save(root, script, expect_revision=None):
    root = Path(root)
    film = compile_script(script, root)
    target = root/'script.json'
    stored = json.loads(target.read_text(encoding='utf-8')) if target.exists() else None
    current = stored.get('revision', 0) if stored else script.get('revision', 0)
    if expect_revision is not None and expect_revision != current:
        raise ScriptError(msg('p.conflicto_de_revision_se_esperaba', expect_revision=expect_revision, current=current))
    if stored is not None:
        shutil.copyfile(target, root/'script.previous.json')
    script = dict(script, revision=current+1)
    sroot = series_root(root)
    written = _strip(load_series(sroot), script, stored or {}) if sroot is not None else script
    target.write_text(json.dumps(written, indent=2, ensure_ascii=False), encoding='utf-8')
    write_film(root, film)
    return script


# ---- series: a library shared by many episodes ----
def _slug_id(value, what='id'):
    import re
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', value):
        raise ScriptError(msg('p.el_no_es_valido_usa', what=what, value=value))
    return value


def check_library(root, library):
    """Errors of a series library: missing or invalid files, missing images. Does not look at episodes."""
    root, errors = Path(root), []
    for kind in LIBRARY:
        if not isinstance(library.get(kind, {}), dict):
            errors.append(ScriptError(msg('p.debe_ser_un_objeto', kind=kind), f'library.{kind}'))
    if errors:
        return errors
    for cid, rel in library.get('characters', {}).items():
        _read(root, rel, f'library.characters.{cid}', errors, msg('p.what_character', cid=cid))
    for name, rel in library.get('sets', {}).items():
        data = _read(root, rel, f'library.sets.{name}', errors, msg('p.what_set', name=name))
        for i, layer in enumerate((data or {}).get('layers', [])):
            _asset(root, layer.get('image'), f'library.sets.{name}.layers[{i}].image', errors)
    for name, spec in library.get('props', {}).items():
        if not isinstance(spec, dict):
            errors.append(ScriptError(msg('p.el_prop_debe_ser_un', name=name), f'library.props.{name}'))
        else:
            _asset(root, spec.get('sheet'), f'library.props.{name}.sheet', errors)
    return errors


def save_series(root, series, expect_revision=None, validate=True):
    """Write series.json (revision +1, previous copy in series.previous.json). Returns the saved series."""
    root = Path(root)
    if not isinstance(series, dict) or series.get('kind') != 'series' or series.get('schema_version') != 2:
        raise ScriptError(msg('p.se_requiere_kind_series_y'))
    if validate:
        errors = check_library(root, library_of(series))
        if errors:
            raise errors[0]
    target = root/'series.json'
    stored = json.loads(target.read_text(encoding='utf-8')) if target.exists() else None
    current = stored.get('revision', 0) if stored else series.get('revision', 0)
    if expect_revision is not None and expect_revision != current:
        raise ScriptError(msg('p.conflicto_de_revision_se_esperaba_2', expect_revision=expect_revision, current=current))
    if stored is not None:
        shutil.copyfile(target, root/'series.previous.json')
    series = dict(series, revision=current+1)
    target.write_text(json.dumps(series, indent=2, ensure_ascii=False), encoding='utf-8')
    return series


def episode_ids(root):
    base = Path(root)/'episodes'
    return sorted(d.name for d in base.iterdir() if (d/'script.json').is_file()) if base.is_dir() else []


def episode_info(root):
    """One summary per episode: id, title, scenes, shots, seconds, revision."""
    out = []
    for ep in episode_ids(root):
        try:
            script = load_raw(Path(root)/'episodes'/ep)
        except ScriptError:
            out.append({'id': ep, 'title': ep, 'scenes': 0, 'shots': 0, 'seconds': 0, 'revision': 0, 'broken': True})
            continue
        shots = [s for s in script.get('shots', []) if isinstance(s, dict)]
        out.append({'id': ep, 'title': script.get('title') or ep, 'scenes': len(script.get('scenes', [])), 'shots': len(shots),
                    'seconds': round(sum(s.get('duration', 0) for s in shots if isinstance(s.get('duration'), (int, float))), 3),
                    'revision': script.get('revision', 0), 'notes': script.get('notes', '')})
    return out


def series_usage(root):
    """Use of every library item across all the episodes: {kind: {id: {episode: {'scenes': [...], 'shots': [...]}}}}."""
    out = {k: {} for k in LIBRARY}
    for ep in episode_ids(root):
        try:
            table = usage_table(load(Path(root)/'episodes'/ep))
        except ScriptError:
            continue
        for kind in LIBRARY:
            for name, where in table[kind].items():
                out[kind].setdefault(name, {})[ep] = where
    return out


def usage_in_series(root, kind, name):
    """Like `usage`, but across every episode: [{'episode', 'path', 'message'}] (`message` names the episode)."""
    found = []
    for ep in episode_ids(root):
        try:
            script = load(Path(root)/'episodes'/ep)
        except ScriptError:
            continue
        found += [{'episode': ep, **u, 'message': msg('p.capitulo', message=u["message"], ep=ep)} for u in usage(script, kind, name)]
    return found


_NAMES = {}


def _display_name(path):
    """`name` of a rig json, cached by file stamp (a series can have hundreds of characters)."""
    try:
        info = Path(path).stat()
        key = (str(path), info.st_mtime_ns, info.st_size)
        if key not in _NAMES:
            _NAMES[key] = json.loads(Path(path).read_text(encoding='utf-8')).get('name', '')
        return _NAMES[key]
    except (OSError, ValueError, AttributeError):
        return ''


def library_catalogue(root, q='', kind=None, used=None, episode=None, limit=200, offset=0):
    """Compact, filterable listing of the series library: [{'kind','id','name','file','episodes':{ep: shots+scenes},'uses'}]
    plus counts. `q` matches id and name; `used` True/False keeps used/unused items; `episode` keeps the items an episode
    uses. Returns {'items', 'total', 'counts'}."""
    root = Path(root)
    lib, use = library_of(load_series(root)), series_usage(root)
    items = []
    for k in LIBRARY:
        if kind and k != kind:
            continue
        for name, value in lib[k].items():
            file = value.get('sheet') if k == 'props' and isinstance(value, dict) else value
            title = _display_name(root/value) if k == 'characters' and isinstance(value, str) else ''
            eps = {ep: len(w['scenes'])+len(w['shots']) for ep, w in use[k].get(name, {}).items()}
            items.append({'kind': k, 'id': name, 'name': title if isinstance(title, str) else '',
                          'file': file if isinstance(file, str) else None, 'episodes': eps, 'uses': sum(eps.values())})
    counts = {k: sum(1 for i in items if i['kind'] == k) for k in LIBRARY}
    needle = (q or '').strip().lower()
    if needle:
        items = [i for i in items if needle in i['id'].lower() or needle in i['name'].lower()]
    if used is not None:
        items = [i for i in items if bool(i['episodes']) == used]
    if episode:
        items = [i for i in items if episode in i['episodes']]
    items.sort(key=lambda i: (LIBRARY.index(i['kind']), i['id']))
    return {'items': items[offset:offset+limit], 'total': len(items), 'counts': counts}


def create_series(projects, sid, title=''):
    sid = _slug_id(sid, msg('w.series_id'))
    root = Path(projects)/sid
    if root.exists():
        raise ScriptError(msg('p.ya_existe_projects', sid=sid))
    for folder in ('characters', 'sets', 'assets', 'refs', 'episodes'):
        (root/folder).mkdir(parents=True)
    series = {'schema_version': 2, 'kind': 'series', 'id': sid, 'title': title or sid, 'revision': 0, 'notes': '', 'fps': 24,
              'width': 1920, 'height': 1080, 'style': {'hold': 2, 'contour': 1.4, 'boil': .32, 'boil_hold': 3},
              'bible': {}, 'references': [], 'library': {'characters': {}, 'sets': {}, 'props': {}}}
    save_series(root, series)
    return root


def create_episode(root, ep, title=''):
    root = Path(root)
    if not is_series(root):
        raise ScriptError(msg('p.no_es_una_serie_falta', name=root.name))
    ep = _slug_id(ep, msg('w.episode_id'))
    home = root/'episodes'/ep
    if home.exists():
        raise ScriptError(msg('p.ya_existe_el_capitulo', ep=ep))
    (home/'renders').mkdir(parents=True)
    script = {'schema_version': 2, 'kind': 'script', 'id': ep, 'title': title or ep, 'revision': 0, 'notes': '', 'story': '',
              'scenes': [], 'shots': []}
    try:
        save(home, effective(load_series(root), script))
    except Exception:
        shutil.rmtree(home, ignore_errors=True)
        raise
    return home


def duplicate_episode(root, ep, new_id, title=None):
    root = Path(root)
    source, new_id = root/'episodes'/_slug_id(ep), _slug_id(new_id, msg('w.episode_id'))
    if not (source/'script.json').is_file():
        raise ScriptError(msg('p.no_existe_el_capitulo', ep=ep))
    home = root/'episodes'/new_id
    if home.exists():
        raise ScriptError(msg('p.ya_existe_el_capitulo_2', new_id=new_id))
    raw = load_raw(source)
    raw.update(id=new_id, revision=0, title=title or f'{raw.get("title") or ep} (copia)')
    (home/'renders').mkdir(parents=True)
    (home/'script.json').write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding='utf-8')
    try:
        write_film(home, compile_script(load(home), home))
    except Exception:
        shutil.rmtree(home, ignore_errors=True)
        raise
    return home


def retire_episode(root, ep):
    """Delete an episode without losing it: its folder moves to <series>/papelera/episodes/<ep>-<timestamp>."""
    root = Path(root)
    source = root/'episodes'/_slug_id(ep)
    if not (source/'script.json').is_file():
        raise ScriptError(msg('p.no_existe_el_capitulo', ep=ep))
    folder = root/'papelera'/'episodes'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder/f'{ep}-{int(time.time())}'
    shutil.move(str(source), str(target))
    return target


def _free(wanted, taken):
    candidate, n = wanted, 1
    while candidate in taken:
        n += 1
        candidate = f'{wanted}-{n}'
    return candidate


def import_scene(dest, source, scene_id, new_id=None):
    """Copy scene `scene_id` of the (effective) script `source` and all its shots into `dest` (a copy is returned; `dest`
    and `source` may be the same script, which duplicates the scene). Ids that clash get a suffix (`id-2`). Local items of
    the source episode that `dest` lacks are copied into `dest`'s library. Returns (script, scene, shots)."""
    scene = next((s for s in source.get('scenes', []) if isinstance(s, dict) and s.get('id') == scene_id), None)
    if scene is None:
        raise ScriptError(msg('p.no_existe_la_escena_en', scene_id=scene_id))
    out = copy.deepcopy(dest)
    scene = copy.deepcopy(scene)
    scene['id'] = _free(_slug_id(new_id or scene_id, msg('w.scene_id')), {s.get('id') for s in out.get('scenes', []) if isinstance(s, dict)})
    shots = [copy.deepcopy(s) for s in source.get('shots', []) if isinstance(s, dict) and s.get('scene') == scene_id]
    taken = {s.get('id') for s in out.get('shots', []) if isinstance(s, dict)}
    for shot in shots:
        shot['id'] = _free(shot.get('id') or 'plano', taken)
        taken.add(shot['id'])
        shot['scene'] = scene['id']
    used = usage_table({'scenes': [scene], 'shots': shots})
    for kind in LIBRARY:
        for name in used[kind]:
            if name not in out.setdefault(kind, {}) and name in (source.get(kind) or {}):
                out[kind][name] = copy.deepcopy(source[kind][name])
    out['scenes'] = list(out.get('scenes', []))+[scene]
    out['shots'] = list(out.get('shots', []))+shots
    return out, scene, shots


def convert_series(root):
    """Turn a single film (root script.json) into a series with one episode `ep01`: the library moves to series.json and the
    script to episodes/ep01/. Files are moved, never deleted. Returns the series root."""
    root = Path(root)
    if is_series(root):
        raise ScriptError(msg('p.ya_es_una_serie', name=root.name))
    script = load_raw(root)
    series = {'schema_version': 2, 'kind': 'series', 'id': root.name, 'title': script.get('title') or root.name, 'revision': 0,
              'notes': script.get('story', ''), 'fps': script.get('fps', 24), 'width': script.get('width', 1920),
              'height': script.get('height', 1080), 'style': script.get('style', {}), 'bible': script.get('bible', {}),
              'references': script.get('references', []), 'library': {k: script.get(k, {}) for k in LIBRARY}}
    errors = check_library(root, library_of(series))
    if errors:
        raise errors[0]
    home = root/'episodes'/'ep01'
    home.mkdir(parents=True)
    episode = {k: v for k, v in script.items() if k not in LIBRARY+('references', 'bible', 'style')}
    episode.update(id='ep01', schema_version=2, kind='script')
    (home/'script.json').write_text(json.dumps(episode, indent=2, ensure_ascii=False), encoding='utf-8')
    if (root/'script.previous.json').is_file():
        shutil.move(str(root/'script.previous.json'), str(home/'script.previous.json'))
    if (root/'renders').is_dir():
        shutil.move(str(root/'renders'), str(home/'renders'))
    (home/'renders').mkdir(exist_ok=True)
    (root/'script.json').unlink()
    (root/'film.json').unlink(missing_ok=True)
    save_series(root, series, validate=False)
    write_film(home, compile_script(load(home), home))
    return root


def catalogue():
    """Verbs, channels, expressions and eases for building forms; generated by introspection."""
    def entry(name, fn):
        params = []
        for p in _params(fn):
            if p.kind is p.VAR_KEYWORD:
                continue
            item = {'name': p.name}
            if p.kind is p.VAR_POSITIONAL:
                item['varargs'] = True
            elif p.default is p.empty:
                item['required'] = True
            else:
                item['default'] = list(p.default) if isinstance(p.default, tuple) else p.default
            params.append(item)
        return {'name': name, 'doc': inspect.getdoc(fn) or '', 'params': params,
                'kwargs': any(p.kind is p.VAR_KEYWORD for p in _params(fn))}
    verbs = {kind: [entry(n, f) for n, f in sorted(verbs_of(cls).items())] for kind, cls in VERB_CLASSES.items()}
    channels = dict(DEFAULTS)
    channels.update({name: 'numeric' for name in RIG_CHANNELS})
    return {'verbs': verbs, 'channels': channels, 'expressions': list(EXPRESSIONS), 'eases': list(EASES)}
