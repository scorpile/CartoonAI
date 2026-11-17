'use strict';
/* Estudio v2 de Cel Studio. El guion (script.json) vive en memoria en S.script y es la única fuente de estado:
   cada vista lo edita en el sitio, sin reordenar ni descartar claves que no conoce. */

const $ = s => document.querySelector(s);
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; };
const clone = v => JSON.parse(JSON.stringify(v));
const sleep = ms => new Promise(r => setTimeout(r, ms));

/* ---------- idiomas (es | en) ----------
   Cada texto visible pasa por t('clave', {argumentos}); el catálogo CATALOG (es y en, mismas claves) está al final del archivo.
   Los datos del usuario (historia, nombres, notas) no se traducen. Para añadir un idioma: ver el bloque «i18n» al final. */
const LANGS = ['es', 'en'];
const I18N = { lang: 'es' };
function detectLang() {
  try { const saved = localStorage.getItem('cel-lang'); if (LANGS.includes(saved)) return saved; } catch { /* sin almacenamiento */ }
  return String(navigator.language || '').toLowerCase().startsWith('es') ? 'es' : 'en';
}
I18N.lang = detectLang();
function t(key, args) {
  const text = (CATALOG[I18N.lang] || CATALOG.es)[key] ?? CATALOG.es[key] ?? key;
  return args ? text.replace(/\{(\w+)\}/g, (m, k) => (k in args ? args[k] : m)) : text;
}
function tp(key, n) {        // plural: el texto del catálogo es «singular|plural» con {n}
  const [one, many] = t(key).split('|');
  return (n === 1 ? one : many ?? one).replace('{n}', n);
}
const verbDoc = (type, entry) => (CATALOG[I18N.lang] || CATALOG.es)[`verb.${type}.${entry.name}`] ?? entry.doc;
const withLang = path => `${path}${path.includes('?') ? '&' : '?'}lang=${I18N.lang}`;
const langHeaders = extra => ({ 'Accept-Language': I18N.lang, ...extra });
function applyStatic() {
  document.documentElement.lang = I18N.lang;
  document.title = t('html.title');
  document.querySelectorAll('[data-i18n]').forEach(e => { e.textContent = t(e.getAttribute('data-i18n')); });
  for (const [attr, prop] of [['title', 'title'], ['aria', 'aria-label'], ['ph', 'placeholder']]) {
    document.querySelectorAll(`[data-i18n-${attr}]`).forEach(e => e.setAttribute(prop, t(e.getAttribute(`data-i18n-${attr}`))));
  }
  document.querySelectorAll('[data-lang]').forEach(b => { const on = b.dataset.lang === I18N.lang; b.classList.toggle('active', on); b.setAttribute('aria-pressed', String(on)); });
}
function setStatus(key) { S.statusKey = key; $('#save-state').textContent = t(key); }
/* Cambia el idioma sin recargar: el guion en memoria (S.script, con sus cambios sin guardar) no se toca; sólo se repinta. */
async function setLang(lang) {
  if (!LANGS.includes(lang) || lang === I18N.lang) return;
  I18N.lang = lang;
  try { localStorage.setItem('cel-lang', lang); } catch { /* sin almacenamiento */ }
  applyStatic(); updateHeading();
  if (S.films.length) { fillFilmSelect(); fillEpisodeSelect(); }
  if (S.script || S.series) show(S.view); else if (!S.films.length) renderEmpty();
  if (S.script) await attempt(async () => {      // los textos que vienen del servidor (errores, avisos) se piden de nuevo en el idioma nuevo
    const data = await api(v2()); S.warnings = data.warnings || [];
    await runCheck(); if (S.view === 'episodes') show('episodes');
  });
}
function renderEmpty() { $('#view').replaceChildren(heading(t('ui.no_hay_proyectos_v2'), t('ui.crea_el_primero_con_nueva'))); }
const toDataUrl = blob => new Promise((resolve, reject) => { const r = new FileReader(); r.onload = () => resolve(r.result); r.onerror = reject; r.readAsDataURL(blob); });

const VIEWS = { episodes: 'ui.capitulos', library: 'ui.biblioteca_de_la_serie', references: 'ui.referencias', script: 'ui.guion', characters: 'ui.personajes', sets: 'ui.escenarios_y_utileria', scenes: 'ui.escenas', shots: 'ui.planos', render: 'ui.render' };
const STYLE_KEYS = ['hold', 'contour', 'boil', 'boil_hold'];
const TIME_PARAMS = ['t', 't0', 't1'];
const STRING_PARAMS = ['name', 'channel', 'prop', 'side', 'color'];
const EASE_PARAMS = ['ease', 'back'];
const PROPORTIONS = [['outline'], ['hip_height'], ['hip_half'], ['hip_joint_dy'], ['ankle_h'], ['foot', 'toe'], ['foot', 'heel'], ['foot', 'depth'],
  ['arm', 'upper'], ['arm', 'fore'], ['arm', 'smooth'], ['leg', 'thigh'], ['leg', 'shin'], ['leg', 'smooth']];
const SET_BLOCKS = ['lights', 'smoke', 'particles', 'rays', 'light', 'post'];
const PLAY_STEP = 0.1;      // segundos de película por fotograma pedido al reproducir (ritmo reducido)

const S = {
  films: [], series: null, assetId: null, local: null, warnings: [], importableSeries: null, id: null, script: null, savedJson: '', catalogue: null, characters: {}, sets: {}, renders: [], errors: [],
  view: 'shots', shot: 0, time: 0, width: 640, filter: 'all', editor: null, playing: false,
  rigDraft: {}, setDraft: {}, poseVersion: {}, setVersion: 0, job: null, scene: 0, sceneFilter: 'all', importable: null, statusKey: null,
};

/* ---------- utilidades generales ---------- */
let toastTimer;
function toast(text) {
  const t = $('#toast'); t.textContent = text; t.classList.remove('hidden');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.add('hidden'), 7000);
}
async function api(path, body) {
  const options = body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
  options.headers = langHeaders(options.headers);
  const response = await fetch(withLang(path), options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) { const error = new Error(data.error || t('ui.no_se_pudo_completar_la')); error.data = data; throw error; }
  return data;
}
const encodePath = file => String(file).split('/').map(encodeURIComponent).join('/');
// S.id es el id de la película o «serie/episodes/capítulo»; los archivos de la biblioteca cuelgan de la raíz (película o serie).
const v2 = (action = '') => `/api/v2/films/${encodePath(S.id)}${action ? '/' + action : ''}`;
const fileUrl = file => `/files/${encodeURIComponent(S.assetId || S.id)}/${encodePath(file)}`;
async function attempt(fn) { try { return await fn(); } catch (e) { toast(e.message); } }
function button(text, fn, cls = 'button') {
  const b = el('button', cls, text); b.type = 'button';
  b.addEventListener('click', () => attempt(fn));
  return b;
}
let idCounter = 0;
function field(label, input, cls = 'field') {
  const div = el('div', cls);
  input.id = input.id || `f${++idCounter}`;
  const l = el('label', '', label); l.htmlFor = input.id;
  div.append(l, input);
  return div;
}
function heading(title, description) {
  const h = el('div', 'view-heading'); const text = el('div');
  text.append(el('h2', '', title), el('p', '', description)); h.append(text);
  return h;
}
function panel(title, meta) {
  const box = el('div', 'panel'); const head = el('div', 'panel-title');
  head.append(el('h2', '', title)); if (meta) head.append(el('span', 'meta', meta));
  const body = el('div', 'pad'); box.append(head, body);
  return { box, head, body };
}
function textInput(value, onchange, cls = '') {
  const i = el('input', cls); i.type = 'text'; i.value = value ?? '';
  i.addEventListener('input', () => onchange(i.value));
  return i;
}
function numberInput(value, onchange, cls = '', placeholder = '') {
  const i = el('input', cls); i.type = 'number'; i.step = 'any'; i.value = value ?? ''; i.placeholder = placeholder;
  i.addEventListener('input', () => { if (i.value === '') return; const n = Number(i.value); if (Number.isFinite(n)) onchange(n); });
  return i;
}
function selectInput(options, value, onchange, cls = '') {
  const s = el('select', cls);
  for (const o of options) { const [v, label] = Array.isArray(o) ? o : [o, o]; const opt = el('option', '', label); opt.value = v; s.append(opt); }
  s.value = value ?? ''; if (s.value !== String(value ?? '')) s.selectedIndex = -1;
  s.addEventListener('change', () => onchange(s.value));
  return s;
}
function getPath(obj, path) { return path.reduce((o, k) => (o == null ? undefined : o[k]), obj); }
function setPath(obj, path, value) { const parent = getPath(obj, path.slice(0, -1)); if (parent) parent[path[path.length - 1]] = value; }
function uniqueId(base, taken) { let n = 1, id = base; while (taken.includes(id)) id = `${base}${++n}`; return id; }
function seconds(s) { return `${Number(s).toFixed(2).replace(/\.?0+$/, '')} s`; }
function toText(value) { return typeof value === 'string' ? value : JSON.stringify(value); }
function parseText(text, asString) {
  const t = String(text).trim();
  if (asString) return String(text);
  try { return JSON.parse(t); } catch { return String(text); }
}
/* Un textarea de JSON: sólo aplica el valor cuando es JSON válido; si no, se marca en rojo. */
function jsonArea(value, onvalid, cls = 'code short') {
  const area = el('textarea', cls); area.spellcheck = false;
  area.value = value === undefined ? '' : JSON.stringify(value, null, 1);
  area.addEventListener('input', () => {
    if (area.value.trim() === '') { area.classList.remove('invalid'); onvalid(undefined); return; }
    try { onvalid(JSON.parse(area.value)); area.classList.remove('invalid'); } catch { area.classList.add('invalid'); }
  });
  return area;
}

/* ---------- estado, guardado y cabecera ---------- */
const isDirty = () => !!S.script && JSON.stringify(S.script) !== S.savedJson;

function updateHeading() {
  const sc = S.script;
  if (!sc) { if (S.series) { $('#film-title').textContent = S.series.title || S.series.id; setStatus('ui.serie_sin_capitulos'); } else $('#save-state').textContent = S.statusKey ? t(S.statusKey) : ''; return; }
  $('#film-title').textContent = S.series ? `${S.series.title || S.series.id} · ${sc.title || sc.id}` : (sc.title || sc.id);
  const total = (sc.shots || []).reduce((a, s) => a + (Number(s.duration) || 0), 0);
  $('#stat-duration').textContent = seconds(total);
  $('#stat-shots').textContent = String((sc.shots || []).length).padStart(2, '0');
  $('#stat-fps').textContent = `${sc.fps} · ${sc.width}×${sc.height}`;
  $('#revision-tag').textContent = t('ui.revision', { sc: sc.revision ?? 0 });
  $('#save-state').textContent = isDirty() ? t('ui.cambios_sin_guardar') : t('ui.guardado_en_tu_equipo');
  $('#save').classList.toggle('orange', isDirty()); $('#save').classList.toggle('dark', !isDirty());
}

/* Toda edición del guion llama aquí: actualiza el indicador y valida (con retraso). */
function edited(preview = true) {
  updateHeading();
  scheduleCheck();
  if (preview && S.view === 'shots') schedulePreview(250);
}

let checkTimer, checkSeq = 0;
function scheduleCheck() { clearTimeout(checkTimer); checkTimer = setTimeout(runCheck, 500); }
async function runCheck() {
  const seq = ++checkSeq;
  try {
    const r = await api(v2('check'), { script: S.script });
    if (seq !== checkSeq) return;
    S.errors = r.errors;
  } catch { return; }
  renderErrors();
}

async function save() {
  if (document.activeElement && document.activeElement.blur) document.activeElement.blur();   // confirma el campo en edición
  if (!S.script) return false;
  if (!isDirty()) { toast(t('ui.el_guion_ya_esta_guardado')); return true; }
  try {
    const r = await api(v2(), { script: S.script });
    S.script.revision = r.script.revision;
    S.savedJson = JSON.stringify(S.script);
    S.errors = r.errors || [];
    S.setVersion++;
    updateHeading(); renderErrors();
    const films = await api('/api/v2/films'); S.films = films; fillFilmSelect();
    if (S.series) { await refreshSeries(); fillEpisodeSelect(); }
    toast(t('ui.guion_guardado'));
    return true;
  } catch (e) {
    if (e.data && e.data.errors) { S.errors = e.data.errors; renderErrors(); }
    toast(e.data && e.data.path ? `${e.message} (${e.data.path})` : e.message);
    return false;
  }
}

function fillFilmSelect() {
  const select = $('#film-select');
  const group = (label, items, prefix) => {
    const g = el('optgroup'); g.label = label;
    for (const f of items) { const o = el('option', '', f.kind === 'series' ? `${f.title || f.id} (${tp('ui.n_capitulo', f.episodes)})` : (f.title || f.id)); o.value = prefix + f.id; g.append(o); }
    return g;
  };
  const series = S.films.filter(f => f.kind === 'series'), films = S.films.filter(f => f.kind !== 'series');
  select.replaceChildren(...[series.length && group(t('ui.series'), series, 's:'), films.length && group(t('ui.peliculas'), films, 'f:')].filter(Boolean));
  select.value = S.series ? `s:${S.series.id}` : (S.id ? `f:${S.id}` : '');
  fillEpisodeSelect();
}

async function loadFilm(id) {
  stopPlaying();
  const data = await api(`/api/v2/films/${encodePath(id)}`);
  if (data.series) { if (!S.series || S.series.id !== data.series.id) await loadSeries(data.series.id); }
  else { S.series = null; S.importableSeries = null; }
  S.assetId = data.series ? data.series.id : id; S.local = data.local || null; S.warnings = data.warnings || [];
  S.id = id; S.script = data.script; S.savedJson = JSON.stringify(data.script); S.catalogue = data.catalogue;
  S.characters = data.characters; S.sets = data.sets; S.renders = data.renders; S.errors = data.errors;
  S.rigDraft = {}; S.setDraft = {}; S.poseVersion = {}; S.setVersion++;
  S.shot = 0; S.time = 0; S.editor = null; S.filter = 'all'; S.scene = 0; S.sceneFilter = 'all'; S.importable = null;
  fillFilmSelect(); updateHeading(); show(S.view);
  if (S.warnings.length) toast(t('ui.aviso') + S.warnings.map(w => w.message).join(' · '));
}

/* ---------- navegación ---------- */
function show(view) {
  stopPlaying();
  if (!S.script && !['episodes', 'library'].includes(view)) view = 'episodes';
  if (!S.series && ['episodes', 'library'].includes(view)) view = 'shots';
  S.view = view;
  $('#view-name').textContent = t(VIEWS[view]);
  document.querySelectorAll('#nav button').forEach(b => b.classList.toggle('active', b.dataset.view === view));
  const root = $('#view'); root.replaceChildren();
  ({ episodes: episodesView, library: libraryView, references: referencesView, script: scriptView, characters: charactersView, sets: setsView, scenes: scenesView, shots: shotsView, render: renderView })[view](root);
  renderErrors();
}

function renderErrors() {
  const badge = $('#error-badge');
  badge.textContent = S.errors.length; badge.classList.toggle('hidden', !S.errors.length);
  // Sólo se repinta lo que no tiene campos de texto en edición (los formularios no pierden el foco al validar).
  if (S.view === 'shots' && $('#shots-errors')) { renderErrorPanel(); renderShotList(); renderActions(); markCastErrors(); }
  if (S.view === 'scenes' && $('#scene-errors')) { renderSceneList(); renderSceneErrors(); }
}
function markCastErrors() {
  document.querySelectorAll('#shot-cast .mini-item').forEach(item => {
    if (!item.dataset.kind) return;
    const errs = errorsIn(S.shot, item.dataset.kind, Number(item.dataset.index));
    item.classList.toggle('error', errs.length > 0); item.title = errs.map(e => e.message).join('\n');
  });
}

/* ---------- 1. Referencias ---------- */
function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result).split(',')[1]);
    r.onerror = () => reject(new Error(t('ui.no_se_pudo_leer_el')));
    r.readAsDataURL(file);
  });
}

function referencesView(root) {
  root.append(heading(t('ui.un_lugar_para_tu_universo'), t('ui.sube_imagenes_o_notas_de')));
  const refs = S.script.references || [];
  const form = el('div', 'panel form-panel stack');
  const file = el('input'); file.type = 'file'; file.accept = 'image/*,.txt,.md';
  const kind = selectInput([['estilo', t('ui.estilo')], ['personaje', t('ui.personaje')], ['escenario', t('ui.escenario')], ['guion', t('ui.guion_2')]], 'estilo', () => {});
  const notes = el('textarea'); notes.placeholder = t('ui.notas_que_debe_tomarse_de');
  form.append(el('h3', '', t('ui.anadir_referencia')), field(t('ui.archivo_imagen_txt_o_md'), file), field(t('ui.tipo'), kind), field(t('ui.notas'), notes),
    button(t('ui.subir_referencia'), async () => {
      const f = file.files[0];
      if (!f) throw new Error(t('ui.elige_un_archivo_primero'));
      if (f.size > 20 * 1024 * 1024) throw new Error(t('ui.el_archivo_supera_los_20'));
      const wasDirty = isDirty();
      const r = await api(v2('upload'), { name: f.name, kind: kind.value, notes: notes.value, data: await fileToBase64(f) });
      (S.script.references = S.script.references || []).push(r.reference); S.script.revision = r.revision;
      if (!wasDirty) S.savedJson = JSON.stringify(S.script);     // el servidor ya guardó la lista: no cuenta como cambio pendiente
      updateHeading(); toast(t('ui.referencia_subida')); show('references');
    }, 'button orange'));
  const grid = el('div', 'reference-grid');
  if (!refs.length) grid.append(el('div', 'empty', t('ui.todavia_no_hay_referencias')));
  refs.forEach((ref, i) => grid.append(referenceCard(ref, i)));
  root.append(form, el('div', 'section-caption'), grid);
}

function referenceCard(ref, i) {
  const card = el('div', 'panel ref-card');
  const wrap = el('div', 'thumb-wrap');
  if (/\.(png|jpe?g|webp|gif)$/i.test(ref.file || '')) {
    const img = el('img'); img.src = fileUrl(ref.file); img.alt = ref.name || ''; img.loading = 'lazy'; wrap.append(img);
  } else {
    wrap.append(el('span', 'file-type', 'TXT'));
    fetch(fileUrl(ref.file)).then(r => r.text()).then(t => { wrap.replaceChildren(Object.assign(el('pre'), { textContent: t.slice(0, 600) })); }).catch(() => {});
  }
  const name = el('div', 'reference-name');
  name.append(el('h3', '', ref.name || ref.file), button(t('ui.quitar_de_la_lista'), () => {
    if (!confirm(t('ui.quitar_esta_referencia_del_guion'))) return;
    S.script.references.splice(i, 1); edited(false); show('references');
  }, 'remove-ref'));
  const kind = selectInput([['estilo', t('ui.estilo')], ['personaje', t('ui.personaje')], ['escenario', t('ui.escenario')], ['guion', t('ui.guion_2')]], ref.kind,
    v => { ref.kind = v; edited(false); });
  const notes = el('textarea'); notes.value = ref.notes || '';
  notes.addEventListener('input', () => { ref.notes = notes.value; edited(false); });
  card.append(wrap, name, field(t('ui.tipo'), kind), field(t('ui.notas'), notes));
  return card;
}

/* ---------- 2. Guion ---------- */
function kvEditor(owner, key, options) {
  const wrap = el('div');
  const data = owner[key] || {};
  const rows = el('div');
  function draw() {
    rows.replaceChildren();
    for (const k of Object.keys(data)) {
      const row = el('div', 'kv'); const value = data[k];
      const label = el('label', '', k);
      let input;
      if (typeof value === 'number') input = numberInput(value, n => { data[k] = n; edited(false); });
      else if (typeof value === 'string') { input = el('textarea'); input.value = value; input.addEventListener('input', () => { data[k] = input.value; edited(false); }); }
      else input = jsonArea(value, v => { if (v !== undefined) { data[k] = v; edited(false); } });
      input.id = `f${++idCounter}`; label.htmlFor = input.id;
      row.append(label, input, button(t('ui.quitar'), () => { delete data[k]; edited(false); draw(); }, 'button tiny danger'));
      rows.append(row);
    }
    if (!Object.keys(data).length) rows.append(el('p', 'hint', t('ui.sin_claves')));
  }
  draw();
  const add = el('div', 'row');
  const name = el('input', 'mid'); name.placeholder = options.placeholder; if (options.datalist) { name.setAttribute('list', options.datalist); }
  add.append(name, button(t('ui.anadir_clave'), () => {
    const k = name.value.trim();
    if (!k) throw new Error(t('ui.escribe_el_nombre_de_la'));
    if (k in data) throw new Error(t('ui.esa_clave_ya_existe'));
    if (!owner[key]) owner[key] = data;
    data[k] = options.initial(k); name.value = ''; edited(false); draw();
  }, 'button small'));
  wrap.append(rows, add);
  return wrap;
}

function scriptView(root) {
  const sc = S.script;
  root.append(heading(t('ui.el_guion_como_datos'), t('ui.el_texto_literario_guia_la')));
  const title = textInput(sc.title, v => { sc.title = v; edited(false); }); title.classList.add('project-title-input');
  const story = el('textarea', 'script-editor'); story.value = sc.story || '';
  story.addEventListener('input', () => { sc.story = story.value; edited(false); });
  const main = panel(t('ui.historia_y_titulo')); main.body.append(field(t('ui.titulo'), title), field(t('ui.guion_literario_story'), story));
  const size = el('div', 'two-col');
  for (const [label, value] of [['fps', sc.fps], [t('ui.tamano'), `${sc.width} × ${sc.height}`]]) {
    const i = el('input'); i.value = value; i.readOnly = true; size.append(field(label + t('ui.solo_lectura'), i));
  }
  main.body.append(size);
  const dl = el('datalist'); dl.id = 'style-keys'; STYLE_KEYS.forEach(k => { const o = el('option'); o.value = k; dl.append(o); });
  const bible = panel(t('ui.biblia'), t('ui.estilo_historia_continuidad'));
  bible.body.append(el('p', 'hint', t('ui.notas_de_direccion_no_cambian')),
    kvEditor(sc, 'bible', { placeholder: t('ui.nueva_clave'), initial: () => '' }));
  const style = panel(t('ui.estilo_de_dibujo'), t('ui.se_aplica_a_toda_la'));
  style.body.append(el('p', 'hint', t('ui.hold_dibujo_a_pasos_2')),
    kvEditor(sc, 'style', { placeholder: 'hold, contour, boil…', datalist: 'style-keys', initial: () => 0 }), dl);
  root.append(el('div', 'stack'));
  root.lastChild.append(main.box, el('div', 'grid-2'));
  root.lastChild.lastChild.append(bible.box, style.box);
}

/* ---------- biblioteca: usos, importar, duplicar y quitar ----------
   La biblioteca (characters, sets, props) es del proyecto; las escenas y los planos sólo la usan.
   Las operaciones de biblioteca las hace el servidor sobre el disco y devuelven el elemento cambiado y la nueva
   revisión: aquí se mezclan en S.script sin tocar el resto de ediciones sin guardar (igual que la subida de referencias). */
