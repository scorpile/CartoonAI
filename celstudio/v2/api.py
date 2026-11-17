"""HTTP-facing logic for engine v2 films (any `projects/<id>/script.json`). Wired into celstudio/server.py.

`Service.handle` returns `(value, status, content_type)`; errors are raised as ContractError/V2Error and become
`{"error": ...}` with status 400 in the server. All Skia rendering is serialised by one lock because `Stage` is not
thread-safe, and Stage objects are cached (texture loading is the slow part).
"""
from collections import OrderedDict
from pathlib import Path
import base64
import copy
import hashlib
import io
import json
import posixpath
import re
import shutil
import threading
import time
import unicodedata
import uuid
from PIL import Image
from ..model import asset_path, identifier, ContractError
from . import i18n, project
from .i18n import msg
from .project import ScriptError

MAX_UPLOAD = 20*1024*1024
REF_KINDS = ('estilo', 'personaje', 'escenario', 'guion')
LIBRARY = ('characters', 'sets', 'props')
LIBRARY_NAMES = {'characters': msg('lib.characters'), 'sets': msg('lib.sets'), 'props': msg('lib.props')}
IMAGE_SUFFIXES = ('.png', '.jpg', '.jpeg', '.webp')
EMPTY_SET = {'color': '#e9c48f', 'ground_y': 690.0, 'layers': [], 'post': False,
             'light': {'rim': {'dir': [.78, -.62], 'color': '#ffe0a6', 'opacity': .55, 'width': 3.2},
                       'shade': {'dir': [-.75, .66], 'color': '#b7a3c4', 'opacity': .55, 'width': 6.0},
                       'shadow': {'contact': {'width': 118, 'height': 20, 'opacity': .3}, 'cast': {}}}}


class V2Error(ContractError):
    """Error with extra fields for the JSON response (`path`, `errors`)."""

    def __init__(self, message, payload=None):
        super().__init__(message)
        self.payload = {'error': message, **(payload or {})}


def _dump(path, data, indent=2):
    Path(path).write_text(json.dumps(data, indent=indent, ensure_ascii=False), encoding='utf-8')