const LIBRARY_NAMES = { characters: 'ui.lib_personaje', sets: 'ui.lib_escenario', props: 'ui.utileria' };
const libName = kind => t(LIBRARY_NAMES[kind]);
const sceneById = id => (S.script.scenes || []).find(s => s.id === id);
const sceneClass = id => { const i = (S.script.scenes || []).findIndex(s => s.id === id); return i < 0 ? 'scene-none' : `scene-c${i % 8}`; };
function sceneChip(id) { const c = el('span', `chip ${sceneClass(id)}`, id); c.title = t('ui.escena', { id }); return c; }
const actionCount = (shot, id) => (shot.actions || []).filter(a => a.on === id).length;

/* Dónde se usa un elemento de la biblioteca, según el guion en memoria (escenas y planos sin escena). */
function usageOf(kind, name) {
  const found = [];
  const own = kind === 'characters' ? 'character' : 'prop';
  for (const scene of S.script.scenes || []) {
    if (kind === 'sets' && scene.set === name) found.push(t('ui.escenario_de_la_escena', { id: scene.id }));
    const members = kind === 'characters' ? scene.cast : kind === 'props' ? scene.props : [];
    for (const m of members || []) if ((m[own] || m.id) === name) found.push(t(kind === 'characters' ? 'ui.use_cast_scene' : 'ui.use_props_scene', { id: scene.id, member: m.id }));
  }
  for (const shot of S.script.shots || []) {
    if (kind === 'sets' && shot.set === name) found.push(t('ui.escenario_del_plano', { id: shot.id }));
    if (!shot.scene && kind !== 'sets') for (const m of shot[kind === 'characters' ? 'actors' : 'props'] || []) if ((m[own] || m.id) === name) found.push(t('ui.plano', { id: shot.id, id2: m.id }));
    if (kind === 'props' && name === 'puff' && (shot.actions || []).some(a => a.do === 'puff_burst')) found.push(t('ui.puff_burst_en_el_plano', { id: shot.id }));
  }
  return found;
}
function usageLine(kind, name) {
  const uses = usageOf(kind, name);
  return el('p', 'hint', uses.length ? t('ui.se_usa_en', { uses: uses.join(' · ') }) : t('ui.sin_usar_se_puede_quitar'));
}

function mergeLibrary(r, removed) {
  const wasDirty = isDirty();
  const table = S.script[r.kind] = S.script[r.kind] || {};
  if (removed) delete table[r.id]; else table[r.id] = r.library[r.kind][r.id];
  S.script.revision = r.revision;
  if (r.kind === 'characters') { if (removed) { delete S.characters[r.id]; delete S.rigDraft[r.id]; } else S.characters[r.id] = r.data; }
  if (r.kind === 'sets') { if (removed) { delete S.sets[r.id]; delete S.setDraft[r.id]; } else S.sets[r.id] = r.data; S.setVersion++; }
  if (!wasDirty) S.savedJson = JSON.stringify(S.script);      // el servidor ya guardó este cambio: no cuenta como pendiente
  updateHeading(); runCheck();
}
async function libraryCall(action, body, removed = false) {
  const r = await api(v2(`library/${action}`), body);
  mergeLibrary(r, removed);
  return r;
}

/* Botones Duplicar y Quitar de una ficha de biblioteca. */
function libraryButtons(kind, id) {
  return [button(t('ui.duplicar'), async () => {
    const as = prompt(t('ui.id_de_la_copia_de', { id }), t('ui.copia', { id }));
    if (!as) return;
    const r = await libraryCall('duplicate', { kind, id, as: as.trim() });
    toast(t('ui.copia_creada', { id: r.id })); show(S.view);
  }), button(t('ui.quitar_de_la_biblioteca'), async () => {
    const uses = usageOf(kind, id);
    if (uses.length) throw new Error(t('ui.no_se_puede_quitar_quita', { id, uses: uses.join('; ') }));
    const files = kind === 'props' ? t('ui.las_imagenes_se_conservan') : t('ui.su_archivo_json_pasa_a');
    if (!confirm(t('ui.quitar_de_la_biblioteca_2', { kind: libName(kind), id, files }))) return;
    await libraryCall('remove', { kind, id, script: S.script }, true);
    toast(t('ui.quitado_de_la_biblioteca', { id })); show(S.view);
  }, 'button danger')];
}

function importThumb(o) {
  if (o.kind === 'characters') return `/api/v2/${o.series ? 'series' : 'films'}/${encodeURIComponent(o.film)}/pose?character=${encodeURIComponent(o.id)}&turn=0&w=160`;
  const file = o.kind === 'props' ? o.sheet : o.preview;
  return file ? `/files/${encodeURIComponent(o.film)}/${encodePath(file)}` : '';
}
/* Importar de otra película: el servidor copia el JSON y todas las imágenes que referencia dentro de este proyecto. */
function importPanel(kind, title, toSeries = false) {
  const box = panel(title, toSeries ? t('ui.se_copia_dentro_de_la') : t('ui.se_copia_dentro_de_esta'));
  const holder = el('div', 'stack'); box.body.append(holder);
  holder.append(el('p', 'hint', t('ui.buscando_en_las_demas_peliculas')));
  const load = toSeries ? (S.importableSeries ? Promise.resolve(S.importableSeries) : api(sv2('importable')).then(r => (S.importableSeries = r)))
    : (S.importable ? Promise.resolve(S.importable) : api(v2('importable')).then(r => (S.importable = r)));
  load.then(items => {
    const options = items.filter(i => i.kind === kind);
    holder.replaceChildren();
    if (!options.length) { holder.append(el('p', 'hint', t('ui.no_importable_' + kind))); return; }
    const thumb = el('img', 'import-thumb'); thumb.alt = t('ui.vista_previa');
    thumb.addEventListener('error', () => thumb.classList.add('hidden'));
    const pick = selectInput(options.map((o, n) => [String(n), `${o.title} · ${o.id}`]), '0', () => showThumb());
    function showThumb() { const url = importThumb(options[Number(pick.value)]); thumb.classList.toggle('hidden', !url); if (url) thumb.src = url; }
    const newId = el('input', 'mid'); newId.placeholder = t('ui.id_nuevo_opcional');
    const row = el('div', 'row');
    row.append(thumb, field(t('ui.elemento'), pick), field(t('ui.id_en_esta_pelicula'), newId), button(t('ui.importar'), async () => {
      const o = options[Number(pick.value)];
      const r = await (toSeries ? seriesLibraryCall : libraryCall)('import', { film: o.film, kind, id: o.id, as: newId.value.trim() || undefined });
      toast(t('ui.importado_desde', { id: r.id, film: o.film })); S.importable = null; show(S.view);
    }, 'button orange'));
    holder.append(row, el('p', 'hint', t('ui.si_el_id_ya_existe')));
    showThumb();
  }).catch(e => { holder.replaceChildren(el('p', 'error-text', e.message)); });
  return box.box;
}

/* ---------- 3. Personajes ---------- */
function collectImages(value, prefix, out) {
  if (typeof value === 'string') { if (/\.(png|jpe?g|webp)$/i.test(value) && !out.some(o => o.file === value)) out.push({ label: prefix, file: value }); }
  else if (value && typeof value === 'object') for (const [k, v] of Object.entries(value)) collectImages(v, prefix ? `${prefix}.${k}` : k, out);
  return out;
}

function charactersView(root) {
  root.append(heading(t('ui.los_actores_de_la_pelicula'), t('ui.cada_ficha_edita_el_archivo')));
  root.append(el('p', 'hint', t('ui.un_personaje_nuevo_a_partir')));
  const list = el('div', 'stack'); root.append(list);
  list.append(importPanel('characters', t('ui.importar_un_personaje_de_otra')));
  const ids = Object.keys(S.script.characters || {});
  if (!ids.length) list.append(el('p', 'hint', t('ui.esta_pelicula_no_tiene_personajes')));
  ids.forEach(cid => list.append(characterCard(cid)));
}

function characterCard(cid) {
  const card = el('div', 'panel character-card');
  if (!S.characters[cid]) {
    card.append(el('h3', '', cid), el('p', 'error-text', t('ui.no_se_pudo_leer_el_2', { v: S.script.characters[cid] })), Object.assign(el('div', 'action-row'), {}));
    card.lastChild.append(...libraryButtons('characters', cid));
    return card;
  }
  const rig = S.rigDraft[cid] = S.rigDraft[cid] || clone(S.characters[cid]);
  const advanced = jsonArea(rig, () => {}, 'code'); advanced.classList.remove('short');
  const syncAdvanced = () => { advanced.value = JSON.stringify(rig, null, 1); advanced.classList.remove('invalid'); };

  const head = el('div', 'panel-title');
  head.append(el('h2', '', `${rig.name || cid}  ·  ${cid}`), el('span', 'meta', S.script.characters[cid]));
  card.append(head);
  const body = el('div'); body.className = 'pad'; card.append(body);
  body.append(usageLine('characters', cid));

  const poses = el('div', 'pose-strip');
  const expressions = ['happy', 'surprise', 'worried'].filter(e => S.catalogue.expressions.includes(e));
  const shots = [[t('ui.frente'), 0, ''], ['3/4', 1, '']].concat(expressions.map(e => [e, 1, e]));
  for (const [label, turn, expression] of shots) {
    const wrap = el('div', 'pose'); const img = el('img'); img.loading = 'lazy'; img.alt = `${cid} ${label}`;
    img.src = `${v2('pose')}?character=${encodeURIComponent(cid)}&turn=${turn}&expression=${expression}&w=300&v=${S.poseVersion[cid] || 0}`;
    wrap.append(img, el('div', '', label.toUpperCase())); poses.append(wrap);
  }
  body.append(poses);

  const parts = el('div', 'parts');
  for (const p of collectImages(rig, '', [])) {
    const wrap = el('div', 'part'); const img = el('img'); img.src = fileUrl(p.file); img.loading = 'lazy'; img.alt = p.label; wrap.title = `${p.label}: ${p.file}`;
    wrap.append(img, el('div', '', p.label)); parts.append(wrap);
  }
  body.append(el('div', 'inspector-label', t('ui.partes_imagenes_del_rig')), parts);

  const swatches = el('div', 'swatches');
  for (const [k, v] of Object.entries(rig.colors || {})) {
    const wrap = el('div', 'swatch'); const label = el('label', '', k);
    const input = el('input'); input.type = /^#[0-9a-f]{6}$/i.test(v) ? 'color' : 'text'; input.value = v; input.id = `f${++idCounter}`; label.htmlFor = input.id;
    input.addEventListener('input', () => { rig.colors[k] = input.value; syncAdvanced(); });
    wrap.append(label, input); swatches.append(wrap);
  }
  body.append(el('div', 'inspector-label', t('ui.colores')), swatches);

  const numbers = el('div', 'numbers');
  for (const path of PROPORTIONS) {
    const value = getPath(rig, path);
    if (typeof value !== 'number') continue;
    numbers.append(field(path.join('.'), numberInput(value, n => { setPath(rig, path, n); syncAdvanced(); })));
  }
  body.append(el('div', 'inspector-label', t('ui.proporciones')), numbers);

  const details = el('details', 'advanced'); details.append(el('summary', '', t('ui.avanzado_json_completo_del_rig')), advanced);
  advanced.addEventListener('change', () => {          // al salir del cuadro, el JSON válido sustituye al borrador
    try { S.rigDraft[cid] = JSON.parse(advanced.value); card.replaceWith(characterCard(cid)); } catch { advanced.classList.add('invalid'); }
  });
  body.append(details);
  body.append(Object.assign(el('div', 'action-row'), {}));
  const actions = body.lastChild;
  actions.append(button(t('ui.guardar_personaje'), async () => {
    let data;
    try { data = JSON.parse(advanced.value); } catch { throw new Error(t('ui.el_json_avanzado_no_es')); }
    await api(v2(`characters/${encodeURIComponent(cid)}`), data);
    S.characters[cid] = clone(data); S.rigDraft[cid] = clone(data); S.poseVersion[cid] = (S.poseVersion[cid] || 0) + 1; S.setVersion++;
    toast(t('ui.personaje_guardado_y_pelicula_recompilada', { cid }));
    card.replaceWith(characterCard(cid)); runCheck();
  }, 'button orange'), button(t('ui.descartar_cambios'), () => { delete S.rigDraft[cid]; card.replaceWith(characterCard(cid)); }), ...libraryButtons('characters', cid));
  return card;
}

/* ---------- 4. Escenarios y utilería ---------- */
function setsView(root) {
  root.append(heading(t('ui.donde_ocurre_la_historia'), t('ui.cada_escenario_es_un_archivo')));
  const list = el('div', 'stack'); root.append(list);
  list.append(newSetPanel(), importPanel('sets', t('ui.importar_un_escenario_de_otra')));
  Object.keys(S.script.sets || {}).forEach(sid => list.append(setCard(sid)));
  list.append(propsPanel());
}

function newSetPanel() {
  const box = panel(t('ui.nuevo_escenario_vacio'), t('ui.color_liso_sin_capas'));
  const id = el('input', 'mid'); id.placeholder = t('ui.id_letras_numeros');
  const color = el('input'); color.type = 'color'; color.value = '#e9c48f';
  box.body.append(Object.assign(el('div', 'row'), {}));
  box.body.lastChild.append(field('Id', id), field(t('ui.color_de_fondo'), color), button(t('ui.crear_escenario'), async () => {
    const r = await libraryCall('set', { id: id.value.trim(), color: color.value });
    toast(t('ui.escenario_creado_anade_capas_desde', { id: r.id })); show('sets');
  }, 'button orange'));
  box.body.append(el('p', 'hint', t('ui.un_escenario_nuevo_se_puede')));
  return box.box;
}

function setCard(sid) {
  const card = el('div', 'panel');
  if (!S.sets[sid]) {
    card.append(el('h3', '', sid), el('p', 'error-text', t('ui.no_se_pudo_leer_el_3', { v: S.script.sets[sid] })));
    card.append(Object.assign(el('div', 'action-row'), {})); card.lastChild.append(...libraryButtons('sets', sid));
    return card;
  }
  const spec = S.setDraft[sid] = S.setDraft[sid] || clone(S.sets[sid]);
  const head = el('div', 'panel-title'); head.append(el('h2', '', sid), el('span', 'meta', S.script.sets[sid])); card.append(head);
  const body = el('div', 'pad'); card.append(body);

  body.append(usageLine('sets', sid));
  const img = el('img', 'set-preview'); img.alt = t('ui.vista_previa_de', { sid });
  img.src = `${v2('setframe')}?set=${encodeURIComponent(sid)}&w=480&v=${S.setVersion}`;
  body.append(img, el('p', 'hint', t('ui.escenario_sin_actores_tal_como')));

  const top = el('div', 'numbers');
  const color = el('input'); color.type = 'color'; color.value = /^#[0-9a-f]{6}$/i.test(spec.color) ? spec.color : '#ffffff';
  color.addEventListener('input', () => { spec.color = color.value; });
  top.append(field(t('ui.color_de_fondo_2'), color), field(t('ui.ground_y_suelo'), numberInput(spec.ground_y, n => { spec.ground_y = n; })));
  body.append(top);

  const table = el('table', 'data');
  const hr = el('tr'); ['', 'id', 'depth', 'x', 'y', 'w', 'blur', 'opacity', 'front', t('ui.otros'), ''].forEach(h => hr.append(el('th', '', h)));
  const thead = el('thead'); thead.append(hr); table.append(thead);
  const tb = el('tbody'); table.append(tb);
  const moveLayer = (n, dir) => {
    const to = n + dir; if (to < 0 || to >= spec.layers.length) return;
    [spec.layers[n], spec.layers[to]] = [spec.layers[to], spec.layers[n]]; drawLayers();
  };
  function drawLayers() {
    tb.replaceChildren();
    (spec.layers || []).forEach((layer, n) => {
      const tr = el('tr'); const td = () => { const c = el('td'); tr.append(c); return c; };
      const thumb = el('img', 'thumb'); thumb.src = fileUrl(layer.image); thumb.loading = 'lazy'; thumb.alt = layer.id || ''; thumb.title = layer.image; td().append(thumb);
      td().append(el('code', '', layer.id || '—'));
      for (const key of ['depth', 'x', 'y', 'w', 'blur', 'opacity']) {
        td().append(numberInput(layer[key], v => { layer[key] = v; }, 'narrow', key === 'opacity' ? '1' : key === 'blur' ? '0' : ''));
      }
      const front = el('input'); front.type = 'checkbox'; front.checked = !!layer.front; front.addEventListener('change', () => { if (front.checked) layer.front = true; else delete layer.front; });
      td().append(front);
      td().append(el('span', 'muted', ['drift', 'sway'].filter(k => layer[k]).join(' · ') || '—'));
      td().append(button('↑', () => moveLayer(n, -1), 'button tiny'), button('↓', () => moveLayer(n, 1), 'button tiny'),
        button('✕', () => { spec.layers.splice(n, 1); drawLayers(); }, 'button tiny danger'));
      tb.append(tr);
    });
    if (!(spec.layers || []).length) { const tr = el('tr'); const c = el('td', 'muted', t('ui.sin_capas_el_escenario_es')); c.colSpan = 11; tr.append(c); tb.append(tr); }
  }
  drawLayers();
  const wrap = el('div'); wrap.append(table); wrap.style.overflowX = 'auto';
  body.append(el('div', 'inspector-label', t('ui.capas_de_lejos_a_cerca')), wrap);

  const add = el('div', 'row');
  const file = el('input'); file.type = 'file'; file.accept = 'image/*';
  const layerId = el('input', 'mid'); layerId.placeholder = t('ui.id_de_la_capa');
  add.append(field(t('ui.imagen_de_la_capa'), file), field('Id', layerId), button(t('ui.subir_capa'), async () => {
    const f = file.files[0];
    if (!f) throw new Error(t('ui.elige_una_imagen_primero'));
    if (f.size > 20 * 1024 * 1024) throw new Error(t('ui.el_archivo_supera_los_20'));
    const r = await api(v2('upload'), { category: 'set_layer', target: sid, name: f.name, data: await fileToBase64(f) });
    if (!spec.layers) spec.layers = [];
    spec.layers.push({ id: uniqueId(layerId.value.trim() || t('ui.default_layer_id'), spec.layers.map(l => l.id)), image: r.file, x: 640, y: 360, w: 1280, depth: 0.1 });
    file.value = ''; layerId.value = ''; drawLayers();
    toast(t('ui.capa_subida_ajusta_su_posicion'));
  }, 'button small'));
  body.append(add, el('p', 'hint', t('ui.x_y_y_w_estan')));

  for (const key of SET_BLOCKS) {
    const block = el('div', 'json-block');
    const area = jsonArea(spec[key], v => { if (v === undefined) delete spec[key]; else spec[key] = v; });
    area.placeholder = t('ui.ausente');
    area.id = `f${++idCounter}`;
    const label = el('label', '', key); label.htmlFor = area.id;
    block.append(label, area); body.append(block);
  }
  body.append(el('p', 'hint', t('ui.vacio_quitar_la_clave_un')));
  const actions = el('div', 'action-row');
  actions.append(button(t('ui.guardar_escenario'), async () => {
    await api(v2(`sets/${encodeURIComponent(sid)}`), spec);
    S.sets[sid] = clone(spec); S.setVersion++;
    toast(t('ui.escenario_guardado_y_pelicula_recompilada', { sid }));
    card.replaceWith(setCard(sid)); runCheck();
  }, 'button orange'), button(t('ui.descartar_cambios'), () => { delete S.setDraft[sid]; card.replaceWith(setCard(sid)); }), ...libraryButtons('sets', sid));
  body.append(actions);
  return card;
}

function propsPanel() {
  const box = panel(t('ui.biblioteca_de_utileria'), t('ui.props_del_guion_se_guarda'));
  const props = S.script.props || {};
  box.body.append(el('p', 'hint', t('ui.cada_prop_es_la_especificacion')));
  const names = Object.keys(props);
  if (!names.length) box.body.append(el('p', 'hint', t('ui.no_hay_utileria')));
  for (const name of names) {
    const item = el('div', 'mini-item');
    const sheet = props[name] && props[name].sheet;
    if (sheet) { const img = el('img', 'thumb large'); img.src = fileUrl(sheet); img.alt = name; img.loading = 'lazy'; item.append(img); }
    const col = el('div', 'grow'); col.style.flex = '1';
    col.append(el('strong', '', name), usageLine('props', name));
    const area = jsonArea(props[name], v => { if (v !== undefined) { props[name] = v; edited(false); } }, 'code short');
    const tools = el('div', 'action-row'); tools.append(...libraryButtons('props', name));
    col.append(area, tools); item.append(col); box.body.append(item);
  }
  box.body.append(newPropForm(), importPanel('props', t('ui.importar_utileria_de_otra_pelicula')));
  return box.box;
}

function newPropForm() {
  const form = el('div', 'stack');
  const id = el('input', 'mid'); id.placeholder = t('ui.id_letras_numeros');
  const file = el('input'); file.type = 'file'; file.accept = 'image/*';
  const row = el('div', 'row');
  row.append(field(t('ui.id_de_la_utileria'), id), field(t('ui.hoja_de_sprites_imagen'), file), button(t('ui.crear_utileria'), async () => {
    const f = file.files[0]; const name = id.value.trim();
    if (!name) throw new Error(t('ui.escribe_el_id_de_la'));
    if (!f) throw new Error(t('ui.elige_la_imagen_de_la'));
    if (f.size > 20 * 1024 * 1024) throw new Error(t('ui.el_archivo_supera_los_20'));
    const up = await api(v2('upload'), { category: 'prop_sheet', target: name, name: f.name, data: await fileToBase64(f) });
    const r = await libraryCall('prop', { id: name, spec: { sheet: up.file } });
    toast(t('ui.utileria_creada_con_la_imagen', { id: r.id })); show('sets');
  }, 'button orange'));
  form.append(el('div', 'inspector-label', t('ui.nueva_utileria')), row);
  return form;
}

/* ---------- 5. Escenas ---------- */
function ensureScenes() {          // 'scenes' va antes de 'shots' en el archivo; no se crea hasta que hace falta
  const sc = S.script;
  if (!sc.scenes) { const shots = sc.shots; delete sc.shots; sc.scenes = []; sc.shots = shots; }
  return sc.scenes;
}
const shotsOfScene = scene => S.script.shots.filter(s => s.scene === scene.id);
const memberIds = scene => [...(scene.cast || []), ...(scene.props || [])].map(m => m.id);

function scenesView(root) {
  root.append(heading(t('ui.donde_y_con_quien_ocurre'), t('ui.una_escena_elige_un_escenario')));
  const scenes = S.script.scenes || [];
  S.scene = Math.max(0, Math.min(S.scene, scenes.length - 1));
  if (S.series && S.series.episodes.length) { const d = el('details', 'panel pad'); d.append(el('summary', '', t('ui.importar_o_duplicar_una_escena')), importScenePanel()); root.append(d); }
  const layout = el('div', 'shots-layout'); root.append(layout);
  const left = el('div', 'panel'); const lt = el('div', 'panel-title'); lt.append(el('h2', '', t('ui.escenas_2')), el('span', 'meta', t('ui.biblioteca_escena_plano')));
  const list = el('div', 'shot-list'); list.id = 'scene-list';
  const tools = el('div', 'shot-tools');
  tools.append(button(t('ui.nueva'), addScene, 'button small'), button(t('ui.duplicar'), duplicateScene, 'button small'),
    button('↑', () => moveScene(-1), 'button small'), button('↓', () => moveScene(1), 'button small'), button(t('ui.eliminar'), deleteScene, 'button small danger'));
  left.append(lt, list, tools);
  const right = el('div', 'stack'); right.id = 'scene-editor';
  layout.append(left, right);
  renderSceneList(); renderSceneEditor();
}

function renderSceneList() {
  const list = $('#scene-list'); if (!list) return;
  list.replaceChildren();
  const scenes = S.script.scenes || [];
  if (!scenes.length) list.append(el('p', 'hint pad', t('ui.todavia_no_hay_escenas_crea')));
  scenes.forEach((scene, i) => {
    const item = el('button', 'shot-item'); item.type = 'button';
    item.classList.toggle('active', i === S.scene);
    item.classList.toggle('error', S.errors.some(e => (parsePath(e.path) || {}).scene === i));
    const top = el('div', 'top'); top.append(sceneChip(scene.id), el('span', '', tp('ui.n_plano', shotsOfScene(scene).length)));
    item.append(top, el('div', 'desc', scene.title || scene.set || '—'));
    item.addEventListener('click', () => { S.scene = i; renderSceneList(); renderSceneEditor(); });
    list.append(item);
  });
}

function addScene() {
  const set = Object.keys(S.script.sets || {})[0];
  if (!set) throw new Error(t('ui.la_biblioteca_no_tiene_escenarios'));
  const scenes = ensureScenes();
  scenes.push({ id: uniqueId(t('ui.default_scene_id'), scenes.map(s => s.id)), title: '', description: '', set, cast: [], props: [] });
  S.scene = scenes.length - 1; edited(false); show('scenes');
}
function duplicateScene() {
  const scenes = S.script.scenes || [];
  if (!scenes[S.scene]) throw new Error(t('ui.no_hay_ninguna_escena_que'));
  const copy = clone(scenes[S.scene]); copy.id = uniqueId(t('ui.copia', { id: copy.id }), scenes.map(s => s.id));
  scenes.splice(S.scene + 1, 0, copy); S.scene++; edited(false); show('scenes');
}
function moveScene(dir) {
  const scenes = S.script.scenes || []; const to = S.scene + dir;
  if (!scenes[S.scene] || to < 0 || to >= scenes.length) return;
  [scenes[S.scene], scenes[to]] = [scenes[to], scenes[S.scene]]; S.scene = to; edited(false); renderSceneList();
}
function deleteScene() {
  const scenes = S.script.scenes || []; const scene = scenes[S.scene];
  if (!scene) throw new Error(t('ui.no_hay_ninguna_escena_que_2'));
  const users = shotsOfScene(scene);
  if (users.length) throw new Error(t('ui.no_se_puede_eliminar_la', { id: scene.id, users: users.map(s => s.id).join(', ') }));
  if (!confirm(t('ui.eliminar_la_escena_no_se', { id: scene.id }))) return;
  scenes.splice(S.scene, 1); S.scene = Math.max(0, S.scene - 1); edited(false); show('scenes');
}

function renderSceneErrors() {
  const box = $('#scene-errors'); if (!box) return;
  box.replaceChildren();
  const errs = S.errors.filter(e => (parsePath(e.path) || {}).scene === S.scene);
  if (!errs.length) return;
  const ul = el('ul', 'error-list');
  for (const e of errs) { const li = el('li'); li.append(el('code', '', e.path), ' ', e.message); ul.append(li); }
  box.append(el('p', 'error-text', tp('ui.n_problema_scene', errs.length)), ul);
}

function renderSceneEditor() {
  const host = $('#scene-editor'); if (!host) return;
  host.replaceChildren();
  const scene = (S.script.scenes || [])[S.scene];
  if (!scene) { host.append(el('div', 'empty', t('ui.crea_una_escena_para_elegir'))); return; }
  const main = panel(t('ui.escena_2'), t('ui.id_titulo_escenario'));
  main.body.append(Object.assign(el('div'), { id: 'scene-errors' }));
  const id = el('input'); id.value = scene.id;
  id.addEventListener('change', () => {
    const next = id.value.trim();
    if (next === scene.id) return;
    if (!next || (S.script.scenes || []).some(s => s !== scene && s.id === next)) { toast(next ? t('ui.ya_existe_la_escena', { next }) : t('ui.la_escena_necesita_un_id')); id.value = scene.id; return; }
    for (const shot of shotsOfScene(scene)) shot.scene = next;
    scene.id = next; edited(false); renderSceneList(); renderSceneEditor();
  });
  const title = textInput(scene.title, v => { scene.title = v; edited(false); renderSceneList(); });
  const desc = el('textarea'); desc.rows = 2; desc.value = scene.description || '';
  desc.addEventListener('input', () => { scene.description = desc.value; edited(false); });
  const preview = el('img', 'set-preview'); preview.alt = t('ui.vista_previa_del_escenario');
  const showSet = () => { preview.src = `${v2('setframe')}?set=${encodeURIComponent(scene.set)}&w=480&v=${S.setVersion}`; };
  const set = selectInput(Object.keys(S.script.sets || {}), scene.set, v => { scene.set = v; edited(false); showSet(); });
  const grid = el('div', 'two-col'); grid.append(field(t('ui.id_de_la_escena'), id), field(t('ui.titulo'), title));
  const users = shotsOfScene(scene);
  const link = button(t('ui.ver_sus_planos'), () => { S.sceneFilter = scene.id; const at = S.script.shots.findIndex(s => s.scene === scene.id); if (at >= 0) { S.shot = at; S.time = 0; S.editor = null; } show('shots'); }, 'button small');
  main.body.append(grid, field(t('ui.descripcion'), desc), field(t('ui.escenario_de_la_biblioteca'), set), preview,
    el('p', 'hint', t('ui.escenario_tal_como_esta_guardado')));
  const info = el('div', 'row'); info.append(el('span', 'muted', users.length ? t('ui.planos_2', { users: users.map(s => s.id).join(', ') }) : t('ui.ningun_plano_usa_esta_escena')));
  if (users.length) info.append(link);
  main.body.append(info);
  if (scene.set) showSet();
  host.append(main.box, castPanel(scene), scenePropsPanel(scene));
  renderSceneErrors();
}

/* Renombra un miembro del reparto o de la utilería en la escena y en los planos que lo usan. */
function renameMember(scene, section, member, oldId, input) {
  const next = input.value.trim();
  if (next === oldId) return oldId;
  if (!next || next === 'shot' || memberIds(scene).filter(x => x !== oldId).includes(next)) { toast(t('ui.id_no_valido_o_repetido')); input.value = oldId; return oldId; }
  const key = section === 'cast' ? 'actors' : 'props';
  const retarget = list => { for (const p of list || []) if (p.spec && p.spec.anchor && p.spec.anchor.actor === oldId) p.spec.anchor.actor = next; };
  retarget(scene.props);
  for (const shot of shotsOfScene(scene)) {
    for (const m of shot[key] || []) if (m.id === oldId) m.id = next;
    renameTarget(shot, oldId, next); retarget(shot.props);
  }
  member.id = next; edited(false);
  return next;
}
function removeFromScene(scene, section, member) {
  const key = section === 'cast' ? 'actors' : 'props';
  const users = shotsOfScene(scene).filter(s => (s[key] || []).some(m => m.id === member.id));
  const n = users.reduce((sum, s) => sum + actionCount(s, member.id), 0);
  const text = users.length ? t('ui.member_in_shots', { id: member.id, shots: tp('ui.n_plano', users.length), list: users.map(s => s.id).join(', '), actions: tp('ui.n_accion', n) })
    : t('ui.quitar_de_la_escena', { id: member.id });
  if (!confirm(text)) return;
  for (const shot of users) { shot[key] = shot[key].filter(m => m.id !== member.id); if (shot.actions) shot.actions = shot.actions.filter(a => a.on !== member.id); }
  scene[section] = scene[section].filter(m => m !== member);
  S.editor = null; edited(false); renderSceneEditor();
}

function castPanel(scene) {
  const box = panel(t('ui.reparto'), t('ui.instancias_de_personajes_de_la'));
  const channelNames = Object.keys(S.catalogue.channels);
  const characters = Object.keys(S.script.characters || {});
  const list = el('div', 'mini-list');
  (scene.cast || []).forEach(member => {
    const item = el('div', 'mini-item');
    let known = member.id;
    const id = el('input', 'mid'); id.value = member.id || '';
    id.addEventListener('change', () => { known = renameMember(scene, 'cast', member, known, id); });
    const character = selectInput(characters, member.character || member.id, v => { member.character = v; edited(false); }, 'mid');
    item.append(field(t('ui.id_en_la_escena'), id), field(t('ui.personaje'), character), button(t('ui.quitar_del_reparto'), () => removeFromScene(scene, 'cast', member), 'button small danger'));
    item.append(startEditor(member, channelNames));
    list.append(item);
  });
  if (!(scene.cast || []).length) list.append(el('p', 'hint', t('ui.el_reparto_esta_vacio_anade')));
  const pick = selectInput(characters, characters[0], () => {}, 'mid');
  const add = el('div', 'row');
  add.append(pick, button(t('ui.anadir_al_reparto'), () => {
    if (!pick.value) throw new Error(t('ui.la_biblioteca_no_tiene_personajes'));
    const ground = (S.sets[scene.set] && S.sets[scene.set].ground_y) || 690;
    (scene.cast = scene.cast || []).push({ id: uniqueId(pick.value, memberIds(scene)), character: pick.value, start: { x: 640, y: ground, scale: 0.66 } });
    edited(false); renderSceneEditor();
  }, 'button small'));
  box.body.append(list, add, el('p', 'hint', t('ui.puedes_poner_varias_instancias_del')));
  return box.box;
}

function scenePropsPanel(scene) {
  const box = panel(t('ui.utileria_de_la_escena'), t('ui.props_de_la_biblioteca_disponibles'));
  const library = Object.keys(S.script.props || {});
  const list = el('div', 'mini-list');
  (scene.props || []).forEach(prop => {
    const item = el('div', 'mini-item');
    let known = prop.id;
    const id = el('input', 'mid'); id.value = prop.id || '';
    id.addEventListener('change', () => { known = renameMember(scene, 'props', prop, known, id); });
    const lib = selectInput(library, prop.prop || prop.id, v => { prop.prop = v; edited(false); }, 'mid');
    item.append(field(t('ui.id_en_la_escena'), id), field(t('ui.prop_de_la_biblioteca'), lib), button(t('ui.quitar_de_la_escena_2'), () => removeFromScene(scene, 'props', prop), 'button small danger'));
    const spec = jsonArea(prop.spec === undefined ? {} : prop.spec, v => { if (v === undefined) delete prop.spec; else prop.spec = v; edited(false); }, 'code short');
    const wrap = field(t('ui.spec_se_mezcla_sobre_la'), spec, 'field'); wrap.classList.add('wide');
    item.append(wrap); list.append(item);
  });
  if (!(scene.props || []).length) list.append(el('p', 'hint', t('ui.sin_utileria_los_verbos_que')));
  const pick = selectInput(library, library[0], () => {}, 'mid');
  const add = el('div', 'row');
  add.append(pick, button(t('ui.anadir_utileria'), () => {
    if (!pick.value) throw new Error(t('ui.la_biblioteca_de_utileria_esta'));
    (scene.props = scene.props || []).push({ id: uniqueId(pick.value, memberIds(scene)), prop: pick.value, spec: {} });
    edited(false); renderSceneEditor();
  }, 'button small'));
  box.body.append(list, add);
  return box.box;
}

/* ---------- 6. Planos ---------- */
const P = { busy: false, again: false, timer: null };
const cur = () => S.script.shots[S.shot];

function parsePath(path) {
  const m = /^shots\[(\d+)\](?:\.(actions|actors|props)\[(\d+)\])?(?:\.(.*))?$/.exec(path || '');
  if (m) return { shot: +m[1], kind: m[2] || null, index: m[3] === undefined ? null : +m[3], rest: m[4] || '' };
  const s = /^scenes\[(\d+)\](?:\.(cast|props)\[(\d+)\])?(?:\.(.*))?$/.exec(path || '');
  return s ? { scene: +s[1], kind: s[2] || null, index: s[3] === undefined ? null : +s[3], rest: s[4] || '' } : null;
}
function errorsIn(shotIndex, kind, index) {
  return S.errors.filter(e => {
    const p = parsePath(e.path);
    return p && p.shot === shotIndex && (kind === undefined || (p.kind === kind && (index === undefined || p.index === index)));
  });
}

function shotsView(root) {
  const sc = S.script;
  if (!sc.shots.length) {
    root.append(heading(t('ui.aun_no_hay_planos'), t('ui.anade_el_primero_para_empezar')));
    root.append(button(t('ui.nuevo_plano'), () => { addShot(); show('shots'); }, 'button orange'));
    return;
  }
  S.shot = Math.min(S.shot, sc.shots.length - 1);
  root.append(Object.assign(el('div'), { id: 'shots-errors' }));
  const layout = el('div', 'shots-layout'); root.append(layout);

  const left = el('div', 'panel'); const lt = el('div', 'panel-title'); lt.append(el('h2', '', t('ui.planos_3')), el('span', 'meta', t('ui.orden_de_la_pelicula')));
  const list = el('div', 'shot-list'); list.id = 'shot-list';
  const tools = el('div', 'shot-tools');
  tools.append(button(t('ui.nuevo'), () => { addShot(); }, 'button small'), button(t('ui.duplicar'), duplicateShot, 'button small'),
    button('↑', () => moveShot(-1), 'button small'), button('↓', () => moveShot(1), 'button small'), button(t('ui.eliminar'), deleteShot, 'button small danger'));
  const filter = el('div', 'shot-filter'); filter.id = 'scene-filter';
  left.append(lt, filter, list, tools);

  const right = el('div', 'stack');
  right.append(previewPanel());
  const fields = panel(t('ui.plano_2'), t('ui.id_duracion_escena')); fields.body.id = 'shot-fields';
  const cast = panel(t('ui.actores_y_utileria'), t('ui.valores_iniciales_start_y_piezas')); cast.body.id = 'shot-cast';
  const acts = panel(t('ui.acciones'), t('ui.una_lista_ordenada_el_orden')); acts.body.id = 'actions-panel';
  acts.body.className = ''; acts.body.append(Object.assign(el('div', 'pad'), { id: 'actions-table' }), Object.assign(el('div'), { id: 'action-editor' }));
  right.append(fields.box, cast.box, acts.box);
  layout.append(left, right);

  renderErrorPanel(); renderSceneFilter(); renderShotList(); renderShotFields(); renderActors(); renderActions(); renderEditor();
  syncScrubber(); schedulePreview(0);
}

function renderErrorPanel() {
  const box = $('#shots-errors'); if (!box) return;
  box.replaceChildren();
  if (!S.errors.length) return;
  const d = el('details', 'errors-panel'); d.open = true;
  d.append(el('summary', '', tp('ui.n_problema_script', S.errors.length)));
  const ul = el('ul');
  for (const e of S.errors) {
    const li = el('li'); const p = parsePath(e.path);
    const text = el('button', '', e.message); text.type = 'button';
    text.addEventListener('click', () => { if (p) goToError(p); });
    li.append(el('code', '', e.path || 'global'), ' ', text); ul.append(li);
  }
  d.append(ul); box.append(d);
}
function goToError(p) {
  if (p.scene !== undefined) { S.scene = p.scene; show('scenes'); return; }
  S.sceneFilter = 'all';
  S.shot = p.shot; S.time = 0; S.filter = 'all'; S.editor = null;
  show('shots');
  if (p.kind === 'actions' && (cur().actions || [])[p.index]) openEditor(p.index);
}

const inFilter = shot => S.sceneFilter === 'all' || (S.sceneFilter === '@none' ? !shot.scene : shot.scene === S.sceneFilter);
function selectShot(i) {
  S.shot = i; S.time = 0; S.editor = null; S.filter = 'all';
  renderShotList(); renderShotFields(); renderActors(); renderActions(); renderEditor(); syncScrubber(); schedulePreview(0);
}
function renderSceneFilter() {
  const host = $('#scene-filter'); if (!host) return;
  host.replaceChildren();
  const scenes = S.script.scenes || [];
  if (!scenes.length && !S.script.shots.some(s => s.scene)) return;
  const options = [['all', t('ui.todas_las_escenas')], ...scenes.map(s => [s.id, s.title ? `${s.id} · ${s.title}` : s.id])];
  if (S.script.shots.some(s => !s.scene)) options.push(['@none', t('ui.planos_sin_escena')]);
  if (!options.some(o => o[0] === S.sceneFilter)) S.sceneFilter = 'all';
  host.append(field(t('ui.escena_2'), selectInput(options, S.sceneFilter, v => {
    S.sceneFilter = v;
    if (!inFilter(cur())) { const first = S.script.shots.findIndex(inFilter); if (first >= 0) { selectShot(first); return; } }
    renderShotList();
  })));
}

function renderShotList() {
  const list = $('#shot-list'); if (!list) return;
  list.replaceChildren();
  let shown = 0;
  S.script.shots.forEach((shot, i) => {
    if (!inFilter(shot)) return;
    shown++;
    const item = el('button', 'shot-item'); item.type = 'button';
    item.classList.toggle('active', i === S.shot); item.classList.toggle('error', errorsIn(i).length > 0);
    const top = el('div', 'top'); const name = el('div', 'name'); name.append(el('strong', '', shot.id || t('ui.sin_id')));
    if (shot.scene) name.append(sceneChip(shot.scene));
    top.append(name, el('span', '', seconds(shot.duration)));
    item.append(top, el('div', 'desc', shot.description || '—'));
    if (errorsIn(i).length) item.title = errorsIn(i).map(e => e.message).join('\n');
    item.addEventListener('click', () => { if (i !== S.shot) selectShot(i); });
    list.append(item);
  });
  if (!shown) list.append(el('p', 'hint pad', t('ui.no_hay_planos_en_esta')));
}

function newShot() {
  const sc = S.script; const scenes = sc.scenes || [];
  const wanted = S.sceneFilter !== 'all' && S.sceneFilter !== '@none' ? S.sceneFilter : (sc.shots[S.shot] && sc.shots[S.shot].scene) || (scenes[0] && scenes[0].id);
  const base = { id: uniqueId(t('ui.default_shot_id'), sc.shots.map(s => s.id)), duration: 3 };
  if (wanted && sceneById(wanted)) return { ...base, scene: wanted, description: '', actors: [], props: [], actions: [] };
  const first = sc.shots[0];
  if (!first && !scenes.length) throw new Error(t('ui.crea_primero_una_escena_vista'));
  return { ...base, set: first ? first.set : Object.keys(sc.sets || {})[0], description: '', actors: [], props: [], actions: [] };
}
function insertShot(shot, at) {
  S.script.shots.splice(at, 0, shot); S.shot = at; S.time = 0; S.editor = null; S.filter = 'all';
  edited(false); show('shots');
}
function addShot() {
  const shot = newShot(); const shots = S.script.shots;
  let at = shots.length ? S.shot + 1 : 0;
  if (shot.scene && shots[S.shot] && shots[S.shot].scene !== shot.scene) { const last = shots.map(s => s.scene).lastIndexOf(shot.scene); at = last >= 0 ? last + 1 : shots.length; }
  insertShot(shot, at);
}
function duplicateShot() {
  const copy = clone(cur()); copy.id = uniqueId(t('ui.copia', { id: copy.id }), S.script.shots.map(s => s.id));
  insertShot(copy, S.shot + 1);
}
function moveShot(dir) {
  const shots = S.script.shots;
  let to = S.shot + dir;
  while (to >= 0 && to < shots.length && !inFilter(shots[to])) to += dir;      // salta los planos que el filtro oculta
  if (to < 0 || to >= shots.length) return;
  const [moved] = shots.splice(S.shot, 1); shots.splice(to, 0, moved); S.shot = to;
  edited(false); renderShotList(); renderErrorPanel();
}
function deleteShot() {
  if (!confirm(t('ui.eliminar_el_plano_y_todas', { cur: cur().id }))) return;
  S.script.shots.splice(S.shot, 1); S.shot = Math.max(0, S.shot - 1); S.time = 0; S.editor = null;
  edited(false); show('shots');
}

/* vista previa y reproducción */
function previewPanel() {
  const box = el('div', 'panel');
  const stage = el('div', 'stage');
  const img = el('img'); img.id = 'preview-img'; img.alt = t('ui.vista_previa_del_plano');
  const label = el('div', 'stage-label'); label.id = 'preview-label';
  const busy = el('div', 'busy hidden'); busy.id = 'preview-busy';
  const err = el('div', 'stage-error hidden'); err.id = 'preview-error';
  stage.append(img, label, busy, err);
  const transport = el('div', 'transport');
  const play = el('button', 'play', '▶'); play.type = 'button'; play.id = 'play'; play.setAttribute('aria-label', t('ui.reproducir_o_pausar'));
  play.addEventListener('click', () => { S.playing ? stopPlaying() : startPlaying(); });
  const range = el('input'); range.type = 'range'; range.id = 'scrubber'; range.min = '0'; range.step = '0.01'; range.value = '0';
  range.setAttribute('aria-label', t('ui.tiempo_del_plano'));
  range.addEventListener('input', () => { S.time = Number(range.value); syncScrubber(false); schedulePreview(0); });
  const code = el('span', 'timecode'); code.id = 'timecode';
  const width = selectInput([[320, '320 px'], [480, '480 px'], [640, '640 px'], [960, '960 px'], [1280, '1280 px']], S.width, v => { S.width = Number(v); schedulePreview(0); }, 'narrow');
  width.setAttribute('aria-label', t('ui.ancho_de_la_vista_previa'));
  transport.append(play, range, code, width);
  box.append(stage, transport, el('div', 'preview-note', t('ui.vista_previa_del_guion_con')));
  return box;
}
function syncScrubber(updateRange = true) {
  const range = $('#scrubber'); if (!range) return;
  const shot = cur(); const dur = Number(shot.duration) || 0;
  S.time = Math.max(0, Math.min(S.time, dur));
  range.max = String(dur);
  if (updateRange) range.value = String(S.time);
  $('#timecode').textContent = `${S.time.toFixed(2)} / ${dur.toFixed(2)} s`;
  $('#preview-label').textContent = `${shot.id} · ${S.time.toFixed(2)} s`;
}
function schedulePreview(delay = 0) { clearTimeout(P.timer); P.timer = setTimeout(requestPreview, delay); }
async function requestPreview() {
  const img = $('#preview-img');
  if (S.view !== 'shots' || !img || !S.script.shots.length) return;
  if (P.busy) { P.again = true; return; }       // una petición a la vez; la última posición pedida se dibuja al terminar
  P.busy = true; $('#preview-busy').classList.remove('hidden');
  const shot = cur();
  try {
    const response = await fetch(withLang(v2('preview')), { method: 'POST', headers: langHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ script: S.script, shot: shot.id, t: Math.min(S.time, shot.duration), w: S.width }) });
    if (!response.ok) { const data = await response.json().catch(() => ({})); throw new Error(data.error || t('ui.no_se_pudo_dibujar_el')); }
    const url = await toDataUrl(await response.blob());
    if (img.isConnected) { img.src = url; $('#preview-error').classList.add('hidden'); }
  } catch (e) {
    const box = $('#preview-error');
    if (box) { box.textContent = e.message; box.classList.remove('hidden'); }
  } finally {
    P.busy = false;
    const busy = $('#preview-busy'); if (busy) busy.classList.add('hidden');
    if (P.again) { P.again = false; requestPreview(); }
  }
}
function stopPlaying() { S.playing = false; const b = $('#play'); if (b) b.textContent = '▶'; }
async function startPlaying() {
  S.playing = true; $('#play').textContent = '❚❚';
  while (S.playing && S.view === 'shots' && $('#preview-img')) {
    if (P.busy) { await sleep(30); continue; }       // se descartan los fotogramas mientras hay uno pendiente
    const shot = cur();
    S.time += PLAY_STEP; if (S.time >= shot.duration) S.time = 0;
    syncScrubber();
    await requestPreview();
    await sleep(20);
  }
  stopPlaying();
}