def _digest(value):
    return hashlib.sha1(json.dumps(value, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def _jpeg(image, quality=85):
    import skia
    data = image.encodeToData(skia.kJPEG, quality)
    if data is None:
        raise ContractError(msg('a.no_se_pudo_codificar_la'))
    return bytes(data)


def _slug(text, default='pelicula'):
    ascii_text = unicodedata.normalize('NFKD', text.lower()).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', ascii_text).strip('-')[:40] or default


def _walk_strings(value, found):
    """Every string of a JSON value, in order."""
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            _walk_strings(item, found)
    elif isinstance(value, list):
        for item in value:
            _walk_strings(item, found)
    return found


def _rewrite_strings(value, mapping):
    if isinstance(value, str):
        return mapping.get(value, value)
    if isinstance(value, dict):
        return {k: _rewrite_strings(v, mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [_rewrite_strings(v, mapping) for v in value]
    return value


def _stat(path):
    try:
        info = Path(path).stat()
        return (info.st_mtime_ns, info.st_size)
    except OSError:
        return None


def keep_number_format(new, old):
    """Browsers drop the ".0" of floats (690.0 -> 690). Where a number equals the stored one, reuse the stored value so
    that saving without edits does not rewrite script.json."""
    if isinstance(new, dict) and isinstance(old, dict):
        return {k: keep_number_format(v, old[k]) if k in old else v for k, v in new.items()}
    if isinstance(new, list) and isinstance(old, list):
        return [keep_number_format(v, old[i]) if i < len(old) else v for i, v in enumerate(new)]
    if (isinstance(new, (int, float)) and isinstance(old, (int, float)) and not isinstance(new, bool)
            and not isinstance(old, bool) and new == old):
        return old
    return new


class _Holder:
    """Where the library of a project lives and how a change to it is committed. A film keeps it in its script.json; a series
    keeps it in series.json, and each of its episodes (pid "serie/episodes/ep") edits that same shared library."""

    def __init__(self, service, pid):
        parts = str(pid).split('/')
        projects = service.projects
        self.pid = pid
        if len(parts) == 1 and (projects/identifier(parts[0])/'series.json').is_file():
            self.sid, self.root, self.home = parts[0], projects/parts[0], None
        else:
            self.home = service.home(pid)
            self.root = project.asset_root(self.home)
            self.sid = parts[0] if project.series_root(self.home) is not None else None
        self.shared = self.sid is not None

    def load(self):
        """Library carrier: the whole script of a film, or {revision, characters, sets, props} of a series."""
        if not self.shared:
            return project.load(self.root)
        series = project.load_series(self.root)
        return {'revision': series.get('revision', 0), **project.library_of(series)}

    def local(self, kind):
        """Ids the episode defines itself (they shadow the series': a new shared item must not take them)."""
        if self.home is None or not self.shared:
            return set()
        return set(project.load_raw(self.home).get(kind) or {})

    def uses(self, kind, name, browser=None):
        """Where `name` is used: the saved script (every episode for a series) plus the browser's unsaved `browser` script."""
        if not self.shared:
            found = project.usage(self.load(), kind, name)
            if isinstance(browser, dict):
                known = {u['message'] for u in found}
                found += [u for u in project.usage(browser, kind, name) if u['message'] not in known]
            return found
        current = self.home.name if self.home is not None else None
        found = [u for u in project.usage_in_series(self.root, kind, name) if u['episode'] != current]
        mine = browser if isinstance(browser, dict) else (project.load(self.home) if current else None)
        if mine is not None:
            found += [{'episode': current, **u, 'message': msg('a.capitulo', message=u["message"], current=current)} for u in project.usage(mine, kind, name)]
        return found

    def commit(self, carrier):
        """Save the carrier; returns {'revision', 'library'} (for an episode, its own revision and its effective library)."""
        if not self.shared:
            saved = project.save(self.root, carrier, expect_revision=carrier.get('revision', 0))
            return {'revision': saved['revision'], 'library': {k: saved.get(k, {}) for k in LIBRARY}}
        series = project.load_series(self.root)
        series['library'] = {k: carrier.get(k, {}) for k in LIBRARY}
        saved = project.save_series(self.root, series, expect_revision=carrier.get('revision'))
        if self.home is None:
            return {'revision': saved['revision'], 'library': project.library_of(saved)}
        script = project.load(self.home)
        try:
            project.write_film(self.home, project.compile_script(script, self.home))
        except ScriptError:
            pass
        return {'revision': script.get('revision', 0), 'library': {k: script.get(k, {}) for k in LIBRARY}}


class Service:
    def __init__(self, projects):
        self.projects = Path(projects).resolve()
        self.lock = threading.RLock()          # writes to project files
        self.render_lock = threading.RLock()   # every Skia use
        self.stages = OrderedDict()            # (film id, width) -> {'stage', 'token', 'rig_stats'}
        self.films = OrderedDict()             # script hash -> compiled film
        self.poses = OrderedDict()             # pose key -> jpeg bytes
        self.pose_stages = OrderedDict()       # (film id, character, width) -> (stat, Stage)

    # ---- paths ----
    @staticmethod
    def _parts(pid):
        """`pid` is a film ("taller-v3") or an episode ("serie/episodes/ep01"); a series alone has no script."""
        parts = str(pid).split('/')
        if len(parts) not in (1, 3) or (len(parts) == 3 and parts[1] != 'episodes'):
            raise ContractError(msg('a.pelicula_inexistente'))
        return [identifier(p) for p in parts]

    def home(self, pid):
        """Folder with script.json, film.json and renders/ of a film or an episode."""
        parts = self._parts(pid)
        home = self.projects.joinpath(*parts)
        if len(parts) == 3 and not (self.projects/parts[0]/'series.json').is_file():
            raise ContractError(msg('a.serie_inexistente'))
        if not (home/'script.json').is_file():
            raise ContractError(msg('a.capitulo_inexistente') if len(parts) == 3 else msg('a.pelicula_inexistente'))
        return home

    def root(self, pid):
        """Folder every asset path is relative to: the film itself, or the series root for an episode."""
        return project.asset_root(self.home(pid))

    def series_dir(self, sid):
        root = self.projects/identifier(sid)
        if not (root/'series.json').is_file():
            raise ContractError(msg('a.serie_inexistente'))
        return root

    def script(self, pid):
        """Script of a film, or the effective script of an episode (series library merged in)."""
        return project.load(self.home(pid))

    def context(self, pid):
        """(asset root, script-like with the library) of a film, an episode or a series."""
        parts = str(pid).split('/')
        if len(parts) == 1 and (self.projects/identifier(parts[0])/'series.json').is_file():
            root = self.series_dir(parts[0])
            series = project.load_series(root)
            return root, {**{k: series[k] for k in ('id', 'title', 'fps', 'width', 'height', 'revision') if k in series},
                          **project.library_of(series)}
        home = self.home(pid)
        return project.asset_root(home), project.load(home)

    def declared(self, root, section, name, script):
        """Path of a character/set file declared in the library (must stay inside the project)."""
        declared = script.get(section, {})
        if not isinstance(declared, dict) or name not in declared:
            raise ContractError(msg('a.no_esta_declarado_en_el', name=name, section=section))
        return asset_path(root, declared[name])

    # ---- reading ----
    def create_film(self, body):
        title = str(body.get('title') or '').strip()[:200] or 'Nueva película'
        with self.lock:
            base, pid, n = _slug(title), _slug(title), 1
            while (self.projects/pid).exists():
                n += 1
                pid = f'{base}-{n}'
            root = self.projects/identifier(pid)
            for folder in ('characters', 'sets', 'assets', 'refs', 'renders'):
                (root/folder).mkdir(parents=True)
            script = {'schema_version': 2, 'kind': 'script', 'id': pid, 'title': title, 'revision': 0, 'fps': 24, 'width': 1920,
                      'height': 1080, 'story': '', 'style': {'hold': 2, 'contour': 1.4, 'boil': .32, 'boil_hold': 3}, 'bible': {},
                      'characters': {}, 'sets': {}, 'props': {}, 'references': [], 'scenes': [], 'shots': []}
            try:
                project.save(root, script)
            except Exception:
                shutil.rmtree(root, ignore_errors=True)
                raise
        return {'id': pid, 'title': title}

    def films_list(self):
        """Standalone films (`kind` film) and series (`kind` series, with their episode count and library sizes)."""
        out = []
        for path in sorted(self.projects.glob('*/series.json')):
            try:
                series = json.loads(path.read_text(encoding='utf-8'))
                episodes = project.episode_info(path.parent)
                out.append({'id': path.parent.name, 'kind': 'series', 'title': series.get('title', path.parent.name),
                            'episodes': len(episodes), 'shots': sum(e['shots'] for e in episodes),
                            'seconds': round(sum(e['seconds'] for e in episodes), 3), 'revision': series.get('revision', 0),
                            'library': {k: len(v) for k, v in project.library_of(series).items()}})
            except (ValueError, OSError, TypeError, AttributeError):
                continue
        for path in sorted(self.projects.glob('*/script.json')):
            if (path.parent/'series.json').is_file():
                continue
            try:
                script = json.loads(path.read_text(encoding='utf-8'))
                shots = script.get('shots', [])
                out.append({'id': path.parent.name, 'kind': 'film', 'title': script.get('title', path.parent.name), 'shots': len(shots),
                            'seconds': round(sum(s.get('duration', 0) for s in shots if isinstance(s, dict)), 3),
                            'revision': script.get('revision', 0)})
            except (ValueError, OSError, TypeError):
                continue
        return sorted(out, key=lambda f: f['id'])

    def renders(self, pid, home):
        out = []
        for file in sorted((home/'renders').glob('*.mp4'), key=lambda f: f.stat().st_mtime, reverse=True):
            info = file.stat()
            out.append({'file': file.name, 'url': f'/files/{pid}/renders/{file.name}', 'bytes': info.st_size, 'modified': info.st_mtime})
        return out

    def film(self, pid):
        home = self.home(pid)
        root = project.asset_root(home)
        script = project.load(home)
        characters, sets = {}, {}
        for cid in script.get('characters', {}):
            try:
                characters[cid] = json.loads(self.declared(root, 'characters', cid, script).read_text(encoding='utf-8'))
            except (ValueError, OSError, ContractError):
                pass
        for sid in script.get('sets', {}):
            try:
                sets[sid] = json.loads(self.declared(root, 'sets', sid, script).read_text(encoding='utf-8'))
            except (ValueError, OSError, ContractError):
                pass
        out = {'script': script, 'errors': project.check(script, home), 'catalogue': project.catalogue(),
               'characters': characters, 'sets': sets, 'renders': self.renders(pid, home)}
        sroot = project.series_root(home)
        if sroot is not None:
            raw = project.load_raw(home)
            out.update(series={'id': sroot.name, 'title': project.load_series(sroot).get('title', sroot.name)}, episode=home.name,
                       local={k: sorted(raw.get(k) or {}) for k in project.LIBRARY}, warnings=project.warnings(script, home))
        return out

    # ---- writing ----
    def _fail(self, home, error, script):
        payload = {'path': getattr(error, 'path', '')}
        try:
            payload['errors'] = project.check(script, home)
        except Exception:
            payload['errors'] = []
        raise V2Error(error.args[0], payload) from None

    def save(self, pid, script):
        home = self.home(pid)
        if not isinstance(script, dict):
            raise ContractError(msg('a.el_guion_debe_ser_un'))
        with self.lock:
            stored = project.load(home)
            if script.get('id') != stored.get('id'):
                raise ContractError(msg('a.no_se_puede_cambiar_el'))
            script = keep_number_format(script, stored)
            try:
                saved = project.save(home, script, expect_revision=script.get('revision'))
            except ScriptError as error:
                self._fail(home, error, script)
        return {'script': saved, 'errors': []}

    def check(self, pid, script):
        home = self.home(pid)
        out = {'errors': project.check(script, home)}
        warnings = project.warnings(script, home)
        if warnings:
            out['warnings'] = warnings
        return out

    def _recompile(self, pid):
        home = self.home(pid)
        project.write_film(home, project.compile_script(project.load(home), home))

    def _refresh_users(self, pid, kind, name):
        """After a shared library file changed, recompile the other episodes of the series that use it (best effort)."""
        home = self.home(pid)
        sroot = project.series_root(home)
        if sroot is None or not name:
            return
        for ep in project.series_usage(sroot)[kind].get(name, {}):
            if ep != home.name:
                other = sroot/'episodes'/ep
                try:
                    project.write_film(other, project.compile_script(project.load(other), other))
                except (ScriptError, OSError):
                    pass

    def _replace_file(self, pid, target, data, validate, kind=None, name=None):
        """Back up `target` as <name>.previous.json, write `data`, validate; restore the old file if validation fails."""
        backup = target.with_name(target.stem+'.previous.json')
        old = target.read_bytes() if target.exists() else None
        if old is not None:
            shutil.copyfile(target, backup)
        target.parent.mkdir(parents=True, exist_ok=True)
        _dump(target, data, 1)
        try:
            validate()
            self._recompile(pid)
        except Exception as error:
            if old is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(old)
            if isinstance(error, ScriptError):
                raise V2Error(msg('a.el_cambio_rompe_la_pelicula', error=error), {'path': error.path}) from None
            raise ContractError(msg('a.no_es_valido', error=error)) from None
        self._refresh_users(pid, kind, name)

    def save_character(self, pid, cid, rig):
        home = self.home(pid)
        root = project.asset_root(home)
        if not isinstance(rig, dict):
            raise ContractError(msg('a.el_rig_debe_ser_un'))
        with self.lock:
            target = self.declared(root, 'characters', cid, project.load(home))
            self._replace_file(pid, target, rig, lambda: self._pose_check(root, rig), 'characters', cid)
        return {'ok': True, 'character': rig}

    def save_set(self, pid, sid, spec):
        home = self.home(pid)
        root = project.asset_root(home)
        if not isinstance(spec, dict):
            raise ContractError(msg('a.el_escenario_debe_ser_un'))
        with self.lock:
            script = project.load(home)
            target = self.declared(root, 'sets', sid, script)
            self._replace_file(pid, target, spec, lambda: self._set_check(home, script, sid), 'sets', sid)
        return {'ok': True, 'set': spec}

    def upload_asset(self, root, body, raw, name, script):
        """Image for the library (`category` set_layer: layer of the set `target`; prop_sheet: sheet of the prop `target`).
        Only stores the file; the caller adds it to the set or prop. Does not touch script.json."""
        category, target = body['category'], identifier(body.get('target'))
        rid = uuid.uuid4().hex[:8]
        stem = _slug(Path(name).stem)
        if category == 'set_layer':
            if target not in script.get('sets', {}):
                raise ContractError(msg('a.el_escenario_no_esta_en', target=target))
            relative = f'assets/sets/{target}/{stem}-{rid}.png'
        elif category == 'prop_sheet':
            relative = f'assets/props/{target}/{stem}-{rid}.png'
        else:
            raise ContractError(msg('a.categoria_no_valida_set_layer'))
        try:
            with Image.open(io.BytesIO(raw)) as image:
                if image.width*image.height > 20_000_000:
                    raise ContractError(msg('a.imagen_mayor_a_20_megapixeles'))
                image.load()
                path = asset_path(root, relative)
                path.parent.mkdir(parents=True, exist_ok=True)
                image.convert('RGBA').save(path)
                size = image.size
        except OSError:
            raise ContractError(msg('a.el_archivo_no_es_una')) from None
        return {'file': relative, 'width': size[0], 'height': size[1]}

    def upload(self, pid, body):
        try:
            raw = base64.b64decode(body['data'], validate=True)
        except (KeyError, ValueError, TypeError):
            raise ContractError(msg('a.falta_data_en_base64')) from None
        if len(raw) > MAX_UPLOAD:
            raise ContractError(msg('a.recurso_mayor_a_20_mb'))
        name = str(body.get('name', 'referencia'))[:200]
        if body.get('category'):
            root, script = self.context(pid)
            return self.upload_asset(root, body, raw, name, script)
        home = self.home(pid)
        root = project.asset_root(home)
        kind = str(body.get('kind', 'estilo'))[:40]
        if kind not in REF_KINDS:
            raise ContractError(msg('a.invalid_ref_kind', kinds=', '.join(REF_KINDS)))
        rid = uuid.uuid4().hex[:12]
        (root/'refs').mkdir(exist_ok=True)
        if Path(name).suffix.lower() in ('.txt', '.md'):
            raw.decode('utf-8-sig')
            relative = f'refs/{rid}.txt'
            asset_path(root, relative).write_bytes(raw)
        else:
            try:
                with Image.open(io.BytesIO(raw)) as image:
                    if image.width*image.height > 20_000_000:
                        raise ContractError(msg('a.imagen_mayor_a_20_megapixeles'))
                    image.load()
                    relative = f'refs/{rid}.png'
                    image.convert('RGBA').save(asset_path(root, relative))
            except OSError:
                raise ContractError(msg('a.el_archivo_no_es_una_2')) from None
        entry = {'id': rid, 'file': relative, 'name': name, 'kind': kind, 'notes': str(body.get('notes', ''))[:8000],
                 'sha256': hashlib.sha256(asset_path(root, relative).read_bytes()).hexdigest()}
        with self.lock:
            script = project.load(home)
            script.setdefault('references', []).append(entry)
            try:
                saved = project.save(home, script, expect_revision=script.get('revision', 0))
            except ScriptError as error:
                asset_path(root, relative).unlink(missing_ok=True)
                self._fail(home, error, script)
        return {'file': relative, 'id': rid, 'reference': entry, 'revision': saved['revision']}

    # ---- library: characters, sets and props of the project ----
    def _libraries(self):
        """Every project that has a library: (id, type, title, root, library). Series first, then standalone films."""
        for path in sorted(self.projects.glob('*/series.json')):
            try:
                series = json.loads(path.read_text(encoding='utf-8'))
                yield path.parent.name, 'series', series.get('title', path.parent.name), path.parent, project.library_of(series)
            except (ValueError, OSError, TypeError, AttributeError):
                continue
        for path in sorted(self.projects.glob('*/script.json')):
            if (path.parent/'series.json').is_file():
                continue
            try:
                script = json.loads(path.read_text(encoding='utf-8'))
                yield path.parent.name, 'film', script.get('title', path.parent.name), path.parent, {
                    k: script.get(k, {}) if isinstance(script.get(k, {}), dict) else {} for k in LIBRARY}
            except (ValueError, OSError, TypeError):
                continue

    def importable(self, pid):
        """Library items of the other projects (films and series) that can be copied into `pid` (film, episode or series)."""
        h = _Holder(self, pid)
        own = h.sid or pid
        out = []
        for name, kind_of, title, root, library in self._libraries():
            if name == own:
                continue
            for kind in LIBRARY:
                for item_id, value in library[kind].items():
                    item = {'film': name, 'title': title, 'kind': kind, 'id': item_id, **({'series': True} if kind_of == 'series' else {})}
                    if kind == 'props' and isinstance(value, dict) and isinstance(value.get('sheet'), str):
                        item['sheet'] = value['sheet']
                    if kind == 'sets':
                        try:
                            layers = json.loads(asset_path(root, value).read_text(encoding='utf-8')).get('layers', [])
                            item['preview'] = next((l['image'] for l in layers if isinstance(l, dict) and 'image' in l), None)
                        except (ValueError, OSError, ContractError, AttributeError, TypeError):
                            pass
                    out.append(item)
        return out

    @staticmethod
    def _library_dir(kind, name):
        return {'characters': f'assets/{name}', 'sets': f'assets/sets/{name}', 'props': f'assets/props/{name}'}[kind]

    def _free_id(self, root, script, kind, wanted, taken=()):
        candidate, n = wanted, 1
        while (candidate in script.get(kind, {}) or candidate in taken or asset_path(root, self._library_dir(kind, candidate)).exists()
               or (kind != 'props' and asset_path(root, f'{kind}/{candidate}.json').exists())):
            n += 1
            candidate = f'{wanted}-{n}'
        return candidate

    def _images_of(self, root, data):
        """Image files referenced by a JSON value (paths relative to `root` that exist inside it)."""
        out = []
        for text in _walk_strings(data, []):
            if text.lower().endswith(IMAGE_SUFFIXES) and text not in out:
                try:
                    if asset_path(root, text).is_file():
                        out.append(text)
                except ContractError:
                    pass
        return out

    def _copy_item(self, source, source_lib, script, kind, name, root, wanted, taken=()):
        """Copy a library item of the folder `source` (whose library is `source_lib`) into the project `root`, whose library
        carrier is `script` (modified). Every referenced image is copied under the item's own folder, so the copy is
        self-contained. Returns (new id, item data, written files)."""
        declared = source_lib.get(kind, {})
        if not isinstance(declared, dict) or name not in declared:
            raise ContractError(msg('a.no_existe_el_en_esa', a=LIBRARY_NAMES[kind], name=name))
        new = self._free_id(root, script, kind, identifier(wanted or name), taken)
        if kind == 'props':
            data = copy.deepcopy(declared[name])
            if not isinstance(data, dict):
                raise ContractError(msg('a.la_utileria_no_es_un'))
        else:
            data = json.loads(asset_path(source, declared[name]).read_text(encoding='utf-8'))
        images = self._images_of(source, data)
        folders = [posixpath.dirname(i.replace('\\', '/')) for i in images]
        common = posixpath.commonpath(folders) if images else ''
        mapping = {i: f'{self._library_dir(kind, new)}/{i.replace(chr(92), "/")[len(common):].lstrip("/")}' for i in images}
        written = []
        try:
            for old, rel in mapping.items():
                target = asset_path(root, rel)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(asset_path(source, old), target)
                written.append(target)
            data = _rewrite_strings(data, mapping)
            if kind == 'props':
                if 'id' in data:
                    data['id'] = new
                script.setdefault('props', {})[new] = data
            else:
                rel = f'{kind}/{new}.json'
                (root/kind).mkdir(exist_ok=True)
                _dump(asset_path(root, rel), data, 1)
                written.append(asset_path(root, rel))
                script.setdefault(kind, {})[new] = rel
        except Exception:
            for file in written:
                file.unlink(missing_ok=True)
            raise
        return new, data, written

    def _commit_library(self, h, script, kind, new, data, written, undo=None):
        """Save the library carrier changed by an operation (validates and recompiles); on failure remove `written` files."""
        try:
            result = h.commit(script)
        except ScriptError as error:
            for file in written:
                file.unlink(missing_ok=True)
            if undo:
                undo()
            if h.shared:
                raise V2Error(error.args[0], {'path': error.path}) from None
            self._fail(h.root, error, script)
        return {'id': new, 'kind': kind, 'data': data if kind != 'props' else None, **result}

    @staticmethod
    def _kind(body):
        kind = body.get('kind')
        if kind not in LIBRARY:
            raise ContractError(msg('a.kind_debe_ser_characters_sets'))
        return kind

    def _source(self, source_id):
        """(root, library) of another project, a film or a series."""
        for name, _, _, root, library in self._libraries():
            if name == source_id:
                return root, library
        raise ContractError(msg('a.pelicula_inexistente'))

    def import_item(self, pid, body):
        h, kind = _Holder(self, pid), self._kind(body)
        film = identifier(body.get('film'))
        if film == (h.sid or pid):
            raise ContractError(msg('a.ese_elemento_ya_es_de'))
        source, source_lib = self._source(film)
        with self.lock:
            script = h.load()
            new, data, written = self._copy_item(source, source_lib, script, kind, str(body.get('id', '')), h.root, body.get('as'),
                                                 h.local(kind))
            return self._commit_library(h, script, kind, new, data, written)

    def duplicate_item(self, pid, body):
        h, kind = _Holder(self, pid), self._kind(body)
        name = str(body.get('id', ''))
        with self.lock:
            script = h.load()
            if body.get('as') and body['as'] in script.get(kind, {}):
                raise ContractError(msg('a.ya_existe_en', new_id=body["as"], kind=kind))
            new, data, written = self._copy_item(h.root, script, script, kind, name, h.root, body.get('as') or f'{name}-copia', h.local(kind))
            return self._commit_library(h, script, kind, new, data, written)

    def create_set(self, pid, body):
        h = _Holder(self, pid)
        name = identifier(body.get('id'))
        with self.lock:
            script = h.load()
            if name in script.get('sets', {}) or name in h.local('sets'):
                raise ContractError(msg('a.ya_existe_el_escenario', name=name))
            spec = copy.deepcopy(EMPTY_SET)
            if isinstance(body.get('color'), str) and re.fullmatch(r'#[0-9a-fA-F]{6}', body['color']):
                spec['color'] = body['color']
            target = asset_path(h.root, f'sets/{name}.json')
            if target.exists():
                raise ContractError(msg('a.ya_existe_el_archivo_sets', name=name))
            target.parent.mkdir(exist_ok=True)
            _dump(target, spec, 1)
            script.setdefault('sets', {})[name] = f'sets/{name}.json'
            return self._commit_library(h, script, 'sets', name, spec, [target])

    def add_prop(self, pid, body):
        h = _Holder(self, pid)
        name = identifier(body.get('id'))
        spec = body.get('spec')
        if not isinstance(spec, dict) or 'sheet' not in spec:
            raise ContractError(msg('a.falta_spec_sheet_imagen_de'))
        sheet = asset_path(h.root, spec['sheet'])
        if not sheet.is_file():
            raise ContractError(msg('a.no_existe_la_imagen', sheet=spec["sheet"]))
        with Image.open(sheet) as image:
            width, height = image.size
        spec = {**{'cells': [[0, 0, width, height]], 'pivot': [width//2, height], 'upp': 0.1, 'layer': 'front'}, **spec}
        with self.lock:
            script = h.load()
            if name in script.get('props', {}) or name in h.local('props'):
                raise ContractError(msg('a.ya_existe_la_utileria', name=name))
            script.setdefault('props', {})[name] = spec
            return self._commit_library(h, script, 'props', name, None, [])

    def remove_item(self, pid, body):
        """Unregister a library item. Refused (listing where it is used) while a scene or shot uses it, both in the saved
        script and in the browser's `script`; for a series, in any of its episodes. Files are never deleted: the json of a
        character or set moves to papelera/."""
        h, kind = _Holder(self, pid), self._kind(body)
        name = str(body.get('id', ''))
        with self.lock:
            script = h.load()
            if name not in script.get(kind, {}):
                if name in h.local(kind):
                    raise ContractError(msg('a.es_local_de_este_capitulo', name=name))
                raise ContractError(msg('a.no_existe_el', a=LIBRARY_NAMES[kind], name=name))
            uses = h.uses(kind, name, body.get('script'))
            if uses:
                shown = i18n.join('; ', [u['message'] for u in uses[:6]], '…' if len(uses) > 6 else '')
                raise V2Error(msg('a.no_se_puede_quitar_quita', name=name, shown=shown), {'usages': uses})
            declared = script[kind].pop(name)
            moved = source = None
            if kind != 'props':
                source = asset_path(h.root, declared)
                if source.is_file():
                    folder = asset_path(h.root, f'papelera/{kind}')
                    folder.mkdir(parents=True, exist_ok=True)
                    moved = folder/source.name
                    if moved.exists():
                        moved = folder/f'{source.stem}-{int(time.time())}{source.suffix}'
                    shutil.move(str(source), str(moved))

            def undo():
                if moved is not None:
                    shutil.move(str(moved), str(source))
            result = self._commit_library(h, script, kind, name, None, [], undo)
        result['moved'] = moved.relative_to(h.root).as_posix() if moved else None
        return result

    # ---- series and episodes ----
    def create_series(self, body):
        title = str(body.get('title') or '').strip()[:200] or 'Nueva serie'
        with self.lock:
            wanted = identifier(body['id']) if body.get('id') else _slug(title, 'serie')
            sid, n = wanted, 1
            while (self.projects/sid).exists():
                if body.get('id'):
                    raise ContractError(msg('a.ya_existe_projects', sid=sid))
                n += 1
                sid = f'{wanted}-{n}'
            project.create_series(self.projects, sid, title)
        return {'id': sid, 'title': title}

    def series(self, sid):
        root = self.series_dir(sid)
        series = project.load_series(root)
        return {'series': series, 'episodes': project.episode_info(root),
                'counts': {k: len(v) for k, v in project.library_of(series).items()}}

    def save_series(self, sid, body):
        """Title, notes, bible, style and defaults of the series (the library is edited through the library routes)."""
        root = self.series_dir(sid)
        with self.lock:
            series = project.load_series(root)
            for key in ('title', 'notes'):
                if key in body:
                    series[key] = str(body[key])[:20000]
            for key in ('bible', 'style'):
                if key in body:
                    if not isinstance(body[key], dict):
                        raise ContractError(msg('a.debe_ser_un_objeto', key=key))
                    series[key] = body[key]
            try:
                saved = project.save_series(root, series, expect_revision=body.get('revision'), validate=False)
            except ScriptError as error:
                raise V2Error(error.args[0], {'path': error.path}) from None
        return {'series': saved}

    def library_catalogue(self, sid, query):
        root = self.series_dir(sid)

        def one(name, default=''):
            return query.get(name, [default])[0]
        kind = one('kind') or None
        if kind is not None and kind not in LIBRARY:
            raise ContractError(msg('a.kind_debe_ser_characters_sets'))
        used = {'1': True, '0': False}.get(one('used'))
        try:
            limit, offset = max(1, min(int(one('limit', '200')), 1000)), max(0, int(one('offset', '0')))
        except ValueError:
            raise ContractError(msg('a.limit_y_offset_deben_ser')) from None
        return project.library_catalogue(root, one('q'), kind, used, one('episode') or None, limit, offset)

    def item_usage(self, sid, query):
        root = self.series_dir(sid)
        kind, name = query.get('kind', [''])[0], query.get('id', [''])[0]
        if kind not in LIBRARY:
            raise ContractError(msg('a.kind_debe_ser_characters_sets'))
        return {'kind': kind, 'id': name, 'usages': project.usage_in_series(root, kind, name),
                'episodes': project.series_usage(root)[kind].get(name, {})}

    def _next_episode(self, root):
        taken = set(project.episode_ids(root))
        n = len(taken)+1
        while f'ep{n:02d}' in taken:
            n += 1
        return f'ep{n:02d}'

    def create_episode(self, sid, body):
        root = self.series_dir(sid)
        title = str(body.get('title') or '').strip()[:200]
        with self.lock:
            ep = identifier(body['id']) if body.get('id') else self._next_episode(root)
            project.create_episode(root, ep, title or ep)
        return {'id': ep, 'title': title or ep, 'pid': f'{sid}/episodes/{ep}'}

    def duplicate_episode(self, sid, ep, body):
        root = self.series_dir(sid)
        with self.lock:
            new = identifier(body['as']) if body.get('as') else self._next_episode(root)
            home = project.duplicate_episode(root, ep, new, str(body.get('title') or '').strip()[:200] or None)
        return {'id': new, 'title': project.load_raw(home).get('title'), 'pid': f'{sid}/episodes/{new}'}

    def rename_episode(self, sid, ep, body):
        root = self.series_dir(sid)
        title = str(body.get('title') or '').strip()[:200]
        if not title:
            raise ContractError(msg('a.falta_el_titulo'))
        pid = f'{sid}/episodes/{identifier(ep)}'
        home = self.home(pid)
        with self.lock:
            script = project.load(home)
            script['title'] = title
            try:
                saved = project.save(home, script)
            except ScriptError:     # a broken episode can still be renamed; its compiled film is refreshed on the next save
                raw = project.load_raw(home)
                raw.update(title=title, revision=raw.get('revision', 0)+1)
                _dump(home/'script.json', raw)
                saved = raw
        return {'id': ep, 'title': title, 'revision': saved['revision']}

    def delete_episode(self, sid, ep, body):
        """Retire an episode: its folder moves to <series>/papelera/episodes/. Needs `confirm` equal to the episode id."""
        root = self.series_dir(sid)
        if body.get('confirm') != ep:
            raise ContractError(msg('a.para_borrar_el_capitulo_escribe', ep=ep))
        with self.lock:
            moved = project.retire_episode(root, identifier(ep))
            for key in [k for k in self.stages if str(k[0]).startswith(f'{sid}/episodes/{ep}')]:
                self.stages.pop(key, None)
        return {'ok': True, 'moved': moved.relative_to(root).as_posix()}

    def import_scene(self, pid, body):
        """Copy a scene (and its shots) of another episode of the same series, or of this one, into the script `script`
        (the browser's, or the saved one). Nothing is written: returns the scene, its shots and the library entries to add."""
        home = self.home(pid)
        sroot = project.series_root(home)
        if sroot is None:
            raise ContractError(msg('a.solo_los_capitulos_de_una'))
        source = sroot/'episodes'/identifier(body.get('episode'))
        if not (source/'script.json').is_file():
            raise ContractError(msg('a.capitulo_de_origen_inexistente'))
        dest = body['script'] if isinstance(body.get('script'), dict) else project.load(home)
        out, scene, shots = project.import_scene(dest, project.load(source), str(body.get('scene', '')),
                                                 identifier(body['as']) if body.get('as') else None)
        added = {k: {n: v for n, v in out.get(k, {}).items() if n not in dest.get(k, {})} for k in LIBRARY}
        return {'scene': scene, 'shots': shots, 'library': added}

    # ---- rendering (one lock, small Stage cache) ----
    def _compiled(self, script, home):
        key = (str(home), _digest(script))
        with self.render_lock:
            if key not in self.films:
                self.films[key] = project.compile_script(script, home)
                while len(self.films) > 8:
                    self.films.popitem(last=False)
            self.films.move_to_end(key)
            return self.films[key]

    def _stage(self, pid, root, film, token, width):
        """Stage for (film id, width). A changed film is swapped in, keeping textures and unchanged rigs."""
        from .puppet import Rig
        from .stage import Stage
        key = (pid, width)
        entry = self.stages.get(key)
        stats = {cid: _stat(root/src) for cid, src in film['characters'].items() if isinstance(src, str)}
        if entry is None:
            stage = Stage(film, root, width)
            entry = self.stages[key] = {'stage': stage, 'token': token, 'stats': stats}
        elif entry['token'] != token:
            stage = entry['stage']
            stage.film, stage._performers, stage._setfx = film, {}, {}
            for cid, source in film['characters'].items():
                if cid not in stage.rigs or entry['stats'].get(cid) != stats.get(cid):
                    data = json.loads((root/source).read_text(encoding='utf-8')) if isinstance(source, str) else source
                    stage.rigs[cid] = Rig(data, root)
            entry.update(token=token, stats=stats)
        self.stages.move_to_end(key)
        while len(self.stages) > 3:
            self.stages.popitem(last=False)
        return entry['stage']

    def _frame(self, pid, root, film, token, shot_id, t, width):
        shot = next((s for s in film['shots'] if s['id'] == shot_id), None)
        if shot is None:
            raise ContractError(msg('a.plano_inexistente'))
        t = min(max(float(t), 0.0), shot['duration'])
        with self.render_lock:
            stage = self._stage(pid, root, film, token, width)
            return _jpeg(stage.frame(shot, t, round(t*film['fps'])))

    @staticmethod
    def _width(value, default=640):
        try:
            width = int(value if value not in (None, '') else default)
        except (TypeError, ValueError):
            raise ContractError(msg('a.ancho_no_valido')) from None
        if not 160 <= width <= 1280:
            raise ContractError(msg('a.el_ancho_debe_estar_entre'))
        return width

    @staticmethod
    def _time(value):
        try:
            t = float(value or 0)
        except (TypeError, ValueError):
            raise ContractError(msg('a.tiempo_no_valido')) from None
        if t != t or abs(t) == float('inf'):
            raise ContractError(msg('a.tiempo_no_valido'))
        return t

    def frame(self, pid, shot_id, t, width):
        home = self.home(pid)
        root = project.asset_root(home)
        path = home/'film.json'
        if not path.is_file():
            raise ContractError(msg('a.la_pelicula_no_esta_compilada'))
        film = json.loads(path.read_text(encoding='utf-8'))
        return self._frame(pid, root, film, ('saved', _stat(path)), shot_id, self._time(t), self._width(width))

    def preview(self, pid, body):
        home = self.home(pid)
        root = project.asset_root(home)
        script = body.get('script')
        if not isinstance(script, dict):
            raise ContractError(msg('a.falta_script'))
        try:
            film = self._compiled(script, home)
        except ScriptError as error:
            self._fail(home, error, script)
        return self._frame(pid, root, film, ('script', _digest(script)), str(body.get('shot', '')), self._time(body.get('t')),
                           self._width(body.get('w')))

    # ---- one character alone on a flat set ----
    def _pose_film(self, rig, width):
        return {'schema_version': 2, 'id': 'pose', 'title': 'pose', 'fps': 24, 'width': 600, 'height': 720, 'world': [600, 720],
                'characters': {'c': rig},
                'sets': {'flat': {'color': '#e9c48f', 'layers': [], 'post': False,
                                  'light': {'rim': {'dir': [.78, -.62], 'color': '#ffe0a6', 'opacity': .55, 'width': 3.2},
                                            'shade': {'dir': [-.75, .66], 'color': '#b7a3c4', 'opacity': .55, 'width': 6.0},
                                            'shadow': {'contact': {'width': 118, 'height': 20, 'opacity': .3}, 'cast': {}}}}},
                'shots': [{'id': 'p', 'duration': 1, 'set': 'flat', 'camera': {'drift': [[0, 0]]}}]}

    def _pose_frame(self, stage, film, turn, expression):
        from .direct import EXPRESSIONS
        from .puppet import Performer
        channels = {'x': 300, 'y': 650, 'scale': .9, 'life': 0, 'facing': 1, 'turn': turn}
        if expression:
            if expression not in EXPRESSIONS:
                raise ContractError(msg('a.expresion_desconocida'))
            channels.update(EXPRESSIONS[expression])
        shot = dict(film['shots'][0], actors=[{'id': 'c', 'character': 'c', 'auto_blink': False,
                                               'channels': {k: [[0, v]] for k, v in channels.items()}}])
        stage._performers = {}
        return stage.frame(shot, 0, 0)

    def _pose_check(self, root, rig):
        from .stage import Stage
        film = self._pose_film(rig, 160)
        with self.render_lock:
            stage = Stage(film, root, 160)
            for turn in (0, 1):
                self._pose_frame(stage, film, turn, 'happy' if turn else None)

    def _set_check(self, home, script, sid):
        from .stage import Stage
        root = project.asset_root(home)
        film = project.compile_script(script, home)
        shot = next((s for s in film['shots'] if s['set'] == sid), None)
        if shot is None:
            shot = dict(film['shots'][0], set=sid) if film['shots'] else None
        if shot is not None:
            with self.render_lock:
                Stage(film, root, 160).frame(shot, 0, 0)

    def set_frame(self, pid, query):
        """A set alone (saved state, no actors), for the library and the scene editor."""
        from .stage import Stage
        root, script = self.context(pid)
        sid = query.get('set', [''])[0]
        path = self.declared(root, 'sets', sid, script)
        width = self._width(query.get('w', [''])[0], 480)
        key = ('set', pid, sid, width, _stat(path))
        spec = json.loads(path.read_text(encoding='utf-8'))
        film = {'schema_version': 2, 'id': 'set', 'title': '', 'fps': 24, 'width': script.get('width', 1920), 'height': script.get('height', 1080),
                'world': [1280, 720], 'characters': {}, 'sets': {sid: spec}, 'shots': []}
        shot = {'id': 'set', 'duration': 1, 'set': sid, 'camera': {}, 'actors': [], 'props': [], 'overlays': []}
        with self.render_lock:
            if key not in self.poses:
                self.poses[key] = _jpeg(Stage(film, root, width).frame(shot, 0, 0))
                while len(self.poses) > 96:
                    self.poses.popitem(last=False)
            self.poses.move_to_end(key)
            return self.poses[key]

    def pose(self, pid, query):
        root, script = self.context(pid)
        cid = query.get('character', [''])[0]
        path = self.declared(root, 'characters', cid, script)
        turn = query.get('turn', ['0'])[0]
        turn = {'front': 0.0, '3q': 1.0, '3/4': 1.0}[turn] if turn in ('front', '3q', '3/4') else self._time(turn)
        if not 0 <= turn <= 1:
            raise ContractError(msg('a.turn_debe_estar_entre_0'))
        expression = query.get('expression', [''])[0]
        width = self._width(query.get('w', [''])[0], 320)
        stat = _stat(path)
        key = (pid, cid, stat, turn, expression, width)
        with self.render_lock:
            if key in self.poses:
                self.poses.move_to_end(key)
                return self.poses[key]
            rig = json.loads(path.read_text(encoding='utf-8'))
            film = self._pose_film(rig, width)
            from .stage import Stage
            skey = (pid, cid, width)
            if skey not in self.pose_stages or self.pose_stages[skey][0] != stat:
                self.pose_stages[skey] = (stat, Stage(film, root, width))
            self.pose_stages.move_to_end(skey)
            while len(self.pose_stages) > 3:
                self.pose_stages.popitem(last=False)
            data = _jpeg(self._pose_frame(self.pose_stages[skey][1], film, turn, expression))
            self.poses[key] = data
            while len(self.poses) > 96:
                self.poses.popitem(last=False)
            return data

    # ---- render job ----
    def start_render(self, studio, pid, body):
        from .stage import render_film
        home = self.home(pid)
        script = project.load(home)
        shot = body.get('shot') or None
        if shot is not None:
            identifier(shot)
            if shot not in [s.get('id') for s in script.get('shots', [])]:
                raise ContractError(msg('a.plano_inexistente'))
        width = body.get('width')
        if width is not None:
            if isinstance(width, bool) or not isinstance(width, int) or not 160 <= width <= 3840:
                raise ContractError(msg('a.el_ancho_debe_ser_un'))
        if not script.get('shots'):
            raise ContractError(msg('a.la_pelicula_no_tiene_planos'))
        project.compile_script(script, home)   # fail now, with a clear message, rather than inside the job

        lang = i18n.current()

        def work(jid, update, cancelled):
            try:
                return run(jid, update, cancelled)
            except ValueError as error:           # the job runs later: its message must use the language of the request
                if lang == i18n.DEFAULT:
                    raise
                raise ContractError(i18n.render(error, lang)) from None

        def run(jid, update, cancelled):
            with self.lock:
                self._recompile(pid)
            (home/'renders').mkdir(exist_ok=True)
            filename = f'{jid}-{shot or "pelicula"}.mp4'
            destination = home/'renders'/filename
            if destination.exists():
                raise ContractError(msg('a.el_archivo_de_render_ya'))
            try:
                result = render_film(home/'film.json', destination, width, [shot] if shot else None, None, None, 20, update, cancelled)
            finally:
                parts = destination.with_name(destination.stem+'.parts')
                for _ in range(20):         # after a cancel Windows may still hold the files of stopped workers for a moment
                    shutil.rmtree(parts, ignore_errors=True)
                    if not parts.exists():
                        break
                    time.sleep(.5)
            return {**result, 'file': filename, 'url': f'/files/{pid}/renders/{filename}'}
        return studio.start_task(pid, 'render-v2', work)

    # ---- routing ----
    def handle_series(self, rest, method, query, body, json_type):
        """/api/v2/series[/<id>[/...]]"""
        if not rest:
            if method == 'POST':
                return self.create_series(body), 201, json_type
            return [f for f in self.films_list() if f['kind'] == 'series'], 200, json_type
        sid = identifier(rest[0])
        rest = rest[1:]
        if not rest:
            return (self.save_series(sid, body) if method == 'POST' else self.series(sid)), 200, json_type
        action = rest[0]
        if action == 'library' and len(rest) == 1 and method == 'GET':
            return self.library_catalogue(sid, query), 200, json_type
        if action == 'usage' and method == 'GET':
            return self.item_usage(sid, query), 200, json_type
        if action == 'importable' and method == 'GET':
            return self.importable(sid), 200, json_type
        if action == 'pose' and method == 'GET':
            return self.pose(sid, query), 200, 'image/jpeg'
        if action == 'setframe' and method == 'GET':
            return self.set_frame(sid, query), 200, 'image/jpeg'
        if action == 'library' and method == 'POST' and len(rest) == 2:
            operations = {'import': self.import_item, 'duplicate': self.duplicate_item, 'remove': self.remove_item,
                          'set': self.create_set, 'prop': self.add_prop}
            if rest[1] in operations:
                return operations[rest[1]](sid, body), 200, json_type
        if action == 'upload' and method == 'POST' and body.get('category'):
            return self.upload(sid, body), 200, json_type
        if action == 'episodes' and method == 'POST':
            if len(rest) == 1:
                return self.create_episode(sid, body), 201, json_type
            if len(rest) == 3:
                ep = identifier(rest[1])
                if rest[2] == 'duplicate':
                    return self.duplicate_episode(sid, ep, body), 201, json_type
                if rest[2] == 'rename':
                    return self.rename_episode(sid, ep, body), 200, json_type
                if rest[2] == 'delete':
                    return self.delete_episode(sid, ep, body), 200, json_type
        return {'error': msg('a.ruta_inexistente')}, 404, json_type

    def handle(self, studio, method, parts, query, body):
        """parts = path components after /api/v2. Returns (value, status, content_type). A film or an episode is addressed
        as films/<id>/... or films/<serie>/episodes/<ep>/... (same actions); a series as series/<id>/...

        The language of user-facing messages comes from `?lang=` (or an Accept-Language value in `query['accept_language']`);
        Spanish is the default. Messages are `i18n.Msg` objects (Spanish text + id); they are rendered here, once."""
        lang = i18n.pick_lang(query)
        i18n.set_current(lang)
        try:
            value, status, kind = self._handle(studio, method, parts, query, body)
        except ValueError as error:
            if lang == i18n.DEFAULT:
                raise
            payload = getattr(error, 'payload', None)
            if payload is not None:
                error.payload = i18n.localize(payload, lang)
                error.args = (error.payload.get('error', i18n.render(error, lang)),)
                raise
            raise V2Error(i18n.render(error, lang), {'path': error.path} if getattr(error, 'path', '') else None) from None
        if lang != i18n.DEFAULT and isinstance(value, (dict, list)):
            value = i18n.localize(value, lang)
        return value, status, kind

    def _handle(self, studio, method, parts, query, body):
        json_type = 'application/json; charset=utf-8'
        if parts and parts[0] == 'series':
            return self.handle_series(parts[1:], method, query, body, json_type)
        if parts == ['films'] and method == 'GET':
            return self.films_list(), 200, json_type
        if parts == ['films'] and method == 'POST':
            return self.create_film(body), 201, json_type
        if len(parts) >= 2 and parts[0] == 'films':
            pid = identifier(parts[1])
            rest = parts[2:]
            if rest[:1] == ['episodes'] and len(rest) >= 2:
                pid = f'{pid}/episodes/{identifier(rest[1])}'
                rest = rest[2:]
            if not rest:
                return (self.save(pid, body.get('script')) if method == 'POST' else self.film(pid)), 200, json_type
            action = rest[0]
            if action == 'check' and method == 'POST':
                return self.check(pid, body.get('script')), 200, json_type
            if action == 'frame' and method == 'GET':
                return self.frame(pid, query.get('shot', [''])[0], query.get('t', ['0'])[0], query.get('w', ['640'])[0]), 200, 'image/jpeg'
            if action == 'preview' and method == 'POST':
                return self.preview(pid, body), 200, 'image/jpeg'
            if action == 'setframe' and method == 'GET':
                return self.set_frame(pid, query), 200, 'image/jpeg'
            if action == 'pose' and method == 'GET':
                return self.pose(pid, query), 200, 'image/jpeg'
            if action in ('characters', 'sets') and method == 'POST' and len(rest) == 2:
                ident = identifier(rest[1])
                return (self.save_character(pid, ident, body) if action == 'characters' else self.save_set(pid, ident, body)), 200, json_type
            if action == 'importable' and method == 'GET':
                return self.importable(pid), 200, json_type
            if action == 'library' and method == 'POST' and len(rest) == 2:
                operations = {'import': self.import_item, 'duplicate': self.duplicate_item, 'remove': self.remove_item,
                              'set': self.create_set, 'prop': self.add_prop}
                if rest[1] in operations:
                    return operations[rest[1]](pid, body), 200, json_type
            if action == 'scenes' and rest[1:] == ['import'] and method == 'POST':
                return self.import_scene(pid, body), 200, json_type
            if action == 'upload' and method == 'POST':
                return self.upload(pid, body), 200, json_type
            if action == 'render' and method == 'POST':
                return self.start_render(studio, pid, body), 202, json_type
        return {'error': msg('a.ruta_inexistente')}, 404, json_type