/* campos del plano */
function renderShotFields() {
  const body = $('#shot-fields'); if (!body) return;
  body.replaceChildren();
  const shot = cur(); const i = S.shot;
  const grid = el('div', 'shot-fields');
  const id = textInput(shot.id, v => { shot.id = v; edited(false); renderShotList(); syncScrubber(false); }); id.id = `f${++idCounter}`;
  const dur = numberInput(shot.duration, n => { shot.duration = n; edited(); renderShotList(); syncScrubber(); });
  const inScene = shot.scene !== undefined;
  const place = inScene
    ? field(t('ui.escena_2'), selectInput((S.script.scenes || []).map(s => [s.id, s.title ? `${s.id} · ${s.title}` : s.id]), shot.scene, v => changeScene(shot, v)))
    : field(t('ui.escenario'), selectInput(Object.keys(S.script.sets || {}), shot.set, v => { shot.set = v; edited(); }));
  grid.append(field('ID', id), field(t('ui.duracion_s'), dur), place);
  const desc = el('textarea'); desc.value = shot.description || ''; desc.rows = 2;
  desc.addEventListener('input', () => { shot.description = desc.value; edited(false); renderShotList(); });
  body.append(grid);
  const scene = inScene ? sceneById(shot.scene) : null;
  if (scene) body.append(el('p', 'hint', t('ui.escenario_de_la_escena_2', { set: scene.set })));
  body.append(field(t('ui.descripcion'), desc));
  if (errorsIn(i).filter(e => !parsePath(e.path).kind).length) body.append(el('p', 'error-text', errorsIn(i).filter(e => !parsePath(e.path).kind).map(e => e.message).join(' · ')));
}

function actorIds(shot) { return (shot.actors || []).map(a => a.id); }
function propIds(shot) { return (shot.props || []).map(p => p.id); }

function renameTarget(shot, oldId, newId) {
  if (oldId === newId || !oldId) return;
  for (const a of shot.actions || []) if (a.on === oldId) a.on = newId;
  for (const a of shot.actions || []) if (a.target === oldId) a.target = newId;
}

function renderActors() {
  const body = $('#shot-cast'); if (!body) return;
  if (cur().scene !== undefined) { renderSceneCast(); return; }
  body.replaceChildren();
  const shot = cur(); const i = S.shot;
  const sc = S.script;
  const channelNames = Object.keys(S.catalogue.channels);

  body.append(el('div', 'inspector-label', t('ui.actores')));
  const actors = el('div', 'mini-list');
  (shot.actors || []).forEach((actor, j) => {
    const item = el('div', 'mini-item'); item.dataset.kind = 'actors'; item.dataset.index = j; item.classList.toggle('error', errorsIn(i, 'actors', j).length > 0);
    if (errorsIn(i, 'actors', j).length) item.title = errorsIn(i, 'actors', j).map(e => e.message).join('\n');
    let known = actor.id;
    const id = el('input', 'mid'); id.value = actor.id || ''; id.placeholder = 'id';
    id.addEventListener('change', () => { actor.id = id.value; renameTarget(shot, known, id.value); known = id.value; edited(); renderActions(); renderEditor(); });
    const character = selectInput(Object.keys(sc.characters || {}), actor.character || actor.id, v => { actor.character = v; edited(); }, 'mid');
    item.append(field('ID', id, 'field'), field(t('ui.personaje'), character, 'field'), button(t('ui.quitar'), () => {
      if (!confirm(t('ui.quitar_el_actor_sus_acciones', { id: actor.id }))) return;
      shot.actors.splice(j, 1); edited(); renderActors(); renderActions();
    }, 'button small danger'));
    item.append(startEditor(actor, channelNames));
    actors.append(item);
  });
  body.append(actors, button(t('ui.actor'), () => {
    const cid = Object.keys(sc.characters || {})[0];
    if (!cid) throw new Error(t('ui.el_guion_no_declara_personajes'));
    (shot.actors = shot.actors || []).push({ id: uniqueId(cid, actorIds(shot).concat(propIds(shot))), character: cid, start: {} }); edited(); renderActors();
  }, 'button small'));

  body.append(el('div', 'inspector-label', t('ui.utileria_del_plano')));
  const props = el('div', 'mini-list');
  (shot.props || []).forEach((prop, j) => {
    const item = el('div', 'mini-item'); item.dataset.kind = 'props'; item.dataset.index = j; item.classList.toggle('error', errorsIn(i, 'props', j).length > 0);
    if (errorsIn(i, 'props', j).length) item.title = errorsIn(i, 'props', j).map(e => e.message).join('\n');
    let known = prop.id;
    const id = el('input', 'mid'); id.value = prop.id || '';
    id.addEventListener('change', () => { prop.id = id.value; renameTarget(shot, known, id.value); known = id.value; edited(); renderActions(); renderEditor(); });
    const lib = selectInput(Object.keys(sc.props || {}), prop.prop, v => { prop.prop = v; edited(); }, 'mid');
    item.append(field('ID', id, 'field'), field(t('ui.prop_de_la_biblioteca'), lib, 'field'), button(t('ui.quitar'), () => {
      if (!confirm(t('ui.quitar_la_utileria', { id: prop.id }))) return;
      shot.props.splice(j, 1); edited(); renderActors(); renderActions();
    }, 'button small danger'));
    const spec = jsonArea(prop.spec === undefined ? {} : prop.spec, v => { if (v === undefined) delete prop.spec; else prop.spec = v; edited(); }, 'code short');
    const specWrap = field(t('ui.spec_se_mezcla_sobre_la_2'), spec, 'field'); specWrap.style.flexBasis = '100%';
    item.append(specWrap);
    props.append(item);
  });
  body.append(props, button(t('ui.utileria_2'), () => {
    const name = Object.keys(sc.props || {})[0];
    if (!name) throw new Error(t('ui.la_biblioteca_de_utileria_esta_2'));
    (shot.props = shot.props || []).push({ id: uniqueId(name, actorIds(shot).concat(propIds(shot))), prop: name, spec: {} }); edited(); renderActors();
  }, 'button small'));
}

/* planos dentro de una escena: quién del reparto aparece en el plano */
function toggleMember(shot, section, id, on) {
  const list = shot[section] = shot[section] || [];
  if (on) list.push({ id });
  else {
    const n = actionCount(shot, id);
    if (n && !confirm(t('ui.member_has_actions', { id, actions: tp('ui.n_accion', n) }))) { renderActors(); return; }
    shot[section] = list.filter(m => m.id !== id);
    if (shot.actions) shot.actions = shot.actions.filter(a => a.on !== id);
    S.editor = null;
  }
  edited(); renderActors(); renderActions(); renderEditor();
}

function changeScene(shot, next) {
  const scene = sceneById(next); if (!scene) return;
  const lost = [...(shot.actors || []).filter(a => !(scene.cast || []).some(m => m.id === a.id)),
    ...(shot.props || []).filter(p => !(scene.props || []).some(m => m.id === p.id))].map(m => m.id);
  if (lost.length) {
    const n = lost.reduce((sum, id) => sum + actionCount(shot, id), 0);
    if (!confirm(t('ui.lost_from_scene', { scene: next, list: lost.join(', '), actions: tp('ui.n_accion', n) }))) { renderShotFields(); return; }
    shot.actors = (shot.actors || []).filter(a => !lost.includes(a.id)); shot.props = (shot.props || []).filter(p => !lost.includes(p.id));
    shot.actions = (shot.actions || []).filter(a => !lost.includes(a.on)); S.editor = null;
  }
  shot.scene = next; edited();
  renderShotList(); renderShotFields(); renderActors(); renderActions(); renderEditor();
}

function describeStart(values) {
  const text = Object.entries(values || {}).map(([k, v]) => `${k}=${toText(v)}`).join(', ');
  return text ? t('ui.por_defecto_en_la_escena', { text }) : t('ui.la_escena_no_fija_valores');
}

function renderSceneCast() {
  const body = $('#shot-cast'); if (!body) return;
  body.replaceChildren();
  const shot = cur(); const i = S.shot; const scene = sceneById(shot.scene);
  if (!scene) { body.append(el('p', 'error-text', t('ui.la_escena_no_existe_elige', { scene: shot.scene }))); return; }
  const channelNames = Object.keys(S.catalogue.channels);
  const row = (section, member, present, index, fields) => {
    const item = el('div', 'mini-item');
    if (index >= 0) {
      item.dataset.kind = section; item.dataset.index = index; item.classList.toggle('error', errorsIn(i, section, index).length > 0);
      if (errorsIn(i, section, index).length) item.title = errorsIn(i, section, index).map(e => e.message).join('\n');
    }
    const check = el('input', 'cast-check'); check.type = 'checkbox'; check.checked = present; check.id = `f${++idCounter}`;
    check.addEventListener('change', () => toggleMember(shot, section, member.id, check.checked));
    const label = el('label', 'cast-name', member.id); label.htmlFor = check.id;
    const origin = member.character || member.prop;
    if (origin && origin !== member.id) label.append(el('span', 'muted', ` (${origin})`));
    item.append(check, label);
    if (present) fields(item);
    return item;
  };

  body.append(el('div', 'inspector-label', t('ui.reparto_de_la_escena_quien', { scene: scene.id.toUpperCase() })));
  const actors = el('div', 'mini-list');
  for (const member of scene.cast || []) {
    const index = (shot.actors || []).findIndex(a => a.id === member.id);
    actors.append(row('actors', member, index >= 0, index, item => {
      item.append(el('span', 'hint grow', describeStart(member.start)), startEditor(shot.actors[index], channelNames));
    }));
  }
  if (!(scene.cast || []).length) actors.append(el('p', 'hint', t('ui.la_escena_no_tiene_reparto')));
  body.append(actors);

  body.append(el('div', 'inspector-label', t('ui.utileria_de_la_escena_en')));
  const props = el('div', 'mini-list');
  for (const member of scene.props || []) {
    const index = (shot.props || []).findIndex(p => p.id === member.id);
    props.append(row('props', member, index >= 0, index, item => {
      const prop = shot.props[index];
      const spec = jsonArea(prop.spec === undefined ? {} : prop.spec, v => { if (v === undefined) delete prop.spec; else prop.spec = v; edited(); }, 'code short');
      const wrap = field(t('ui.spec_de_este_plano_sobre', { v: JSON.stringify(member.spec || {}) }), spec, 'field'); wrap.classList.add('wide');
      item.append(wrap);
    }));
  }
  if (!(scene.props || []).length) props.append(el('p', 'hint', t('ui.la_escena_no_tiene_utileria')));
  body.append(props);

  const stray = [['actors', t('ui.word_actor'), scene.cast], ['props', t('ui.utileria'), scene.props]].flatMap(([section, label, members]) =>
    (shot[section] || []).map((m, index) => ({ section, label, m, index })).filter(x => !(members || []).some(c => c.id === x.m.id)));
  if (stray.length) body.append(el('div', 'inspector-label', t('ui.no_estan_en_la_escena')));
  for (const { section, label, m, index } of stray) {
    const item = el('div', 'mini-item error'); item.dataset.kind = section; item.dataset.index = index;
    item.append(el('span', 'grow', t('ui.no_esta_en_la_escena', { label, id: m.id, id2: scene.id })),
      button(t('ui.quitar_del_plano'), () => toggleMember(shot, section, m.id, false), 'button small danger'));
    body.append(item);
  }
}

/* start: pares canal/valor de un actor */
function startEditor(actor, channelNames) {
  const wrap = el('div', 'channels');
  const start = actor.start || {};
  const rows = el('div');
  const numeric = name => typeof S.catalogue.channels[name] === 'number' || S.catalogue.channels[name] === 'numeric';
  function draw() {
    rows.replaceChildren();
    for (const key of Object.keys(start)) {
      const row = el('div', 'channel-row');
      const options = channelNames.includes(key) ? channelNames : [key, ...channelNames];
      const select = selectInput(options, key, next => {
        if (next in start) { toast(t('ui.ese_canal_ya_esta_en')); select.value = key; return; }
        const rebuilt = {}; for (const [k, v] of Object.entries(start)) rebuilt[k === key ? next : k] = v;
        for (const k of Object.keys(start)) delete start[k]; Object.assign(start, rebuilt); edited(); draw();
      });
      const value = typeof start[key] === 'number' ? numberInput(start[key], n => { start[key] = n; edited(); }) : textInput(toText(start[key]), v => { start[key] = parseText(v, !numeric(key) && typeof S.catalogue.channels[key] === 'string'); edited(); });
      row.append(select, value, button('✕', () => { delete start[key]; edited(); draw(); }, 'button tiny danger'));
      rows.append(row);
    }
  }
  draw();
  wrap.append(rows, button(t('ui.canal'), () => {
    const free = channelNames.find(c => !(c in start)); if (!free) return;
    if (!actor.start) actor.start = start;
    start[free] = typeof S.catalogue.channels[free] === 'number' ? S.catalogue.channels[free] : (numeric(free) ? 0 : S.catalogue.channels[free]);
    edited(); draw();
  }, 'button tiny'));
  return wrap;
}

/* tabla de acciones */
function actionTime(a) {
  if ('t' in a) return seconds(a.t);
  if ('t0' in a || 't1' in a) return `${'t0' in a ? seconds(a.t0) : '?'} – ${'t1' in a ? seconds(a.t1) : '?'}`;
  return '—';
}
function actionSummary(a) {
  return Object.entries(a).filter(([k]) => !['on', 'do', 't', 't0', 't1'].includes(k)).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join('  ');
}
function visibleActions() {
  const actions = cur().actions || [];
  return actions.map((a, i) => i).filter(i => S.filter === 'all' || actions[i].on === S.filter);
}

function renderActions() {
  const host = $('#actions-table'); if (!host) return;
  host.replaceChildren();
  const shot = cur(); const i = S.shot;
  const bar = el('div', 'row');
  const targets = [['all', t('ui.todos_los_destinos')], ['shot', 'shot'], ...actorIds(shot).map(x => [x, x]), ...propIds(shot).map(x => [x, x])];
  if (!targets.some(t => t[0] === S.filter)) S.filter = 'all';
  bar.append(el('span', 'muted', t('ui.filtrar_por_destino')), selectInput(targets, S.filter, v => { S.filter = v; renderActions(); }, 'mid'),
    el('span', 'spacer'), button(t('ui.anadir_accion'), () => openEditor(-1), 'button small orange'));
  host.append(bar);
  const table = el('table', 'data'); const head = el('tr');
  ['#', t('ui.destino_on'), t('ui.verbo_do'), t('ui.tiempo'), t('ui.otros_argumentos'), ''].forEach(h => head.append(el('th', '', h)));
  const thead = el('thead'); thead.append(head); table.append(thead);
  const tb = el('tbody');
  const visible = visibleActions();
  for (const index of visible) {
    const a = shot.actions[index]; const tr = el('tr');
    const errs = errorsIn(i, 'actions', index);
    tr.classList.toggle('error', errs.length > 0); tr.classList.toggle('selected', !!S.editor && S.editor.index === index);
    if (errs.length) tr.title = errs.map(e => e.message).join('\n');
    tr.append(el('td', '', String(index + 1)), el('td', '', toText(a.on)), el('td', '', toText(a.do)), el('td', '', actionTime(a)));
    const summary = el('td', 'summary', actionSummary(a)); summary.title = actionSummary(a); tr.append(summary);
    const tools = el('td', 'actions');
    tools.append(button(t('ui.editar'), () => openEditor(index), 'button tiny'), ' ',
      button(t('ui.ir_al_momento'), () => { S.time = Number('t' in a ? a.t : 't0' in a ? a.t0 : 0) || 0; syncScrubber(); schedulePreview(0); }, 'button tiny'), ' ',
      button('↑', () => moveAction(index, -1), 'button tiny'), button('↓', () => moveAction(index, 1), 'button tiny'), ' ',
      button(t('ui.duplicar'), () => { shot.actions.splice(index + 1, 0, clone(a)); S.editor = null; edited(); renderActions(); renderEditor(); }, 'button tiny'),
      button(t('ui.eliminar'), () => {
        shot.actions.splice(index, 1);
        if (S.editor) S.editor = null;
        edited(); renderActions(); renderEditor();
      }, 'button tiny danger'));
    tr.append(tools); tb.append(tr);
  }
  if (!visible.length) { const tr = el('tr'); const td = el('td', 'muted', t('ui.no_hay_acciones_con_este')); td.colSpan = 6; tr.append(td); tb.append(tr); }
  table.append(tb);
  const wrap = el('div'); wrap.append(table); wrap.style.overflowX = 'auto';
  host.append(wrap);
}

function moveAction(index, dir) {
  const actions = cur().actions; const visible = visibleActions();
  const target = visible[visible.indexOf(index) + dir];
  if (target === undefined) return;
  const [moved] = actions.splice(index, 1); actions.splice(target, 0, moved);
  if (S.editor && S.editor.index === index) S.editor.index = target;
  edited(); renderActions();
}

/* formulario de edición, generado desde catalogue.verbs */
function targetType(shot, on) {
  if (on === 'shot') return 'shot';
  if (propIds(shot).includes(on)) return 'prop';
  return 'actor';
}
function verbEntry(type, verb) { return (S.catalogue.verbs[type] || []).find(v => v.name === verb); }

function editorFrom(index) {
  const shot = cur();
  const action = index >= 0 ? shot.actions[index] : { on: 'shot', do: S.catalogue.verbs.shot[0].name };
  const type = targetType(shot, action.on);
  const ed = { index, on: action.on, verb: action.do, values: {}, extras: [], leftover: {}, original: index >= 0 ? clone(action) : null };
  absorb(ed, action, type);
  return ed;
}
/* Reparte las claves de una acción entre parámetros del verbo, canales extra y claves desconocidas (que se conservan). */
function absorb(ed, action, type) {
  const entry = verbEntry(type, ed.verb);
  const names = (entry ? entry.params : []).map(p => p.name);
  ed.values = {}; ed.extras = []; ed.leftover = {};
  for (const [k, v] of Object.entries(action)) {
    if (k === 'on' || k === 'do') continue;
    const param = entry && entry.params.find(p => p.name === k);
    if (param) ed.values[k] = toText(v);
    else if (!entry || entry.kwargs) ed.extras.push({ k, v: toText(v) });
    else ed.leftover[k] = v;
  }
  return names;
}
function openEditor(index) { S.editor = editorFrom(index); renderActions(); renderEditor(); const host = $('#action-editor'); if (host) host.scrollIntoView({ block: 'nearest' }); }

function paramInput(p, ed, type) {
  const set = value => { if (value === '' || value === undefined) delete ed.values[p.name]; else ed.values[p.name] = value; };
  const current = ed.values[p.name] ?? '';
  const hasDefault = 'default' in p;
  const dflt = hasDefault ? toText(p.default) : '';
  let input;
  if (ed.verb === 'face' && p.name === 'name' && type === 'actor') {
    input = selectInput(S.catalogue.expressions, current, v => set(v));
  } else if (EASE_PARAMS.includes(p.name) && typeof p.default === 'string') {
    input = selectInput([['', t('ui.por_defecto', { default: p.default })], ...S.catalogue.eases], current, v => set(v));
  } else if (!p.varargs && (TIME_PARAMS.includes(p.name) || (typeof p.default === 'number'))) {
    input = el('input'); input.type = 'number'; input.step = 'any'; input.value = current; input.placeholder = dflt;
    input.addEventListener('input', () => set(input.value));
  } else {
    input = el('input'); input.type = 'text'; input.value = current;
    input.placeholder = p.varargs ? t('ui.3_8_4_05_lista') : hasDefault ? dflt : STRING_PARAMS.includes(p.name) ? '' : t('ui.numero_texto_o_json');
    input.addEventListener('input', () => set(input.value));
  }
  const label = p.name + (p.varargs ? ' *' : '');
  const f = field(label, input);
  if (p.required) f.firstChild.append(' ', Object.assign(el('span', '', '•'), { title: t('ui.obligatorio') }));
  return f;
}

function renderEditor() {
  const host = $('#action-editor'); if (!host) return;
  host.replaceChildren();
  const ed = S.editor; if (!ed) return;
  const shot = cur();
  const form = el('div', 'edit-form');
  form.append(el('h3', '', ed.index >= 0 ? t('ui.editar_la_accion', { ed: ed.index + 1 }) : t('ui.nueva_accion_se_anade_al')));
  const type = targetType(shot, ed.on);
  const targets = ['shot', ...actorIds(shot), ...propIds(shot)]; if (!targets.includes(ed.on)) targets.push(ed.on);
  const verbs = (S.catalogue.verbs[type] || []).map(v => v.name); if (!verbs.includes(ed.verb)) verbs.push(ed.verb);
  const top = el('div', 'row');
  const targetSelect = selectInput(targets, ed.on, v => {
    const old = targetType(shot, ed.on); ed.on = v; const nt = targetType(shot, v);
    if (nt !== old) { const keep = { ...ed.values }; const list = (S.catalogue.verbs[nt] || []).map(x => x.name); if (!list.includes(ed.verb)) ed.verb = list[0]; absorbKeep(ed, keep, nt); }
    renderEditor();
  }, 'mid');
  const verbSelect = selectInput(verbs, ed.verb, v => { const keep = { ...ed.values }; ed.verb = v; absorbKeep(ed, keep, type); renderEditor(); }, 'mid');
  top.append(field(t('ui.destino_on_2'), targetSelect), field(t('ui.verbo_do_2'), verbSelect));
  form.append(top);
  const entry = verbEntry(type, ed.verb);
  if (entry) {
    if (entry.doc) form.append(el('p', 'hint', verbDoc(type, entry)));
    const grid = el('div', 'param-grid');
    const ordered = [...entry.params.filter(p => p.required), ...entry.params.filter(p => !p.required)];
    for (const p of ordered) grid.append(paramInput(p, ed, type));
    form.append(grid);
  } else form.append(el('p', 'error-text', t('ui.el_verbo_no_existe_para', { verb: ed.verb })));
  if (!entry || entry.kwargs) {
    form.append(el('div', 'inspector-label', t('ui.canales_adicionales')));
    const names = Object.keys(S.catalogue.channels);
    ed.extras.forEach((extra, n) => {
      const row = el('div', 'channel-row');
      const options = names.includes(extra.k) ? names : [extra.k, ...names];
      row.append(selectInput(options, extra.k, v => { extra.k = v; }), textInput(extra.v, v => { extra.v = v; }), button('✕', () => { ed.extras.splice(n, 1); renderEditor(); }, 'button tiny danger'));
      form.append(row);
    });
    form.append(button(t('ui.anadir_canal'), () => { ed.extras.push({ k: names.find(c => !ed.extras.some(e => e.k === c)) || names[0], v: '0' }); renderEditor(); }, 'button tiny'));
  }
  if (Object.keys(ed.leftover).length) form.append(el('p', 'hint', t('ui.se_conservan_sin_cambios', { v: Object.keys(ed.leftover).join(', ') })));
  if (ed.index >= 0) {
    const errs = errorsIn(S.shot, 'actions', ed.index);
    if (errs.length) form.append(el('p', 'error-text', errs.map(e => e.message).join(' · ')));
  }
  const row = el('div', 'action-row');
  row.append(button(t('ui.aplicar'), () => applyEditor(entry), 'button orange'), button(t('ui.cancelar'), () => { S.editor = null; renderActions(); renderEditor(); }));
  form.append(row);
  host.append(form);
}
/* Al cambiar de verbo o destino se conservan los valores de los parámetros que también existen en el verbo nuevo. */
function absorbKeep(ed, values, type) {
  const entry = verbEntry(type, ed.verb);
  const names = entry ? entry.params.map(p => p.name) : [];
  ed.values = {}; for (const n of names) if (n in values) ed.values[n] = values[n];
  if (!entry || !entry.kwargs) ed.extras = [];
  ed.leftover = {};
}

function buildAction(ed, entry) {
  const out = { on: ed.on, do: ed.verb };
  for (const p of entry ? entry.params : []) {
    const raw = ed.values[p.name];
    if (raw === undefined || String(raw).trim() === '') continue;
    const asString = STRING_PARAMS.includes(p.name) || typeof p.default === 'string';
    const value = parseText(raw, asString);
    if (p.varargs && !Array.isArray(value)) throw new Error(t('ui.debe_ser_una_lista_json', { name: p.name }));
    out[p.name] = value;
  }
  for (const [k, v] of Object.entries(ed.leftover)) out[k] = v;
  for (const extra of ed.extras) {
    if (!extra.k) continue;
    if (extra.k in out) throw new Error(t('ui.el_canal_esta_repetido', { k: extra.k }));
    out[extra.k] = parseText(extra.v, false);
  }
  if (!ed.original) return out;
  const ordered = {};                                 // las acciones existentes conservan el orden de sus claves
  for (const k of Object.keys(ed.original)) if (k in out) ordered[k] = out[k];
  for (const k of Object.keys(out)) if (!(k in ordered)) ordered[k] = out[k];
  return ordered;
}

function applyEditor(entry) {
  const ed = S.editor; if (!ed) return;
  const action = buildAction(ed, entry);
  const shot = cur();
  if (ed.index >= 0) shot.actions[ed.index] = action; else (shot.actions = shot.actions || []).push(action);
  S.editor = null; edited(); renderActions(); renderEditor();
}

/* ---------- 7. Render ---------- */
function formatBytes(n) { return n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`; }

function renderView(root) {
  root.append(heading(t('ui.del_guion_al_video'), t('ui.el_render_es_determinista_y')));
  const grid = el('div', 'render-grid'); root.append(grid);
  const form = panel(t('ui.nuevo_render')); form.body.className = 'pad stack';
  const shot = selectInput([['', t('ui.pelicula_completa')], ...S.script.shots.map(s => [s.id, t('ui.solo_el_plano', { id: s.id, seconds: seconds(s.duration) })])], '', () => {});
  const width = selectInput([[480, t('ui.480_px_borrador')], [960, '960 px'], [1280, '1280 px'], [1920, t('ui.1920_px_completo')]], 960, () => {});
  const start = button(t('ui.iniciar_render'), async () => {
    if (S.job) throw new Error(t('ui.ya_hay_un_render_en'));
    if (isDirty() && !(await save())) return;
    const job = await api(v2('render'), { shot: shot.value || undefined, width: Number(width.value) });
    watchJob(job, shot.value ? t('ui.renderizando_el_plano', { value: shot.value }) : t('ui.renderizando_la_pelicula'));
  }, 'button orange');
  form.body.append(field(t('ui.que_renderizar'), shot), field(t('ui.ancho'), width), start,
    el('p', 'hint', t('ui.si_hay_cambios_sin_guardar')));
  const lib = panel(t('ui.renders_existentes'), `${S.renders.length}`);
  const player = el('video'); player.controls = true; player.className = 'hidden';
  const table = el('table', 'data'); const hr = el('tr'); [t('ui.archivo'), t('ui.tamano'), t('ui.fecha'), ''].forEach(h => hr.append(el('th', '', h)));
  const head = el('thead'); head.append(hr); table.append(head);
  const tb = el('tbody');
  for (const r of S.renders) {
    const tr = el('tr');
    tr.append(el('td', '', r.file), el('td', '', formatBytes(r.bytes)), el('td', '', new Date(r.modified * 1000).toLocaleString(I18N.lang)));
    const td = el('td', 'actions');
    td.append(button(t('ui.ver'), () => { player.src = r.url; player.classList.remove('hidden'); player.play().catch(() => {}); }, 'button tiny'), ' ');
    const link = el('a', 'button tiny', t('ui.abrir')); link.href = r.url; link.target = '_blank'; link.rel = 'noopener'; td.append(link);
    tr.append(td); tb.append(tr);
  }
  if (!S.renders.length) { const tr = el('tr'); const td = el('td', 'muted', t('ui.todavia_no_hay_renders')); td.colSpan = 4; tr.append(td); tb.append(tr); }
  table.append(tb);
  const wrap = el('div'); wrap.append(table); wrap.style.overflowX = 'auto';
  lib.body.append(wrap, player);
  grid.append(form.box, lib.box);
}

async function refreshRenders() {
  const data = await api(v2());
  S.renders = data.renders;
  if (S.view === 'render') show('render');
}

async function watchJob(job, title) {
  S.job = job.id;
  const bar = $('#job'); bar.classList.remove('hidden'); $('#job-title').textContent = title; $('#job-result').classList.add('hidden');
  $('#cancel-job').disabled = false;
  try {
    for (;;) {
      const j = await api(`/api/jobs/${job.id}`);
      $('#job-progress').max = j.total || 1; $('#job-progress').value = j.done || 0; $('#job-message').textContent = j.message || '';
      if (!['queued', 'running'].includes(j.status)) {
        $('#job-title').textContent = j.status === 'completed' ? t('ui.render_terminado') : j.status === 'cancelled' ? t('ui.render_cancelado') : t('ui.el_render_fallo');
        if (j.status === 'completed' && j.result && j.result.url) { const a = $('#job-result'); a.href = j.result.url; a.classList.remove('hidden'); }
        else if (j.status === 'failed') toast(j.message);
        break;
      }
      await sleep(700);
    }
  } finally { S.job = null; $('#cancel-job').disabled = true; }
  await attempt(refreshRenders);
}

/* ---------- series: capítulos y biblioteca compartida ---------- */
const sv2 = (action = '') => `/api/v2/series/${encodeURIComponent(S.series.id)}${action ? '/' + action : ''}`;
const episodePid = ep => `${S.series.id}/episodes/${ep}`;
const currentEpisode = () => (S.series && S.id && S.id.startsWith(`${S.series.id}/episodes/`) ? S.id.split('/')[2] : null);

async function loadSeries(sid) {
  const data = await api(`/api/v2/series/${encodeURIComponent(sid)}`);
  S.series = { ...data.series, episodes: data.episodes, counts: data.counts };
  S.assetId = sid; S.importableSeries = null;
}
async function refreshSeries() { if (S.series) await loadSeries(S.series.id); }
/* Abre una serie (y uno de sus capítulos, si hay). */
async function openSeries(sid, ep) {
  stopPlaying();
  await loadSeries(sid);
  const eps = S.series.episodes;
  const pick = ep && eps.some(e => e.id === ep) ? ep : (eps[0] && eps[0].id);
  if (pick) { if (!['episodes', 'library'].includes(S.view)) S.view = 'episodes'; await loadFilm(episodePid(pick)); }
  else { S.id = null; S.script = null; S.savedJson = ''; S.errors = []; S.view = 'episodes'; fillFilmSelect(); fillEpisodeSelect(); updateHeading(); show('episodes'); }
}
async function openEpisode(ep) {
  if (isDirty() && !confirm(t('ui.hay_cambios_sin_guardar_en'))) return false;
  await loadFilm(episodePid(ep));
  return true;
}
function fillEpisodeSelect() {
  const select = $('#episode-select'), box = $('#episode-box');
  box.classList.toggle('hidden', !S.series);
  document.querySelectorAll('.series-only').forEach(b => b.classList.toggle('hidden', !S.series));
  if (!S.series) return;
  select.replaceChildren(...S.series.episodes.map(e => { const o = el('option', '', `${e.id} · ${e.title}`); o.value = e.id; return o; }));
  if (!S.series.episodes.length) select.append(Object.assign(el('option', '', t('ui.sin_capitulos')), { value: '' }));
  select.value = currentEpisode() || '';
}

/* Una biblioteca de serie cambió desde su panel: se refleja en el capítulo abierto sin tocar sus ediciones. */
function syncSeriesItem(r, removed) {
  if (!S.script) return;
  const wasDirty = isDirty();
  const table = S.script[r.kind] = S.script[r.kind] || {};
  if (removed) delete table[r.id]; else table[r.id] = r.library[r.kind][r.id];
  if (r.kind === 'characters') { if (removed) delete S.characters[r.id]; else if (r.data) S.characters[r.id] = r.data; }
  if (r.kind === 'sets') { if (removed) delete S.sets[r.id]; else if (r.data) S.sets[r.id] = r.data; S.setVersion++; }
  if (!wasDirty) S.savedJson = JSON.stringify(S.script);
  updateHeading();
}
async function seriesLibraryCall(action, body, removed = false) {
  const r = await api(sv2(`library/${action}`), body);
  syncSeriesItem(r, removed);
  await refreshSeries(); fillEpisodeSelect();
  return r;
}

function episodesView(root) {
  const s = S.series;
  root.append(heading(t('ui.una_serie_muchos_capitulos'), t('ui.la_biblioteca_personajes_escenarios_y')));
  const meta = panel(t('ui.la_serie'), t('ui.revision_2', { s: s.revision ?? 0 })); meta.body.className = 'pad stack';
  const draft = { title: s.title || '', notes: s.notes || '', bible: s.bible || {} };
  const notes = el('textarea'); notes.value = draft.notes; notes.addEventListener('input', () => { draft.notes = notes.value; });
  meta.body.append(field(t('ui.titulo_de_la_serie'), textInput(draft.title, v => { draft.title = v; })), field(t('ui.notas_estilo_mundo_continuidad'), notes),
    field(t('ui.biblia_json_estilo_mundo_continuidad'), jsonArea(draft.bible, v => { if (v !== undefined) draft.bible = v; }, 'code short')),
    el('p', 'hint', t('ui.library_counts', { characters: tp('ui.n_personaje', s.counts.characters), sets: tp('ui.n_escenario', s.counts.sets), props: tp('ui.n_utileria', s.counts.props) })),
    button(t('ui.guardar_datos_de_la_serie'), async () => {
      const r = await api(sv2(), { ...draft, revision: s.revision });
      Object.assign(S.series, r.series); S.films = await api('/api/v2/films'); fillFilmSelect(); toast(t('ui.datos_de_la_serie_guardados')); show('episodes');
    }));
  const box = panel(t('ui.capitulos_2'), `${s.episodes.length}`);
  const table = el('table', 'data'); const hr = el('tr'); ['id', t('ui.titulo_2'), 'escenas', 'planos', t('ui.duracion'), ''].forEach(h => hr.append(el('th', '', h)));
  const head = el('thead'); head.append(hr); table.append(head);
  const tb = el('tbody');
  const open = currentEpisode();
  for (const e of s.episodes) {
    const tr = el('tr'); tr.classList.toggle('selected', e.id === open);
    tr.append(el('td', '', e.id), el('td', '', e.title + (e.broken ? t('ui.no_se_puede_leer') : '')), el('td', '', String(e.scenes)), el('td', '', String(e.shots)), el('td', '', seconds(e.seconds)));
    const td = el('td', 'actions');
    td.append(button(e.id === open ? t('ui.abierto') : t('ui.abrir'), async () => { if (await openEpisode(e.id)) { S.view = 'shots'; show('shots'); } }, 'button tiny'), ' ',
      button(t('ui.duplicar'), async () => {
        const as = prompt(t('ui.id_del_capitulo_copia_de', { id: e.id }), t('ui.copia', { id: e.id })); if (!as) return;
        const r = await api(sv2(`episodes/${encodeURIComponent(e.id)}/duplicate`), { as: as.trim() });
        await refreshSeries(); fillEpisodeSelect(); toast(t('ui.capitulo_creado', { id: r.id })); show('episodes');
      }, 'button tiny'), ' ',
      button(t('ui.renombrar'), async () => {
        const title = prompt(t('ui.titulo_del_capitulo', { id: e.id }), e.title); if (!title) return;
        const r = await api(sv2(`episodes/${encodeURIComponent(e.id)}/rename`), { title: title.trim() });
        if (e.id === open && S.script) { const dirty = isDirty(); S.script.title = r.title; S.script.revision = r.revision; if (!dirty) S.savedJson = JSON.stringify(S.script); updateHeading(); }
        await refreshSeries(); fillEpisodeSelect(); show('episodes');
      }, 'button tiny'), ' ',
      button(t('ui.borrar'), async () => {
        if (!confirm(`¿Borrar el capítulo «${e.id}» (${e.title})? Su carpeta pasa a papelera/episodes/ y la biblioteca de la serie no cambia.`)) return;
        const typed = prompt(t('ui.para_confirmar_escribe_el_id', { id: e.id })); if (typed !== e.id) throw new Error(t('ui.el_id_no_coincide_no'));
        await api(sv2(`episodes/${encodeURIComponent(e.id)}/delete`), { confirm: typed });
        S.films = await api('/api/v2/films');
        if (e.id === open) { S.script = null; S.id = null; S.savedJson = ''; await openSeries(S.series.id); } else { await refreshSeries(); fillEpisodeSelect(); show('episodes'); }
        toast(t('ui.capitulo_enviado_a_papelera', { id: e.id }));
      }, 'button tiny danger'));
    tr.append(td); tb.append(tr);
  }
  if (!s.episodes.length) { const tr = el('tr'); const td = el('td', 'muted', t('ui.todavia_no_hay_capitulos_crea')); td.colSpan = 6; tr.append(td); tb.append(tr); }
  table.append(tb);
  const wrap = el('div'); wrap.append(table); wrap.style.overflowX = 'auto';
  const title = el('input', 'grow'); title.placeholder = t('ui.titulo_del_nuevo_capitulo');
  const create = el('div', 'row'); create.append(title, button(t('ui.nuevo_capitulo'), async () => {
    if (isDirty() && !confirm(t('ui.hay_cambios_sin_guardar_en'))) return;
    const r = await api(sv2('episodes'), { title: title.value.trim() || undefined });
    S.films = await api('/api/v2/films'); await refreshSeries(); S.view = 'shots'; await loadFilm(r.pid); toast(t('ui.capitulo_creado', { id: r.id }));
  }, 'button orange'));
  box.body.append(wrap, create);
  const stack = el('div', 'stack'); stack.append(box.box, meta.box); root.append(stack);
  if (S.warnings && S.warnings.length) root.append(el('p', 'error-text', t('ui.avisos_de_este_capitulo') + S.warnings.map(w => `${w.path}: ${w.message}`).join(' · ')));
}

const LIB_FILTER = { q: '', kind: '', used: '', episode: '', limit: 60 };
let libTimer, libSeq = 0;
function libraryThumb(item) {
  if (item.kind === 'characters') return `${sv2('pose')}?character=${encodeURIComponent(item.id)}&turn=0&w=200`;
  if (item.kind === 'sets') return `${sv2('setframe')}?set=${encodeURIComponent(item.id)}&w=320`;
  return item.file ? fileUrl(item.file) : '';
}
function libraryView(root) {
  const s = S.series;
  root.append(heading(t('ui.la_biblioteca_de_la_serie'), t('ui.todo_lo_que_hay_aqui')));
  const bar = el('div', 'panel pad row');
  const reset = () => { LIB_FILTER.limit = 60; };
  const q = el('input', 'grow'); q.type = 'search'; q.placeholder = t('ui.buscar_por_id_o_nombre'); q.value = LIB_FILTER.q;
  const kind = selectInput([['', t('ui.todo')], ['characters', t('ui.personajes_2')], ['sets', t('ui.escenarios')], ['props', t('ui.utileria_3')]], LIB_FILTER.kind, v => { LIB_FILTER.kind = v; reset(); load(); });
  const used = selectInput([['', t('ui.usados_y_sin_usar')], ['1', t('ui.solo_usados')], ['0', t('ui.sin_usar')]], LIB_FILTER.used, v => { LIB_FILTER.used = v; reset(); load(); });
  const ep = selectInput([['', t('ui.cualquier_capitulo')], ...s.episodes.map(e => [e.id, `${e.id} · ${e.title}`])], LIB_FILTER.episode, v => { LIB_FILTER.episode = v; reset(); load(); });
  q.addEventListener('input', () => { LIB_FILTER.q = q.value; reset(); clearTimeout(libTimer); libTimer = setTimeout(load, 250); });
  bar.append(q, field(t('ui.tipo'), kind, 'field inline'), field(t('ui.uso'), used, 'field inline'), field(t('ui.capitulo'), ep, 'field inline'));
  const summary = el('p', 'hint'); const grid = el('div', 'lib-grid'); const more = el('div', 'row');
  const imports = el('details', 'panel pad'); imports.append(el('summary', '', t('ui.importar_de_otro_proyecto_otra')));
  const stack = el('div', 'stack'); imports.append(stack);
  for (const [k, t] of [['characters', t('ui.importar_un_personaje')], ['sets', t('ui.importar_un_escenario')], ['props', t('ui.importar_utileria')]]) stack.append(importPanel(k, t, true));
  root.append(bar, summary, grid, more, imports);
  async function load() {
    const seq = ++libSeq;
    const params = new URLSearchParams({ q: LIB_FILTER.q, kind: LIB_FILTER.kind, used: LIB_FILTER.used, episode: LIB_FILTER.episode, limit: LIB_FILTER.limit });
    const r = await api(`${sv2('library')}?${params}`).catch(e => { toast(e.message); return null; });
    if (!r || seq !== libSeq) return;
    summary.textContent = t('ui.de_elementos_personajes_escenarios_utilerias', { total: r.total, r: r.counts.characters + r.counts.sets + r.counts.props, characters: r.counts.characters, sets: r.counts.sets, props: r.counts.props });
    grid.replaceChildren(...r.items.map(libraryCard));
    if (!r.items.length) grid.append(el('p', 'hint', t('ui.nada_coincide_con_el_filtro')));
    more.replaceChildren();
    if (r.total > r.items.length) more.append(button(t('ui.mostrar_mas', { r: r.total - r.items.length }), async () => { LIB_FILTER.limit += 60; await load(); }, 'button small'));
  }
  load();
}
function libraryCard(item) {
  const card = el('div', 'panel lib-card');
  const url = libraryThumb(item);
  if (url) { const img = el('img'); img.loading = 'lazy'; img.alt = item.id; img.src = url; img.addEventListener('error', () => img.classList.add('hidden')); card.append(img); }
  const body = el('div', 'pad');
  body.append(el('strong', '', item.id), el('span', 'meta', ` ${libName(item.kind)}${item.name ? ' · ' + item.name : ''}`));
  const eps = Object.entries(item.episodes);
  const line = el('p', 'hint');
  if (!eps.length) line.textContent = t('ui.sin_usar_se_puede_quitar_2');
  else {
    line.append(t('ui.usado_en'));
    eps.forEach(([e, n], i) => {
      const a = el('a', 'link', `${e} (${n})`); a.href = '#'; a.title = t('ui.abrir_el_capitulo', { e });
      a.addEventListener('click', ev => { ev.preventDefault(); attempt(async () => { if (await openEpisode(e)) { S.view = 'shots'; show('shots'); } }); });
      if (i) line.append(' · ');
      line.append(a);
    });
  }
  const tools = el('div', 'row');
  tools.append(button(t('ui.duplicar'), async () => {
    const as = prompt(t('ui.id_de_la_copia_de', { id: item.id }), t('ui.copia', { id: item.id })); if (!as) return;
    const r = await seriesLibraryCall('duplicate', { kind: item.kind, id: item.id, as: as.trim() });
    toast(t('ui.copia_creada', { id: r.id })); show('library');
  }, 'button tiny'), button(t('ui.quitar'), async () => {
    if (eps.length) throw new Error(t('ui.no_se_puede_quitar_lo', { id: item.id, eps: eps.map(([e]) => e).join(', ') }));
    if (!confirm(t('ui.confirm_remove_series_item', { kind: libName(item.kind), id: item.id, files: item.kind === 'props' ? t('ui.las_imagenes_se_conservan') : t('ui.su_json_pasa_a_papelera') }))) return;
    await seriesLibraryCall('remove', { kind: item.kind, id: item.id }, true);
    toast(t('ui.quitado_de_la_biblioteca', { id: item.id })); show('library');
  }, 'button tiny danger'));
  body.append(line, tools); card.append(body);
  return card;
}

/* Importar una escena (con sus planos) de otro capítulo de la serie, o duplicar una de éste con otro id. */
function importScenePanel() {
  const box = panel(t('ui.importar_una_escena_de_otro'), t('ui.copia_la_escena_y_sus')); box.body.className = 'pad stack';
  const cache = {};
  const ep = selectInput(S.series.episodes.map(e => [e.id, `${e.id} · ${e.title}${e.id === currentEpisode() ? t('ui.este') : ''}`]), S.series.episodes[0] && S.series.episodes[0].id, () => fill().catch(e => toast(e.message)));
  const scene = el('select'); const newId = el('input', 'mid'); newId.placeholder = t('ui.id_nuevo_opcional');
  async function fill() {
    scene.replaceChildren();
    if (!ep.value) return;
    const data = cache[ep.value] || (cache[ep.value] = await api(`/api/v2/films/${encodePath(episodePid(ep.value))}`));
    for (const sc of data.script.scenes || []) {
      const n = (data.script.shots || []).filter(x => x.scene === sc.id).length;
      const o = el('option', '', `${sc.id} · ${sc.title || sc.set} (${tp('ui.n_plano', n)})`); o.value = sc.id; scene.append(o);
    }
    if (!scene.options.length) scene.append(Object.assign(el('option', '', t('ui.este_capitulo_no_tiene_escenas')), { value: '' }));
  }
  const row = el('div', 'row');
  row.append(field(t('ui.capitulo_de_origen'), ep), field(t('ui.escena_2'), scene), field(t('ui.id_en_este_capitulo'), newId), button(t('ui.importar_escena'), async () => {
    if (!scene.value) throw new Error(t('ui.elige_una_escena'));
    const r = await api(v2('scenes/import'), { episode: ep.value, scene: scene.value, as: newId.value.trim() || undefined, script: S.script });
    ensureScenes().push(r.scene); S.script.shots.push(...r.shots);
    for (const [kind, items] of Object.entries(r.library)) Object.assign(S.script[kind] = S.script[kind] || {}, items);
    S.scene = S.script.scenes.length - 1; edited(false);
    toast(t('ui.scene_imported', { id: r.scene.id, shots: tp('ui.n_plano', r.shots.length) })); show('scenes');
  }, 'button orange'));
  box.body.append(row, el('p', 'hint', t('ui.se_copian_la_escena_y')));
  fill().catch(e => toast(e.message));
  return box.box;
}

/* ---------- arranque ---------- */
async function init() {
  applyStatic(); setStatus('html.loading');
  document.querySelectorAll('[data-lang]').forEach(b => b.addEventListener('click', () => setLang(b.dataset.lang)));
  document.querySelectorAll('#nav button').forEach(b => b.addEventListener('click', () => { if (S.script || ['episodes', 'library'].includes(b.dataset.view)) show(b.dataset.view); }));
  $('#save').addEventListener('click', () => attempt(save));
  $('#new-film').addEventListener('click', () => attempt(async () => {
    if (isDirty() && !confirm(t('ui.hay_cambios_sin_guardar_en_2'))) return;
    const title = prompt(t('ui.titulo_de_la_nueva_pelicula'), t('ui.nueva_pelicula'));
    if (!title) return;
    const made = await api('/api/v2/films', { title });
    S.films = await api('/api/v2/films'); S.series = null;
    S.view = 'characters';
    await loadFilm(made.id);
    toast(t('ui.pelicula_creada_empieza_importando_personajes', { id: made.id }));
  }));
  $('#new-series').addEventListener('click', () => attempt(async () => {
    if (isDirty() && !confirm(t('ui.hay_cambios_sin_guardar_en'))) return;
    const title = prompt(t('ui.titulo_de_la_nueva_serie'), t('ui.nueva_serie'));
    if (!title) return;
    const made = await api('/api/v2/series', { title });
    S.films = await api('/api/v2/films'); S.view = 'episodes';
    await openSeries(made.id);
    toast(t('ui.serie_creada_crea_su_primer', { id: made.id }));
  }));
  $('#episode-select').addEventListener('change', () => attempt(async () => {
    const next = $('#episode-select').value;
    if (next && !(await openEpisode(next))) fillEpisodeSelect();
  }));
  $('#cancel-job').addEventListener('click', () => attempt(async () => { if (S.job) { await api(`/api/jobs/${S.job}`, {}); $('#cancel-job').disabled = true; } }));
  $('#film-select').addEventListener('change', () => attempt(async () => {
    const next = $('#film-select').value;
    if (isDirty() && !confirm(t('ui.hay_cambios_sin_guardar_en_2'))) { fillFilmSelect(); return; }
    if (next.startsWith('s:')) { S.view = 'episodes'; await openSeries(next.slice(2)); } else { S.series = null; await loadFilm(next.slice(2)); }
  }));
  document.addEventListener('keydown', e => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); attempt(save); } });
  window.addEventListener('beforeunload', e => { if (isDirty()) { e.preventDefault(); e.returnValue = ''; } });
  S.films = await api('/api/v2/films');
  if (!S.films.length) { renderEmpty(); setStatus('html.none'); return; }
  const query = new URLSearchParams(location.search);
  const wantedSeries = query.get('series'), wanted = query.get('film');
  if (wantedSeries && S.films.some(f => f.id === wantedSeries && f.kind === 'series')) { if (query.get('view') === 'library') S.view = 'library'; await openSeries(wantedSeries, query.get('episode')); return; }
  const first = S.films.find(f => f.id === wanted) || S.films[0];
  if (first.kind === 'series') { S.view = 'episodes'; await openSeries(first.id); } else await loadFilm(first.id);
}
/* i18n:begin — catálogo de textos. «es» y «en» tienen exactamente las mismas claves (lo comprueba tests/test_i18n.py).
   Para añadir un idioma (p. ej. «fr»): añade «fr» a LANGS arriba, copia aquí un bloque «es» como «fr» traducido
   (los {marcadores} no se traducen), añade un botón data-lang="fr" en studio.html y sus textos en celstudio/v2/i18n.py. */
const CATALOG = {
"es": {
"ui.capitulos": "CAPÍTULOS",
"ui.biblioteca_de_la_serie": "BIBLIOTECA DE LA SERIE",
"ui.referencias": "REFERENCIAS",
"ui.guion": "GUION",
"ui.personajes": "PERSONAJES",
"ui.escenarios_y_utileria": "ESCENARIOS Y UTILERÍA",
"ui.escenas": "ESCENAS",
"ui.planos": "PLANOS",
"ui.render": "RENDER",
"ui.no_se_pudo_completar_la": "No se pudo completar la operación",
"ui.serie_sin_capitulos": "Serie sin capítulos",
"ui.revision": "REVISIÓN {sc}",
"ui.cambios_sin_guardar": "Cambios sin guardar",
"ui.guardado_en_tu_equipo": "Guardado en tu equipo",
"ui.el_guion_ya_esta_guardado": "El guion ya está guardado.",
"ui.guion_guardado": "Guion guardado.",
"ui.series": "Series",
"ui.peliculas": "Películas",
"ui.aviso": "Aviso: ",
"ui.no_se_pudo_leer_el": "No se pudo leer el archivo",
"ui.un_lugar_para_tu_universo": "Un lugar para tu universo.",
"ui.sube_imagenes_o_notas_de": "Sube imágenes o notas de texto de estilo, personajes, escenarios o guion. Las referencias se guardan en refs/ y se listan en el guion; el motor las ignora al renderizar.",
"ui.estilo": "Estilo",
"ui.personaje": "Personaje",
"ui.escenario": "Escenario",
"ui.guion_2": "Guion",
"ui.notas_que_debe_tomarse_de": "Notas: qué debe tomarse de esta referencia",
"ui.anadir_referencia": "Añadir referencia",
"ui.archivo_imagen_txt_o_md": "Archivo (imagen, .txt o .md, hasta 20 MB)",
"ui.tipo": "Tipo",
"ui.notas": "Notas",
"ui.subir_referencia": "Subir referencia",
"ui.elige_un_archivo_primero": "Elige un archivo primero.",
"ui.el_archivo_supera_los_20": "El archivo supera los 20 MB.",
"ui.referencia_subida": "Referencia subida.",
"ui.todavia_no_hay_referencias": "Todavía no hay referencias.",
"ui.quitar_de_la_lista": "Quitar de la lista",
"ui.quitar_esta_referencia_del_guion": "¿Quitar esta referencia del guion? El archivo se conserva en refs/.",
"ui.quitar": "Quitar",
"ui.sin_claves": "Sin claves.",
"ui.anadir_clave": "Añadir clave",
"ui.escribe_el_nombre_de_la": "Escribe el nombre de la clave.",
"ui.esa_clave_ya_existe": "Esa clave ya existe.",
"ui.el_guion_como_datos": "El guion como datos.",
"ui.el_texto_literario_guia_la": "El texto literario guía la dirección; la biblia y el estilo guardan continuidad y acabado. fps y tamaño de imagen son fijos desde la creación de la película.",
"ui.historia_y_titulo": "Historia y título",
"ui.titulo": "Título",
"ui.guion_literario_story": "Guion literario (story)",
"ui.tamano": "tamaño",
"ui.solo_lectura": " (sólo lectura)",
"ui.biblia": "Biblia",
"ui.estilo_historia_continuidad": "estilo · historia · continuidad",
"ui.notas_de_direccion_no_cambian": "Notas de dirección. No cambian el render; sirven de contexto para quien escribe o genera arte.",
"ui.nueva_clave": "nueva clave",
"ui.estilo_de_dibujo": "Estilo de dibujo",
"ui.se_aplica_a_toda_la": "se aplica a toda la película",
"ui.hold_dibujo_a_pasos_2": "hold: dibujo a pasos (2 = a doses). contour: grosor del contorno exterior. boil: temblor de línea. boil_hold: fotogramas entre cada temblor.",
"ui.utileria": "utilería",
"ui.escena": "Escena «{id}»",
"ui.escenario_de_la_escena": "escenario de la escena «{id}»",
"ui.escenario_del_plano": "escenario del plano «{id}»",
"ui.plano": "plano «{id}» ({id2})",
"ui.puff_burst_en_el_plano": "«puff_burst» en el plano «{id}»",
"ui.se_usa_en": "Se usa en: {uses}.",
"ui.sin_usar_se_puede_quitar": "Sin usar: se puede quitar de la biblioteca.",
"ui.duplicar": "Duplicar",
"ui.id_de_la_copia_de": "Id de la copia de «{id}»",
"ui.copia": "{id}-copia",
"ui.copia_creada": "Copia creada: «{id}».",
"ui.quitar_de_la_biblioteca": "Quitar de la biblioteca",
"ui.no_se_puede_quitar_quita": "No se puede quitar «{id}»: {uses}. Quita antes esos usos.",
"ui.las_imagenes_se_conservan": "Las imágenes se conservan.",
"ui.su_archivo_json_pasa_a": "Su archivo JSON pasa a papelera/ y las imágenes se conservan.",
"ui.quitar_de_la_biblioteca_2": "¿Quitar {kind} «{id}» de la biblioteca? {files}",
"ui.quitado_de_la_biblioteca": "«{id}» quitado de la biblioteca.",
"ui.se_copia_dentro_de_la": "se copia dentro de la serie",
"ui.se_copia_dentro_de_esta": "se copia dentro de esta película",
"ui.buscando_en_las_demas_peliculas": "Buscando en las demás películas…",
"ui.vista_previa": "Vista previa",
"ui.id_nuevo_opcional": "id nuevo (opcional)",
"ui.elemento": "Elemento",
"ui.id_en_esta_pelicula": "Id en esta película",
"ui.importar": "Importar",
"ui.importado_desde": "«{id}» importado desde «{film}».",
"ui.si_el_id_ya_existe": "Si el id ya existe se elige otro (id-2…). Se copian el JSON y todas las imágenes que referencia; la película de origen no cambia.",
"ui.los_actores_de_la_pelicula": "Los actores de la película.",
"ui.cada_ficha_edita_el_archivo": "Cada ficha edita el archivo del rig (characters/<id>.json). Guardar valida el rig dibujando una pose, guarda una copia .previous.json y recompila la película.",
"ui.un_personaje_nuevo_a_partir": "Un personaje nuevo a partir de arte no se crea aquí: necesita el flujo de arte (work/v3/prep_parts.py y build_rig.py); importa uno de otra película o duplica uno existente.",
"ui.importar_un_personaje_de_otra": "Importar un personaje de otra película",
"ui.esta_pelicula_no_tiene_personajes": "Esta película no tiene personajes todavía: importa uno de arriba.",
"ui.no_se_pudo_leer_el_2": "No se pudo leer el rig ({v}).",
"ui.frente": "Frente",
"ui.partes_imagenes_del_rig": "PARTES (IMÁGENES DEL RIG)",
"ui.colores": "COLORES",
"ui.proporciones": "PROPORCIONES",
"ui.avanzado_json_completo_del_rig": "Avanzado: JSON completo del rig",
"ui.guardar_personaje": "Guardar personaje",
"ui.el_json_avanzado_no_es": "El JSON avanzado no es válido.",
"ui.personaje_guardado_y_pelicula_recompilada": "Personaje «{cid}» guardado y película recompilada.",
"ui.descartar_cambios": "Descartar cambios",
"ui.donde_ocurre_la_historia": "Dónde ocurre la historia.",
"ui.cada_escenario_es_un_archivo": "Cada escenario es un archivo sets/<id>.json: capas con paralaje, luces, partículas, iluminación y posproceso. La utilería es la biblioteca props del guion y se guarda con el guion. Las escenas eligen de aquí.",
"ui.importar_un_escenario_de_otra": "Importar un escenario de otra película",
"ui.nuevo_escenario_vacio": "Nuevo escenario vacío",
"ui.color_liso_sin_capas": "color liso, sin capas",
"ui.id_letras_numeros": "id (letras, números, - _)",
"ui.color_de_fondo": "Color de fondo",
"ui.crear_escenario": "Crear escenario",
"ui.escenario_creado_anade_capas_desde": "Escenario «{id}» creado. Añade capas desde su ficha.",
"ui.un_escenario_nuevo_se_puede": "Un escenario nuevo se puede variar duplicando uno existente (otra luz, menos capas) o subiendo sus propias capas de imagen.",
"ui.no_se_pudo_leer_el_3": "No se pudo leer el escenario ({v}).",
"ui.vista_previa_de": "Vista previa de {sid}",
"ui.escenario_sin_actores_tal_como": "Escenario sin actores, tal como está guardado (no incluye cambios sin guardar).",
"ui.color_de_fondo_2": "color de fondo",
"ui.ground_y_suelo": "ground_y (suelo)",
"ui.otros": "otros",
"ui.sin_capas_el_escenario_es": "Sin capas: el escenario es un color liso. Sube una imagen para añadir la primera.",
"ui.capas_de_lejos_a_cerca": "CAPAS (DE LEJOS A CERCA: EL ORDEN DE LA LISTA ES EL DE DIBUJO)",
"ui.id_de_la_capa": "id de la capa",
"ui.imagen_de_la_capa": "Imagen de la capa",
"ui.subir_capa": "＋ Subir capa",
"ui.elige_una_imagen_primero": "Elige una imagen primero.",
"ui.capa_subida_ajusta_su_posicion": "Capa subida. Ajusta su posición y pulsa «Guardar escenario» para aplicarla.",
"ui.x_y_y_w_estan": "x, y y w están en unidades del mundo (1280×720). depth: .03 casi fija, 1 = plano de los actores, >1 primer plano.",
"ui.ausente": "(ausente)",
"ui.vacio_quitar_la_clave_un": "Vacío = quitar la clave. Un JSON inválido se marca en rojo y no se aplica.",
"ui.guardar_escenario": "Guardar escenario",
"ui.escenario_guardado_y_pelicula_recompilada": "Escenario «{sid}» guardado y película recompilada.",
"ui.biblioteca_de_utileria": "Biblioteca de utilería",
"ui.props_del_guion_se_guarda": "props del guion · se guarda con el guion",
"ui.cada_prop_es_la_especificacion": "Cada prop es la especificación de una hoja de sprites (sheet, cells, pivot, upp, layer, shadow). Los cambios se aplican al guion y se guardan con Guardar guion; duplicar copia la versión guardada.",
"ui.no_hay_utileria": "No hay utilería.",
"ui.importar_utileria_de_otra_pelicula": "Importar utilería de otra película",
"ui.id_de_la_utileria": "Id de la utilería",
"ui.hoja_de_sprites_imagen": "Hoja de sprites (imagen)",
"ui.crear_utileria": "Crear utilería",
"ui.escribe_el_id_de_la": "Escribe el id de la utilería.",
"ui.elige_la_imagen_de_la": "Elige la imagen de la hoja.",
"ui.utileria_creada_con_la_imagen": "Utilería «{id}» creada con la imagen completa como único fotograma; ajusta cells, pivot y upp en su JSON.",
"ui.nueva_utileria": "NUEVA UTILERÍA",
"ui.donde_y_con_quien_ocurre": "Dónde y con quién ocurre cada escena.",
"ui.una_escena_elige_un_escenario": "Una escena elige un escenario de la biblioteca, un reparto (personajes con su posición inicial) y la utilería disponible. Cada plano pertenece a una escena y usa sólo una parte de ese reparto. El orden de las escenas es organizativo: la película sigue el orden de los planos.",
"ui.importar_o_duplicar_una_escena": "Importar o duplicar una escena de otro capítulo",
"ui.escenas_2": "Escenas",
"ui.biblioteca_escena_plano": "BIBLIOTECA → ESCENA → PLANO",
"ui.nueva": "＋ Nueva",
"ui.eliminar": "Eliminar",
"ui.todavia_no_hay_escenas_crea": "Todavía no hay escenas. Crea la primera con «＋ Nueva».",
"ui.la_biblioteca_no_tiene_escenarios": "La biblioteca no tiene escenarios: crea o importa uno en «Escenarios y utilería».",
"ui.no_hay_ninguna_escena_que": "No hay ninguna escena que duplicar.",
"ui.no_hay_ninguna_escena_que_2": "No hay ninguna escena que eliminar.",
"ui.no_se_puede_eliminar_la": "No se puede eliminar la escena «{id}»: la usan los planos {users}. Muévelos a otra escena o elimínalos antes.",
"ui.eliminar_la_escena_no_se": "¿Eliminar la escena «{id}»? No se borra nada de la biblioteca.",
"ui.crea_una_escena_para_elegir": "Crea una escena para elegir su escenario, su reparto y su utilería.",
"ui.escena_2": "Escena",
"ui.id_titulo_escenario": "id · título · escenario",
"ui.ya_existe_la_escena": "Ya existe la escena «{next}».",
"ui.la_escena_necesita_un_id": "La escena necesita un id.",
"ui.vista_previa_del_escenario": "Vista previa del escenario",
"ui.id_de_la_escena": "Id de la escena",
"ui.ver_sus_planos": "Ver sus planos",
"ui.descripcion": "Descripción",
"ui.escenario_de_la_biblioteca": "Escenario (de la biblioteca)",
"ui.escenario_tal_como_esta_guardado": "Escenario tal como está guardado (los cambios del escenario se guardan en su ficha).",
"ui.planos_2": "Planos: {users}",
"ui.ningun_plano_usa_esta_escena": "Ningún plano usa esta escena todavía.",
"ui.id_no_valido_o_repetido": "Id no válido o repetido en la escena.",
"ui.quitar_de_la_escena": "¿Quitar «{id}» de la escena?",
"ui.reparto": "Reparto",
"ui.instancias_de_personajes_de_la": "instancias de personajes de la biblioteca · start = valores por defecto en la escena",
"ui.id_en_la_escena": "Id en la escena",
"ui.quitar_del_reparto": "Quitar del reparto",
"ui.el_reparto_esta_vacio_anade": "El reparto está vacío: añade los personajes que pueden aparecer en esta escena.",
"ui.anadir_al_reparto": "＋ Añadir al reparto",
"ui.la_biblioteca_no_tiene_personajes": "La biblioteca no tiene personajes: impórtalos en «Personajes».",
"ui.puedes_poner_varias_instancias_del": "Puedes poner varias instancias del mismo personaje con ids distintos. Cada plano elige quién aparece y puede cambiar estos valores.",
"ui.utileria_de_la_escena": "Utilería de la escena",
"ui.props_de_la_biblioteca_disponibles": "props de la biblioteca disponibles aquí · spec = ajustes sobre la biblioteca",
"ui.prop_de_la_biblioteca": "Prop de la biblioteca",
"ui.quitar_de_la_escena_2": "Quitar de la escena",
"ui.spec_se_mezcla_sobre_la": "spec (se mezcla sobre la biblioteca; el plano puede ajustarlo)",
"ui.sin_utileria_los_verbos_que": "Sin utilería. Los verbos que usan la biblioteca directamente (como puff_burst) funcionan sin listarla aquí.",
"ui.anadir_utileria": "＋ Añadir utilería",
"ui.la_biblioteca_de_utileria_esta": "La biblioteca de utilería está vacía: crea o importa una en «Escenarios y utilería».",
"ui.aun_no_hay_planos": "Aún no hay planos.",
"ui.anade_el_primero_para_empezar": "Añade el primero para empezar a dirigir.",
"ui.nuevo_plano": "＋ Nuevo plano",
"ui.planos_3": "Planos",
"ui.orden_de_la_pelicula": "ORDEN DE LA PELÍCULA",
"ui.nuevo": "＋ Nuevo",
"ui.plano_2": "Plano",
"ui.id_duracion_escena": "ID · duración · escena",
"ui.actores_y_utileria": "Actores y utilería",
"ui.valores_iniciales_start_y_piezas": "valores iniciales (start) y piezas del plano",
"ui.acciones": "Acciones",
"ui.una_lista_ordenada_el_orden": "una lista ordenada: el orden es el de la repetición",
"ui.todas_las_escenas": "Todas las escenas",
"ui.planos_sin_escena": "Planos sin escena",
"ui.sin_id": "(sin id)",
"ui.no_hay_planos_en_esta": "No hay planos en esta escena. «＋ Nuevo» crea el primero dentro de ella.",
"ui.crea_primero_una_escena_vista": "Crea primero una escena (vista Escenas): cada plano ocurre dentro de una escena.",
"ui.eliminar_el_plano_y_todas": "¿Eliminar el plano «{cur}» y todas sus acciones?",
"ui.vista_previa_del_plano": "Vista previa del plano",
"ui.reproducir_o_pausar": "Reproducir o pausar",
"ui.tiempo_del_plano": "Tiempo del plano",
"ui.ancho_de_la_vista_previa": "Ancho de la vista previa",
"ui.vista_previa_del_guion_con": "Vista previa del guion con cambios sin guardar. El render final usa el guion guardado.",
"ui.no_se_pudo_dibujar_el": "No se pudo dibujar el fotograma",
"ui.duracion_s": "Duración (s)",
"ui.escenario_de_la_escena_2": "Escenario de la escena: «{set}».",
"ui.actores": "ACTORES",
"ui.quitar_el_actor_sus_acciones": "¿Quitar el actor «{id}»? Sus acciones quedarán sin destino.",
"ui.actor": "＋ Actor",
"ui.el_guion_no_declara_personajes": "El guion no declara personajes.",
"ui.utileria_del_plano": "UTILERÍA DEL PLANO",
"ui.quitar_la_utileria": "¿Quitar la utilería «{id}»?",
"ui.spec_se_mezcla_sobre_la_2": "spec (se mezcla sobre la biblioteca)",
"ui.utileria_2": "＋ Utilería",
"ui.la_biblioteca_de_utileria_esta_2": "La biblioteca de utilería está vacía.",
"ui.por_defecto_en_la_escena": "Por defecto en la escena: {text}",
"ui.la_escena_no_fija_valores": "La escena no fija valores iniciales para este miembro.",
"ui.la_escena_no_existe_elige": "La escena «{scene}» no existe: elige otra en el campo Escena.",
"ui.reparto_de_la_escena_quien": "REPARTO DE LA ESCENA «{scene}»: QUIÉN APARECE EN ESTE PLANO",
"ui.la_escena_no_tiene_reparto": "La escena no tiene reparto. Añádelo en la vista Escenas.",
"ui.utileria_de_la_escena_en": "UTILERÍA DE LA ESCENA EN ESTE PLANO",
"ui.spec_de_este_plano_sobre": "spec de este plano (sobre la escena: {v})",
"ui.la_escena_no_tiene_utileria": "La escena no tiene utilería propia (los verbos de biblioteca como puff_burst no la necesitan).",
"ui.no_estan_en_la_escena": "NO ESTÁN EN LA ESCENA",
"ui.no_esta_en_la_escena": "{label} «{id}»: no está en la escena «{id2}». Añádelo a la escena o quítalo del plano.",
"ui.quitar_del_plano": "Quitar del plano",
"ui.ese_canal_ya_esta_en": "Ese canal ya está en start.",
"ui.canal": "＋ canal",
"ui.todos_los_destinos": "Todos los destinos",
"ui.filtrar_por_destino": "Filtrar por destino:",
"ui.anadir_accion": "＋ Añadir acción",
"ui.destino_on": "destino (on)",
"ui.verbo_do": "verbo (do)",
"ui.tiempo": "tiempo",
"ui.otros_argumentos": "otros argumentos",
"ui.editar": "Editar",
"ui.ir_al_momento": "Ir al momento",
"ui.no_hay_acciones_con_este": "No hay acciones con este filtro.",
"ui.por_defecto": "(por defecto: {default})",
"ui.3_8_4_05_lista": "[3.8, 4.05]  (lista JSON)",
"ui.numero_texto_o_json": "número, texto o JSON",
"ui.obligatorio": "obligatorio",
"ui.editar_la_accion": "Editar la acción {ed}",
"ui.nueva_accion_se_anade_al": "Nueva acción (se añade al final)",
"ui.destino_on_2": "Destino (on)",
"ui.verbo_do_2": "Verbo (do)",
"ui.el_verbo_no_existe_para": "El verbo «{verb}» no existe para este destino; sus argumentos se conservan como canales extra.",
"ui.canales_adicionales": "CANALES ADICIONALES",
"ui.anadir_canal": "＋ añadir canal",
"ui.se_conservan_sin_cambios": "Se conservan sin cambios: {v}",
"ui.aplicar": "Aplicar",
"ui.cancelar": "Cancelar",
"ui.debe_ser_una_lista_json": "«{name}» debe ser una lista JSON, por ejemplo [3.8, 4.05].",
"ui.el_canal_esta_repetido": "El canal «{k}» está repetido.",
"ui.del_guion_al_video": "Del guion al vídeo.",
"ui.el_render_es_determinista_y": "El render es determinista y sale del guion guardado. Cada render crea un archivo nuevo en renders/ (nunca se sobrescribe uno existente). Sin audio.",
"ui.nuevo_render": "Nuevo render",
"ui.pelicula_completa": "Película completa",
"ui.solo_el_plano": "Sólo el plano {id} ({seconds})",
"ui.480_px_borrador": "480 px (borrador)",
"ui.1920_px_completo": "1920 px (completo)",
"ui.iniciar_render": "Iniciar render",
"ui.ya_hay_un_render_en": "Ya hay un render en curso.",
"ui.renderizando_el_plano": "Renderizando el plano {value}",
"ui.renderizando_la_pelicula": "Renderizando la película",
"ui.que_renderizar": "Qué renderizar",
"ui.ancho": "Ancho",
"ui.si_hay_cambios_sin_guardar": "Si hay cambios sin guardar se guarda el guion antes de empezar. El progreso aparece arriba y puede cancelarse.",
"ui.renders_existentes": "Renders existentes",
"ui.archivo": "archivo",
"ui.fecha": "fecha",
"ui.ver": "Ver",
"ui.abrir": "Abrir",
"ui.todavia_no_hay_renders": "Todavía no hay renders.",
"ui.render_terminado": "Render terminado",
"ui.render_cancelado": "Render cancelado",
"ui.el_render_fallo": "El render falló",
"ui.hay_cambios_sin_guardar_en": "Hay cambios sin guardar en este capítulo. ¿Descartarlos?",
"ui.sin_capitulos": "(sin capítulos)",
"ui.una_serie_muchos_capitulos": "Una serie, muchos capítulos.",
"ui.la_biblioteca_personajes_escenarios_y": "La biblioteca (personajes, escenarios y utilería) es de la serie y se usa desde cualquier capítulo. El guion, las escenas y los planos son de cada capítulo.",
"ui.la_serie": "La serie",
"ui.revision_2": "revisión {s}",
"ui.titulo_de_la_serie": "Título de la serie",
"ui.notas_estilo_mundo_continuidad": "Notas (estilo, mundo, continuidad)",
"ui.biblia_json_estilo_mundo_continuidad": "Biblia (JSON: estilo, mundo, continuidad…)",
"ui.guardar_datos_de_la_serie": "Guardar datos de la serie",
"ui.datos_de_la_serie_guardados": "Datos de la serie guardados.",
"ui.capitulos_2": "Capítulos",
"ui.titulo_2": "título",
"ui.duracion": "duración",
"ui.no_se_puede_leer": " (no se puede leer)",
"ui.abierto": "Abierto",
"ui.id_del_capitulo_copia_de": "Id del capítulo copia de «{id}»",
"ui.capitulo_creado": "Capítulo «{id}» creado.",
"ui.renombrar": "Renombrar",
"ui.titulo_del_capitulo": "Título del capítulo «{id}»",
"ui.borrar": "Borrar",
"ui.para_confirmar_escribe_el_id": "Para confirmar, escribe el id del capítulo: {id}",
"ui.el_id_no_coincide_no": "El id no coincide: no se borró nada.",
"ui.capitulo_enviado_a_papelera": "Capítulo «{id}» enviado a papelera/.",
"ui.todavia_no_hay_capitulos_crea": "Todavía no hay capítulos: crea el primero.",
"ui.titulo_del_nuevo_capitulo": "Título del nuevo capítulo",
"ui.nuevo_capitulo": "＋ Nuevo capítulo",
"ui.avisos_de_este_capitulo": "Avisos de este capítulo: ",
"ui.la_biblioteca_de_la_serie": "La biblioteca de la serie.",
"ui.todo_lo_que_hay_aqui": "Todo lo que hay aquí se puede usar desde cualquier capítulo. Busca por id o nombre, filtra por tipo o por uso, y mira en qué capítulos se usa cada elemento. Quitar un elemento se rechaza mientras algún capítulo lo use.",
"ui.buscar_por_id_o_nombre": "Buscar por id o nombre…",
"ui.todo": "Todo",
"ui.personajes_2": "Personajes",
"ui.escenarios": "Escenarios",
"ui.utileria_3": "Utilería",
"ui.usados_y_sin_usar": "Usados y sin usar",
"ui.solo_usados": "Sólo usados",
"ui.sin_usar": "Sin usar",
"ui.cualquier_capitulo": "Cualquier capítulo",
"ui.uso": "Uso",
"ui.capitulo": "Capítulo",
"ui.importar_de_otro_proyecto_otra": "Importar de otro proyecto (otra serie o película)",
"ui.importar_un_personaje": "Importar un personaje",
"ui.importar_un_escenario": "Importar un escenario",
"ui.importar_utileria": "Importar utilería",
"ui.de_elementos_personajes_escenarios_utilerias": "{total} de {r} elementos · {characters} personajes · {sets} escenarios · {props} utilerías",
"ui.nada_coincide_con_el_filtro": "Nada coincide con el filtro.",
"ui.mostrar_mas": "Mostrar más ({r})",
"ui.sin_usar_se_puede_quitar_2": "Sin usar: se puede quitar.",
"ui.usado_en": "Usado en: ",
"ui.abrir_el_capitulo": "Abrir el capítulo «{e}»",
"ui.no_se_puede_quitar_lo": "No se puede quitar «{id}»: lo usan los capítulos {eps}. Quita antes esos usos.",
"ui.importar_una_escena_de_otro": "Importar una escena de otro capítulo",
"ui.copia_la_escena_y_sus": "copia la escena y sus planos",
"ui.este_capitulo_no_tiene_escenas": "(este capítulo no tiene escenas)",
"ui.capitulo_de_origen": "Capítulo de origen",
"ui.id_en_este_capitulo": "Id en este capítulo",
"ui.importar_escena": "Importar escena",
"ui.elige_una_escena": "Elige una escena.",
"ui.se_copian_la_escena_y": "Se copian la escena y sus planos; los ids que ya existan en este capítulo reciben un sufijo (id-2). Los personajes, escenarios y utilería son de la biblioteca de la serie y ya están disponibles. Con el propio capítulo como origen sirve para duplicar una escena con sus planos.",
"ui.hay_cambios_sin_guardar_en_2": "Hay cambios sin guardar en esta película. ¿Descartarlos?",
"ui.titulo_de_la_nueva_pelicula": "Título de la nueva película",
"ui.nueva_pelicula": "Nueva película",
"ui.pelicula_creada_empieza_importando_personajes": "Película «{id}» creada. Empieza importando personajes y escenarios, luego crea una escena.",
"ui.titulo_de_la_nueva_serie": "Título de la nueva serie",
"ui.nueva_serie": "Nueva serie",
"ui.serie_creada_crea_su_primer": "Serie «{id}» creada. Crea su primer capítulo e importa personajes y escenarios a la biblioteca.",
"ui.no_hay_proyectos_v2": "No hay proyectos v2.",
"ui.crea_el_primero_con_nueva": "Crea el primero con «＋ Nueva película» o «＋ Nueva serie» (barra lateral).",
"ui.error_al_cargar": "Error al cargar",
"ui.use_cast_scene": "reparto de la escena «{id}» ({member})",
"ui.use_props_scene": "utilería de la escena «{id}» ({member})",
"ui.no_importable_characters": "Ninguna otra película tiene personajes para importar.",
"ui.no_importable_sets": "Ninguna otra película tiene escenarios para importar.",
"ui.no_importable_props": "Ninguna otra película tiene utilería para importar.",
"ui.n_capitulo": "{n} capítulo|{n} capítulos",
"ui.n_plano": "{n} plano|{n} planos",
"ui.n_accion": "{n} acción|{n} acciones",
"ui.n_problema": "{n} problema|{n} problemas",
"ui.n_personaje": "{n} personaje|{n} personajes",
"ui.n_escenario": "{n} escenario|{n} escenarios",
"ui.n_utileria": "{n} utilería|{n} utilerías",
"ui.n_problema_scene": "{n} problema en esta escena:|{n} problemas en esta escena:",
"ui.n_problema_script": "{n} problema en el guion|{n} problemas en el guion",
"ui.member_in_shots": "«{id}» aparece en {shots} ({list}) con {actions}. Se quitará de ellos y se borrarán esas acciones. ¿Continuar?",
"ui.member_has_actions": "«{id}» tiene {actions} en este plano. Si lo quitas se borrarán. ¿Continuar?",
"ui.lost_from_scene": "No están en la escena «{scene}»: {list}. Se quitarán del plano junto con {actions}. ¿Continuar?",
"ui.library_counts": "Biblioteca: {characters} · {sets} · {props}. Se guarda en series.json.",
"ui.confirm_remove_series_item": "¿Quitar {kind} «{id}» de la biblioteca de la serie? {files}",
"ui.su_json_pasa_a_papelera": "Su JSON pasa a papelera/ y las imágenes se conservan.",
"ui.scene_imported": "Escena «{id}» importada con {shots}. Guarda el capítulo para fijarla.",
"ui.este": " (este)",
"ui.word_actor": "actor",
"ui.default_scene_id": "escena",
"ui.default_shot_id": "plano",
"ui.default_layer_id": "capa",
"ui.lib_personaje": "personaje",
"ui.lib_escenario": "escenario",
"html.title": "Cel Studio · Estudio v2",
"html.brand_aria": "Cel Studio, inicio",
"html.your_project": "TU PROYECTO",
"html.current_project": "Proyecto actual",
"html.new_film": "＋ Nueva película",
"html.new_series": "＋ Nueva serie",
"html.episode": "CAPÍTULO",
"html.nav_aria": "Etapas de producción",
"html.nav_episodes": "Capítulos",
"html.nav_library": "Biblioteca de la serie",
"html.nav_references": "Referencias",
"html.nav_script": "Guion",
"html.nav_characters": "Personajes",
"html.nav_sets": "Escenarios y utilería",
"html.nav_scenes": "Escenas",
"html.nav_shots": "Planos",
"html.nav_render": "Render",
"html.pipeline": "Motor v2 · animación en CPU",
"html.note_script": "El guion es datos: ",
"html.note_render": "El render es determinista.",
"html.audio_note": "DOBLAJE · ETAPA POSTERIOR",
"html.breadcrumb": "TALLER LOCAL",
"html.loading": "Cargando…",
"html.none": "—",
"html.save": "Guardar guion",
"html.eyebrow": "MOTOR V2",
"html.subtitle": "Referencias, guion, personajes, escenarios, planos y render en un solo lugar.",
"html.stat_duration": "DURACIÓN",
"html.stat_shots": "PLANOS",
"html.stat_fps": "FPS",
"html.job_title": "Renderizando",
"html.cancel": "Cancelar",
"html.open_video": "Abrir video ↗",
"html.footer_engine": "CEL STUDIO / MOTOR V2",
"html.footer_save": "Ctrl+S guarda el guion",
"html.footer_local": "LOCAL · VIDEO SILENCIOSO",
"html.language": "Idioma",
"verb.actor.drift": "Mantiene viva una pose sostenida: cada canal oscila alrededor de su valor actual en ±amp (fase propia), con entrada y salida suaves para volver exactamente al valor sostenido. Escríbelo justo después del movimiento que creó la pausa.",
"verb.actor.gasp": "Inhalación brusca: se hunde, salta y vuelve, y se asienta.",
"verb.actor.hop": "Anticipa, salta, aterriza con aplastamiento y se asienta. Devuelve el instante del aterrizaje.",
"verb.actor.laugh": "Rebote de hombros y torso al reír.",
"verb.actor.overshoot": "Llega a los valores numéricos del canal pasándose del objetivo por `over` (fracción del movimiento) y luego se asienta en ellos.",
"verb.actor.pulse": "Va a unos valores y vuelve a lo que había antes.",
"verb.actor.react": "Gesto de oyente: los ojos van primero (t), la cabeza sigue (+.05), el cuerpo se inclina al final (+.14) y vuelve.",
"verb.actor.to": "Mantiene el valor actual hasta t (+ retardo de la familia) y llega al objetivo tras `dur`.\nUna mano que cambia de dirección viaja en arco alrededor del hombro, nunca en línea recta a través del cuerpo.",
"verb.actor.track": "Los ojos (y un poco la cabeza) siguen a un prop volador (id del plano).",
"verb.actor.turn_around": "Gira pasando por una vista frontal real: yaw hacia la cámara, se abre al dibujo frontal, se refleja allí (la pose frontal es simétrica, así que nada cambia de lado en pantalla) y se cierra en la nueva vista de tres cuartos.",
"verb.actor.walk": "Caminata con el pie plantado a lo largo de x. La fase va ligada a la distancia para que los pies de apoyo no resbalen.\nCada paso aterriza con el talón, rueda hasta quedar plano, despega por los dedos y pasa con la rodilla doblada.\n`view`: '3q' (por defecto) camina en tres cuartos; 'profile' gira el cuerpo de lado (turn 2, necesita el arte de perfil del personaje) con una transición suave corta en ambos extremos y vuelve a tres cuartos al final.",
"verb.actor.wave": "Levanta el brazo con anticipación, saluda desde la muñeca y el antebrazo y lo baja. Devuelve el instante final.",
"verb.actor.wave_off": "Saludo de despedida: anticipación hacia atrás, subida con rebasamiento y asentamiento, ciclos que se apagan, una pausa en que la mano cae despacio y una caída limpia que rebasa la pose de reposo. Devuelve el instante final.",
"verb.prop.flap": "Ciclo de aleteo en flipbook.",
"verb.prop.path": "Vuela por puntos del mundo con una trayectoria Catmull-Rom y un cabeceo revoloteante; claves lineales densas.",
"verb.prop.perch": "Respiración lenta de alas en reposo.",
"verb.shot.dof": "Profundidad de campo: un número o claves [[t, valor, ease?], ...].",
"verb.shot.puff_burst": "Nubes de polvo (prop 'puff' de la biblioteca) lanzadas hacia los lados desde un punto."
},
"en": {
"ui.capitulos": "EPISODES",
"ui.biblioteca_de_la_serie": "SERIES LIBRARY",
"ui.referencias": "REFERENCES",
"ui.guion": "SCRIPT",
"ui.personajes": "CHARACTERS",
"ui.escenarios_y_utileria": "SETS AND PROPS",
"ui.escenas": "SCENES",
"ui.planos": "SHOTS",
"ui.render": "RENDER",
"ui.no_se_pudo_completar_la": "The operation could not be completed",
"ui.serie_sin_capitulos": "Series without episodes",
"ui.revision": "REVISION {sc}",
"ui.cambios_sin_guardar": "Unsaved changes",
"ui.guardado_en_tu_equipo": "Saved on your computer",
"ui.el_guion_ya_esta_guardado": "The script is already saved.",
"ui.guion_guardado": "Script saved.",
"ui.series": "Series",
"ui.peliculas": "Films",
"ui.aviso": "Notice: ",
"ui.no_se_pudo_leer_el": "The file could not be read",
"ui.un_lugar_para_tu_universo": "A place for your universe.",
"ui.sube_imagenes_o_notas_de": "Upload images or text notes about style, characters, sets or script. References are stored in refs/ and listed in the script; the engine ignores them when rendering.",
"ui.estilo": "Style",
"ui.personaje": "Character",
"ui.escenario": "Set",
"ui.guion_2": "Script",
"ui.notas_que_debe_tomarse_de": "Notes: what should be taken from this reference",
"ui.anadir_referencia": "Add reference",
"ui.archivo_imagen_txt_o_md": "File (image, .txt or .md, up to 20 MB)",
"ui.tipo": "Type",
"ui.notas": "Notes",
"ui.subir_referencia": "Upload reference",
"ui.elige_un_archivo_primero": "Choose a file first.",
"ui.el_archivo_supera_los_20": "The file exceeds 20 MB.",
"ui.referencia_subida": "Reference uploaded.",
"ui.todavia_no_hay_referencias": "There are no references yet.",
"ui.quitar_de_la_lista": "Remove from list",
"ui.quitar_esta_referencia_del_guion": "Remove this reference from the script? The file is kept in refs/.",
"ui.quitar": "Remove",
"ui.sin_claves": "No keys.",
"ui.anadir_clave": "Add key",
"ui.escribe_el_nombre_de_la": "Type the key name.",
"ui.esa_clave_ya_existe": "That key already exists.",
"ui.el_guion_como_datos": "The script as data.",
"ui.el_texto_literario_guia_la": "The literary text guides the direction; the bible and the style keep continuity and finish. fps and image size are fixed from the moment the film is created.",
"ui.historia_y_titulo": "Story and title",
"ui.titulo": "Title",
"ui.guion_literario_story": "Literary script (story)",
"ui.tamano": "size",
"ui.solo_lectura": " (read only)",
"ui.biblia": "Bible",
"ui.estilo_historia_continuidad": "style · story · continuity",
"ui.notas_de_direccion_no_cambian": "Direction notes. They do not change the render; they give context to whoever writes or generates art.",
"ui.nueva_clave": "new key",
"ui.estilo_de_dibujo": "Drawing style",
"ui.se_aplica_a_toda_la": "applies to the whole film",
"ui.hold_dibujo_a_pasos_2": "hold: stepped drawing (2 = on twos). contour: thickness of the outer outline. boil: line jitter. boil_hold: frames between each jitter.",
"ui.utileria": "prop",
"ui.escena": "Scene «{id}»",
"ui.escenario_de_la_escena": "set of scene «{id}»",
"ui.escenario_del_plano": "set of shot «{id}»",
"ui.plano": "shot «{id}» ({id2})",
"ui.puff_burst_en_el_plano": "«puff_burst» in shot «{id}»",
"ui.se_usa_en": "Used in: {uses}.",
"ui.sin_usar_se_puede_quitar": "Unused: it can be removed from the library.",
"ui.duplicar": "Duplicate",
"ui.id_de_la_copia_de": "Id of the copy of «{id}»",
"ui.copia": "{id}-copy",
"ui.copia_creada": "Copy created: «{id}».",
"ui.quitar_de_la_biblioteca": "Remove from library",
"ui.no_se_puede_quitar_quita": "«{id}» cannot be removed: {uses}. Remove those uses first.",
"ui.las_imagenes_se_conservan": "The images are kept.",
"ui.su_archivo_json_pasa_a": "Its JSON file moves to papelera/ and the images are kept.",
"ui.quitar_de_la_biblioteca_2": "Remove {kind} «{id}» from the library? {files}",
"ui.quitado_de_la_biblioteca": "«{id}» removed from the library.",
"ui.se_copia_dentro_de_la": "copied into the series",
"ui.se_copia_dentro_de_esta": "copied into this film",
"ui.buscando_en_las_demas_peliculas": "Looking in the other films…",
"ui.vista_previa": "Preview",
"ui.id_nuevo_opcional": "new id (optional)",
"ui.elemento": "Item",
"ui.id_en_esta_pelicula": "Id in this film",
"ui.importar": "Import",
"ui.importado_desde": "«{id}» imported from «{film}».",
"ui.si_el_id_ya_existe": "If the id already exists another one is chosen (id-2…). The JSON and every image it references are copied; the source film does not change.",
"ui.los_actores_de_la_pelicula": "The film's actors.",
"ui.cada_ficha_edita_el_archivo": "Each card edits the rig file (characters/<id>.json). Saving validates the rig by drawing a pose, keeps a .previous.json copy and recompiles the film.",
"ui.un_personaje_nuevo_a_partir": "A new character made from art is not created here: it needs the art workflow (work/v3/prep_parts.py and build_rig.py); import one from another film or duplicate an existing one.",
"ui.importar_un_personaje_de_otra": "Import a character from another film",
"ui.esta_pelicula_no_tiene_personajes": "This film has no characters yet: import one above.",
"ui.no_se_pudo_leer_el_2": "The rig could not be read ({v}).",
"ui.frente": "Front",
"ui.partes_imagenes_del_rig": "PARTS (RIG IMAGES)",
"ui.colores": "COLORS",
"ui.proporciones": "PROPORTIONS",
"ui.avanzado_json_completo_del_rig": "Advanced: full rig JSON",
"ui.guardar_personaje": "Save character",
"ui.el_json_avanzado_no_es": "The advanced JSON is not valid.",
"ui.personaje_guardado_y_pelicula_recompilada": "Character «{cid}» saved and film recompiled.",
"ui.descartar_cambios": "Discard changes",
"ui.donde_ocurre_la_historia": "Where the story happens.",
"ui.cada_escenario_es_un_archivo": "Each set is a sets/<id>.json file: parallax layers, lights, particles, lighting and post-processing. Props are the script's props library and are saved with the script. Scenes pick from here.",
"ui.importar_un_escenario_de_otra": "Import a set from another film",
"ui.nuevo_escenario_vacio": "New empty set",
"ui.color_liso_sin_capas": "flat color, no layers",
"ui.id_letras_numeros": "id (letters, numbers, - _)",
"ui.color_de_fondo": "Background color",
"ui.crear_escenario": "Create set",
"ui.escenario_creado_anade_capas_desde": "Set «{id}» created. Add layers from its card.",
"ui.un_escenario_nuevo_se_puede": "A new set can be varied by duplicating an existing one (other light, fewer layers) or by uploading your own image layers.",
"ui.no_se_pudo_leer_el_3": "The set could not be read ({v}).",
"ui.vista_previa_de": "Preview of {sid}",
"ui.escenario_sin_actores_tal_como": "Set without actors, as saved (does not include unsaved changes).",
"ui.color_de_fondo_2": "background color",
"ui.ground_y_suelo": "ground_y (floor)",
"ui.otros": "others",
"ui.sin_capas_el_escenario_es": "No layers: the set is a flat color. Upload an image to add the first one.",
"ui.capas_de_lejos_a_cerca": "LAYERS (FAR TO NEAR: LIST ORDER IS DRAWING ORDER)",
"ui.id_de_la_capa": "layer id",
"ui.imagen_de_la_capa": "Layer image",
"ui.subir_capa": "＋ Upload layer",
"ui.elige_una_imagen_primero": "Choose an image first.",
"ui.capa_subida_ajusta_su_posicion": "Layer uploaded. Adjust its position and press «Save set» to apply it.",
"ui.x_y_y_w_estan": "x, y and w are in world units (1280×720). depth: .03 almost fixed, 1 = the actors' plane, >1 foreground.",
"ui.ausente": "(absent)",
"ui.vacio_quitar_la_clave_un": "Empty = remove the key. Invalid JSON is marked in red and not applied.",
"ui.guardar_escenario": "Save set",
"ui.escenario_guardado_y_pelicula_recompilada": "Set «{sid}» saved and film recompiled.",
"ui.biblioteca_de_utileria": "Props library",
"ui.props_del_guion_se_guarda": "script props · saved with the script",
"ui.cada_prop_es_la_especificacion": "Each prop is the specification of a sprite sheet (sheet, cells, pivot, upp, layer, shadow). Changes apply to the script and are saved with Save script; duplicate copies the saved version.",
"ui.no_hay_utileria": "There are no props.",
"ui.importar_utileria_de_otra_pelicula": "Import props from another film",
"ui.id_de_la_utileria": "Prop id",
"ui.hoja_de_sprites_imagen": "Sprite sheet (image)",
"ui.crear_utileria": "Create prop",
"ui.escribe_el_id_de_la": "Type the prop id.",
"ui.elige_la_imagen_de_la": "Choose the sheet image.",
"ui.utileria_creada_con_la_imagen": "Prop «{id}» created with the whole image as its only frame; adjust cells, pivot and upp in its JSON.",
"ui.nueva_utileria": "NEW PROP",
"ui.donde_y_con_quien_ocurre": "Where and with whom each scene happens.",
"ui.una_escena_elige_un_escenario": "A scene picks a set from the library, a cast (characters with their starting position) and the available props. Each shot belongs to a scene and uses only part of that cast. Scene order is organizational: the film follows the order of the shots.",
"ui.importar_o_duplicar_una_escena": "Import or duplicate a scene from another episode",
"ui.escenas_2": "Scenes",
"ui.biblioteca_escena_plano": "LIBRARY → SCENE → SHOT",
"ui.nueva": "＋ New",
"ui.eliminar": "Delete",
"ui.todavia_no_hay_escenas_crea": "There are no scenes yet. Create the first with «＋ New».",
"ui.la_biblioteca_no_tiene_escenarios": "The library has no sets: create or import one in «Sets and props».",
"ui.no_hay_ninguna_escena_que": "There is no scene to duplicate.",
"ui.no_hay_ninguna_escena_que_2": "There is no scene to delete.",
"ui.no_se_puede_eliminar_la": "Scene «{id}» cannot be deleted: it is used by shots {users}. Move them to another scene or delete them first.",
"ui.eliminar_la_escena_no_se": "Delete scene «{id}»? Nothing is deleted from the library.",
"ui.crea_una_escena_para_elegir": "Create a scene to choose its set, its cast and its props.",
"ui.escena_2": "Scene",
"ui.id_titulo_escenario": "id · title · set",
"ui.ya_existe_la_escena": "Scene «{next}» already exists.",
"ui.la_escena_necesita_un_id": "The scene needs an id.",
"ui.vista_previa_del_escenario": "Set preview",
"ui.id_de_la_escena": "Scene id",
"ui.ver_sus_planos": "See its shots",
"ui.descripcion": "Description",
"ui.escenario_de_la_biblioteca": "Set (from the library)",
"ui.escenario_tal_como_esta_guardado": "Set as saved (set changes are saved on its card).",
"ui.planos_2": "Shots: {users}",
"ui.ningun_plano_usa_esta_escena": "No shot uses this scene yet.",
"ui.id_no_valido_o_repetido": "Invalid or duplicate id in the scene.",
"ui.quitar_de_la_escena": "Remove «{id}» from the scene?",
"ui.reparto": "Cast",
"ui.instancias_de_personajes_de_la": "instances of library characters · start = default values in the scene",
"ui.id_en_la_escena": "Id in the scene",
"ui.quitar_del_reparto": "Remove from cast",
"ui.el_reparto_esta_vacio_anade": "The cast is empty: add the characters that can appear in this scene.",
"ui.anadir_al_reparto": "＋ Add to cast",
"ui.la_biblioteca_no_tiene_personajes": "The library has no characters: import them in «Characters».",
"ui.puedes_poner_varias_instancias_del": "You can add several instances of the same character with different ids. Each shot chooses who appears and can change these values.",
"ui.utileria_de_la_escena": "Scene props",
"ui.props_de_la_biblioteca_disponibles": "library props available here · spec = adjustments over the library",
"ui.prop_de_la_biblioteca": "Library prop",
"ui.quitar_de_la_escena_2": "Remove from scene",
"ui.spec_se_mezcla_sobre_la": "spec (merged over the library; the shot may adjust it)",
"ui.sin_utileria_los_verbos_que": "No props. Verbs that use the library directly (such as puff_burst) work without listing it here.",
"ui.anadir_utileria": "＋ Add prop",
"ui.la_biblioteca_de_utileria_esta": "The props library is empty: create or import one in «Sets and props».",
"ui.aun_no_hay_planos": "There are no shots yet.",
"ui.anade_el_primero_para_empezar": "Add the first one to start directing.",
"ui.nuevo_plano": "＋ New shot",
"ui.planos_3": "Shots",
"ui.orden_de_la_pelicula": "FILM ORDER",
"ui.nuevo": "＋ New",
"ui.plano_2": "Shot",
"ui.id_duracion_escena": "ID · duration · scene",
"ui.actores_y_utileria": "Actors and props",
"ui.valores_iniciales_start_y_piezas": "initial values (start) and parts of the shot",
"ui.acciones": "Actions",
"ui.una_lista_ordenada_el_orden": "an ordered list: the order is the playback order",
"ui.todas_las_escenas": "All scenes",
"ui.planos_sin_escena": "Shots without scene",
"ui.sin_id": "(no id)",
"ui.no_hay_planos_en_esta": "There are no shots in this scene. «＋ New» creates the first one inside it.",
"ui.crea_primero_una_escena_vista": "Create a scene first (Scenes view): every shot happens inside a scene.",
"ui.eliminar_el_plano_y_todas": "Delete shot «{cur}» and all its actions?",
"ui.vista_previa_del_plano": "Shot preview",
"ui.reproducir_o_pausar": "Play or pause",
"ui.tiempo_del_plano": "Shot time",
"ui.ancho_de_la_vista_previa": "Preview width",
"ui.vista_previa_del_guion_con": "Preview of the script with unsaved changes. The final render uses the saved script.",
"ui.no_se_pudo_dibujar_el": "The frame could not be drawn",
"ui.duracion_s": "Duration (s)",
"ui.escenario_de_la_escena_2": "Scene's set: «{set}».",
"ui.actores": "ACTORS",
"ui.quitar_el_actor_sus_acciones": "Remove actor «{id}»? Its actions will be left without a target.",
"ui.actor": "＋ Actor",
"ui.el_guion_no_declara_personajes": "The script declares no characters.",
"ui.utileria_del_plano": "SHOT PROPS",
"ui.quitar_la_utileria": "Remove prop «{id}»?",
"ui.spec_se_mezcla_sobre_la_2": "spec (merged over the library)",
"ui.utileria_2": "＋ Prop",
"ui.la_biblioteca_de_utileria_esta_2": "The props library is empty.",
"ui.por_defecto_en_la_escena": "Default in the scene: {text}",
"ui.la_escena_no_fija_valores": "The scene sets no initial values for this member.",
"ui.la_escena_no_existe_elige": "Scene «{scene}» does not exist: choose another in the Scene field.",
"ui.reparto_de_la_escena_quien": "CAST OF SCENE «{scene}»: WHO APPEARS IN THIS SHOT",
"ui.la_escena_no_tiene_reparto": "The scene has no cast. Add it in the Scenes view.",
"ui.utileria_de_la_escena_en": "SCENE PROPS IN THIS SHOT",
"ui.spec_de_este_plano_sobre": "spec of this shot (over the scene's: {v})",
"ui.la_escena_no_tiene_utileria": "The scene has no props of its own (library verbs such as puff_burst do not need them).",
"ui.no_estan_en_la_escena": "NOT IN THE SCENE",
"ui.no_esta_en_la_escena": "{label} «{id}»: not in scene «{id2}». Add it to the scene or remove it from the shot.",
"ui.quitar_del_plano": "Remove from shot",
"ui.ese_canal_ya_esta_en": "That channel is already in start.",
"ui.canal": "＋ channel",
"ui.todos_los_destinos": "All targets",
"ui.filtrar_por_destino": "Filter by target:",
"ui.anadir_accion": "＋ Add action",
"ui.destino_on": "target (on)",
"ui.verbo_do": "verb (do)",
"ui.tiempo": "time",
"ui.otros_argumentos": "other arguments",
"ui.editar": "Edit",
"ui.ir_al_momento": "Go to time",
"ui.no_hay_acciones_con_este": "There are no actions with this filter.",
"ui.por_defecto": "(default: {default})",
"ui.3_8_4_05_lista": "[3.8, 4.05]  (JSON list)",
"ui.numero_texto_o_json": "number, text or JSON",
"ui.obligatorio": "required",
"ui.editar_la_accion": "Edit action {ed}",
"ui.nueva_accion_se_anade_al": "New action (added at the end)",
"ui.destino_on_2": "Target (on)",
"ui.verbo_do_2": "Verb (do)",
"ui.el_verbo_no_existe_para": "Verb «{verb}» does not exist for this target; its arguments are kept as extra channels.",
"ui.canales_adicionales": "EXTRA CHANNELS",
"ui.anadir_canal": "＋ add channel",
"ui.se_conservan_sin_cambios": "Kept unchanged: {v}",
"ui.aplicar": "Apply",
"ui.cancelar": "Cancel",
"ui.debe_ser_una_lista_json": "«{name}» must be a JSON list, for example [3.8, 4.05].",
"ui.el_canal_esta_repetido": "Channel «{k}» is repeated.",
"ui.del_guion_al_video": "From script to video.",
"ui.el_render_es_determinista_y": "The render is deterministic and comes from the saved script. Each render creates a new file in renders/ (an existing one is never overwritten). No audio.",
"ui.nuevo_render": "New render",
"ui.pelicula_completa": "Whole film",
"ui.solo_el_plano": "Only shot {id} ({seconds})",
"ui.480_px_borrador": "480 px (draft)",
"ui.1920_px_completo": "1920 px (full)",
"ui.iniciar_render": "Start render",
"ui.ya_hay_un_render_en": "A render is already in progress.",
"ui.renderizando_el_plano": "Rendering shot {value}",
"ui.renderizando_la_pelicula": "Rendering the film",
"ui.que_renderizar": "What to render",
"ui.ancho": "Width",
"ui.si_hay_cambios_sin_guardar": "If there are unsaved changes the script is saved before starting. Progress appears above and can be cancelled.",
"ui.renders_existentes": "Existing renders",
"ui.archivo": "file",
"ui.fecha": "date",
"ui.ver": "View",
"ui.abrir": "Open",
"ui.todavia_no_hay_renders": "There are no renders yet.",
"ui.render_terminado": "Render finished",
"ui.render_cancelado": "Render cancelled",
"ui.el_render_fallo": "The render failed",
"ui.hay_cambios_sin_guardar_en": "There are unsaved changes in this episode. Discard them?",
"ui.sin_capitulos": "(no episodes)",
"ui.una_serie_muchos_capitulos": "One series, many episodes.",
"ui.la_biblioteca_personajes_escenarios_y": "The library (characters, sets and props) belongs to the series and is used from any episode. The script, scenes and shots belong to each episode.",
"ui.la_serie": "The series",
"ui.revision_2": "revision {s}",
"ui.titulo_de_la_serie": "Series title",
"ui.notas_estilo_mundo_continuidad": "Notes (style, world, continuity)",
"ui.biblia_json_estilo_mundo_continuidad": "Bible (JSON: style, world, continuity…)",
"ui.guardar_datos_de_la_serie": "Save series data",
"ui.datos_de_la_serie_guardados": "Series data saved.",
"ui.capitulos_2": "Episodes",
"ui.titulo_2": "title",
"ui.duracion": "duration",
"ui.no_se_puede_leer": " (cannot be read)",
"ui.abierto": "Open now",
"ui.id_del_capitulo_copia_de": "Id of the episode copy of «{id}»",
"ui.capitulo_creado": "Episode «{id}» created.",
"ui.renombrar": "Rename",
"ui.titulo_del_capitulo": "Title of episode «{id}»",
"ui.borrar": "Delete",
"ui.para_confirmar_escribe_el_id": "To confirm, type the episode id: {id}",
"ui.el_id_no_coincide_no": "The id does not match: nothing was deleted.",
"ui.capitulo_enviado_a_papelera": "Episode «{id}» sent to papelera/.",
"ui.todavia_no_hay_capitulos_crea": "There are no episodes yet: create the first one.",
"ui.titulo_del_nuevo_capitulo": "New episode title",
"ui.nuevo_capitulo": "＋ New episode",
"ui.avisos_de_este_capitulo": "Notices for this episode: ",
"ui.la_biblioteca_de_la_serie": "The series library.",
"ui.todo_lo_que_hay_aqui": "Everything here can be used from any episode. Search by id or name, filter by type or by use, and see in which episodes each item is used. Removing an item is refused while any episode uses it.",
"ui.buscar_por_id_o_nombre": "Search by id or name…",
"ui.todo": "All",
"ui.personajes_2": "Characters",
"ui.escenarios": "Sets",
"ui.utileria_3": "Props",
"ui.usados_y_sin_usar": "Used and unused",
"ui.solo_usados": "Used only",
"ui.sin_usar": "Unused",
"ui.cualquier_capitulo": "Any episode",
"ui.uso": "Use",
"ui.capitulo": "Episode",
"ui.importar_de_otro_proyecto_otra": "Import from another project (another series or film)",
"ui.importar_un_personaje": "Import a character",
"ui.importar_un_escenario": "Import a set",
"ui.importar_utileria": "Import props",
"ui.de_elementos_personajes_escenarios_utilerias": "{total} of {r} items · {characters} characters · {sets} sets · {props} props",
"ui.nada_coincide_con_el_filtro": "Nothing matches the filter.",
"ui.mostrar_mas": "Show more ({r})",
"ui.sin_usar_se_puede_quitar_2": "Unused: it can be removed.",
"ui.usado_en": "Used in: ",
"ui.abrir_el_capitulo": "Open episode «{e}»",
"ui.no_se_puede_quitar_lo": "«{id}» cannot be removed: it is used by episodes {eps}. Remove those uses first.",
"ui.importar_una_escena_de_otro": "Import a scene from another episode",
"ui.copia_la_escena_y_sus": "copies the scene and its shots",
"ui.este_capitulo_no_tiene_escenas": "(this episode has no scenes)",
"ui.capitulo_de_origen": "Source episode",
"ui.id_en_este_capitulo": "Id in this episode",
"ui.importar_escena": "Import scene",
"ui.elige_una_escena": "Choose a scene.",
"ui.se_copian_la_escena_y": "The scene and its shots are copied; ids that already exist in this episode get a suffix (id-2). Characters, sets and props belong to the series library and are already available. With the episode itself as source it duplicates a scene with its shots.",
"ui.hay_cambios_sin_guardar_en_2": "There are unsaved changes in this film. Discard them?",
"ui.titulo_de_la_nueva_pelicula": "Title of the new film",
"ui.nueva_pelicula": "New film",
"ui.pelicula_creada_empieza_importando_personajes": "Film «{id}» created. Start by importing characters and sets, then create a scene.",
"ui.titulo_de_la_nueva_serie": "Title of the new series",
"ui.nueva_serie": "New series",
"ui.serie_creada_crea_su_primer": "Series «{id}» created. Create its first episode and import characters and sets into the library.",
"ui.no_hay_proyectos_v2": "There are no v2 projects.",
"ui.crea_el_primero_con_nueva": "Create the first one with «＋ New film» or «＋ New series» (sidebar).",
"ui.error_al_cargar": "Error while loading",
"ui.use_cast_scene": "cast of scene «{id}» ({member})",
"ui.use_props_scene": "props of scene «{id}» ({member})",
"ui.no_importable_characters": "No other film has characters to import.",
"ui.no_importable_sets": "No other film has sets to import.",
"ui.no_importable_props": "No other film has props to import.",
"ui.n_capitulo": "{n} episode|{n} episodes",
"ui.n_plano": "{n} shot|{n} shots",
"ui.n_accion": "{n} action|{n} actions",
"ui.n_problema": "{n} problem|{n} problems",
"ui.n_personaje": "{n} character|{n} characters",
"ui.n_escenario": "{n} set|{n} sets",
"ui.n_utileria": "{n} prop|{n} props",
"ui.n_problema_scene": "{n} problem in this scene:|{n} problems in this scene:",
"ui.n_problema_script": "{n} problem in the script|{n} problems in the script",
"ui.member_in_shots": "«{id}» appears in {shots} ({list}) with {actions}. It will be removed from them and those actions deleted. Continue?",
"ui.member_has_actions": "«{id}» has {actions} in this shot. If you remove it they will be deleted. Continue?",
"ui.lost_from_scene": "Not in scene «{scene}»: {list}. They will be removed from the shot together with {actions}. Continue?",
"ui.library_counts": "Library: {characters} · {sets} · {props}. Saved in series.json.",
"ui.confirm_remove_series_item": "Remove {kind} «{id}» from the series library? {files}",
"ui.su_json_pasa_a_papelera": "Its JSON moves to papelera/ and the images are kept.",
"ui.scene_imported": "Scene «{id}» imported with {shots}. Save the episode to make it permanent.",
"ui.este": " (this one)",
"ui.word_actor": "actor",
"ui.default_scene_id": "scene",
"ui.default_shot_id": "shot",
"ui.default_layer_id": "layer",
"ui.lib_personaje": "character",
"ui.lib_escenario": "set",
"html.title": "Cel Studio · Studio v2",
"html.brand_aria": "Cel Studio, home",
"html.your_project": "YOUR PROJECT",
"html.current_project": "Current project",
"html.new_film": "＋ New film",
"html.new_series": "＋ New series",
"html.episode": "EPISODE",
"html.nav_aria": "Production stages",
"html.nav_episodes": "Episodes",
"html.nav_library": "Series library",
"html.nav_references": "References",
"html.nav_script": "Script",
"html.nav_characters": "Characters",
"html.nav_sets": "Sets and props",
"html.nav_scenes": "Scenes",
"html.nav_shots": "Shots",
"html.nav_render": "Render",
"html.pipeline": "Engine v2 · CPU animation",
"html.note_script": "The script is data: ",
"html.note_render": "The render is deterministic.",
"html.audio_note": "VOICE-OVER · LATER STAGE",
"html.breadcrumb": "LOCAL WORKSHOP",
"html.loading": "Loading…",
"html.none": "—",
"html.save": "Save script",
"html.eyebrow": "ENGINE V2",
"html.subtitle": "References, script, characters, sets, shots and render in one place.",
"html.stat_duration": "DURATION",
"html.stat_shots": "SHOTS",
"html.stat_fps": "FPS",
"html.job_title": "Rendering",
"html.cancel": "Cancel",
"html.open_video": "Open video ↗",
"html.footer_engine": "CEL STUDIO / ENGINE V2",
"html.footer_save": "Ctrl+S saves the script",
"html.footer_local": "LOCAL · SILENT VIDEO",
"html.language": "Language",
"verb.actor.drift": "Keep a held pose alive: each channel sways around its current value by +-amp (own phase), eased in and out\nso it leaves and returns to the held value exactly. Write it right after the move that created the hold.",
"verb.actor.gasp": "Sharp inhale: dip, then pop up and back, settle.",
"verb.actor.hop": "Anticipate, jump, land with squash and settle. Returns landing time.",
"verb.actor.laugh": "Shoulder/torso bounce while laughing.",
"verb.actor.overshoot": "Arrive at numeric channel values past the target by `over` (fraction of the move), then settle on them.",
"verb.actor.pulse": "Go to values and return to whatever was there before.",
"verb.actor.react": "Listener beat: the eyes lead (t), the head follows (+.05), the body leans last (+.14) and comes back.",
"verb.actor.to": "Hold the current value until t (+family lag), then arrive at the target after `dur`.\nA hand that changes direction travels on an arc around its shoulder, never in a straight line through the body.",
"verb.actor.track": "Eyes (and a little head) follow a flying prop (id in the shot).",
"verb.actor.turn_around": "Turn through a real front view: yaw toward camera, open into the frontal drawing, mirror there (the frontal\npose is symmetric, so nothing swaps sides on screen), and close into the new three-quarter view.",
"verb.actor.walk": "Foot-planted walk along x. Phase is tied to distance so stance feet do not slide.\nEach step lands on the heel, rolls flat, peels off over the toes and swings through with a bent knee.\n`view`: '3q' (default) walks in three-quarter view; 'profile' turns the body side-on (turn 2, needs the character's\nprofile art) with a short eased transition at both ends and returns to three-quarter at the end.",
"verb.actor.wave": "Raise the arm with anticipation, wave from the wrist/forearm, bring it down. Returns end time.",
"verb.actor.wave_off": "Farewell wave: pull-back anticipation, raise with overshoot and settle, cycles that taper off, a hang where the\nhand sags slowly, then a clean drop that overshoots the rest pose. Returns end time.",
"verb.prop.flap": "Flipbook wing cycle.",
"verb.prop.path": "Fly through world points with a Catmull-Rom path plus fluttery bobbing; dense linear keys.",
"verb.prop.perch": "Slow wing breathing while resting.",
"verb.shot.dof": "Depth of field: a number or keys [[t, value, ease?], ...].",
"verb.shot.puff_burst": "Dust puffs (library prop 'puff') thrown sideways from a point."
}
};
/* i18n:end */

init().catch(e => { toast(e.message); setStatus('ui.error_al_cargar'); });
