"""Messages for the user (script errors, API errors) in Spanish and English.

How it works
- `msg('p.falta_el_campo', key='fps')` returns a `Msg`: a `str` whose value is the Spanish text (so the CLI, logs and
  every existing test keep their messages) that also remembers its id and arguments.
- The API (`Service.handle`) picks the language of the request (`?lang=en`, or an Accept-Language value) and calls
  `localize`, which renders every `Msg` found in an error or in a response with the catalog of that language.
- Messages built from other messages (`join`, or a `Msg` or an exception passed as an argument) are rendered recursively.
- Data written by the user (story, names, notes) is never translated.

Add a language: add its code to LANGS, add a catalog (same ids and same {placeholders} as ES; tests/test_i18n.py checks it)
to CATALOGS, and a button in web/studio.html plus a block in web/studio.js (see «i18n» there).
"""
import re
import threading

DEFAULT = 'es'
LANGS = ('es', 'en')
_local = threading.local()

# Plain Spanish texts raised outside this layer (celstudio/model.py) that the API can still translate.
LEGACY = {
    'en': {
        'Ruta de recurso vacía': 'Empty asset path',
        'La ruta de recurso debe ser relativa al proyecto': 'The asset path must be relative to the project',
        'El recurso debe estar dentro del proyecto': 'The asset must be inside the project',
        'ID inválido: usa letras, números, guion o guion bajo': 'Invalid ID: use letters, numbers, hyphen or underscore',
    },
}


def _text(id_, args, lang):
    if id_ == '_join':
        sep, items, suffix = args['sep'], args['items'], args['suffix']
        return sep.join(render(item, lang) for item in items) + suffix
    template = CATALOGS.get(lang, {}).get(id_) or CATALOGS[DEFAULT].get(id_) or id_
    return template.format(**{k: render(v, lang) for k, v in args.items()})


class Msg(str):
    """A Spanish text that remembers its id and arguments, so it can be rendered in another language."""

    def __new__(cls, id_, args=None):
        args = dict(args or {})
        obj = super().__new__(cls, _text(id_, args, DEFAULT))
        obj.id, obj.args = id_, args
        return obj

    def __getnewargs__(self):          # copy.deepcopy / pickle
        return (self.id, self.args)

    def render(self, lang):
        return _text(self.id, self.args, lang)


def msg(id_, **args):
    return Msg(id_, args)


def join(sep, items, suffix=''):
    return Msg('_join', {'sep': sep, 'items': list(items), 'suffix': suffix})


def render(value, lang):
    """Text of `value` (a Msg, an exception raised with a Msg, or anything else) in `lang`."""
    if isinstance(value, Msg):
        return value.render(lang)
    if isinstance(value, BaseException):
        return render(value.args[0], lang) if value.args and isinstance(value.args[0], (Msg, str)) else str(value)
    if isinstance(value, str):
        return LEGACY.get(lang, {}).get(value, value)
    return value


def localize(value, lang):
    """Copy of a JSON-like `value` with every Msg (and known legacy text) rendered in `lang`."""
    if isinstance(value, str):
        return render(value, lang)
    if isinstance(value, dict):
        return {k: localize(v, lang) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [localize(v, lang) for v in value]
    return value


def pick_lang(query=None, accept=None):
    """Language for a request: `lang` in the query (dict of lists, as parse_qs gives, or plain), else an Accept-Language
    value (argument or `accept_language` in the query), else Spanish."""
    query = query or {}

    def one(name):
        value = query.get(name)
        return (value[0] if isinstance(value, (list, tuple)) and value else value) or ''
    wanted = str(one('lang')).strip().lower()[:2]
    if wanted in LANGS:
        return wanted
    header = accept or one('accept_language')
    ranked = []
    for n, part in enumerate(str(header).split(',')):
        tag, _, params = part.strip().partition(';')
        quality = re.search(r'q=([0-9.]+)', params)
        try:
            weight = float(quality.group(1)) if quality else 1.0
        except ValueError:
            weight = 0.0
        ranked.append((-weight, n, tag.strip().lower()[:2]))
    for _, _, tag in sorted(ranked):
        if tag in LANGS:
            return tag
    return DEFAULT


def set_current(lang):
    _local.lang = lang


def current():
    return getattr(_local, 'lang', DEFAULT)


ES = {
    'p.es_local_del_capitulo_y': '«{k}» es local del capítulo y tapa al de la biblioteca de la serie',
    'p.el_guion_debe_tener_una': 'El guion debe tener una lista «shots»',
    'p.conflicto_de_revision_se_esperaba': 'Conflicto de revisión: se esperaba la {expect_revision} pero el guion guardado es la {current}',
    'p.el_no_es_valido_usa': 'El {what} «{value}» no es válido: usa letras, números, guion o guion bajo',
    'p.se_requiere_kind_series_y': 'Se requiere kind "series" y schema_version 2',
    'p.conflicto_de_revision_se_esperaba_2': 'Conflicto de revisión: se esperaba la {expect_revision} pero la serie guardada es la {current}',
    'p.ya_existe_projects': 'Ya existe projects/{sid}',
    'p.no_es_una_serie_falta': '«{name}» no es una serie (falta series.json)',
    'p.ya_existe_el_capitulo': 'Ya existe el capítulo «{ep}»',
    'p.no_existe_el_capitulo': 'No existe el capítulo «{ep}»',
    'p.ya_existe_el_capitulo_2': 'Ya existe el capítulo «{new_id}»',
    'p.no_existe_la_escena_en': 'No existe la escena «{scene_id}» en el capítulo de origen',
    'p.ya_es_una_serie': '«{name}» ya es una serie',
    'p.no_existe_en': 'No existe {name} en {parent}',
    'p.no_es_json_valido': '{name} no es JSON válido: {e}',
    'p.la_ruta_de_debe_ser': 'La ruta de {what} debe ser un texto',
    'p.la_ruta_de_sale_del': 'La ruta de {what} sale del proyecto: {rel}',
    'p.falta_la_imagen': 'Falta la imagen: {rel}',
    'p.debe_ser_una_lista': '«{name}» debe ser una lista',
    'p.scenes_debe_ser_una_lista': '«scenes» debe ser una lista',
    'p.se_requiere_kind_script_y': 'Se requiere kind "script" y schema_version 2',
    'p.capitulo': '{message} (capítulo «{ep}»)',
    'p.falta_el_archivo_de': 'Falta el archivo de {what}: {rel}',
    'p.falta_el_argumento_obligatorio_de': 'Falta el argumento obligatorio «{name}» de «{name2}»',
    'p.argumento_inesperado_en': 'Argumento inesperado «{k}» en «{name}»',
    'p.el_tiempo_debe_ser_un': 'El tiempo «{k}» debe ser un número, no {a!r}',
    'p.curva_desconocida_usa_una_de': 'Curva desconocida «{a}»; usa una de: {a2}',
    'p.canal_desconocido': 'Canal desconocido «{channel}»',
    'p.expresion_desconocida_usa_una_de': 'Expresión desconocida «{name}»; usa una de: {a}',
    'p.prop_desconocido_en_este_plano': 'Prop desconocido «{prop}» en este plano',
    'p.la_escena_debe_ser_un': 'La escena debe ser un objeto',
    'p.la_escena_necesita_un_id': 'La escena necesita un «id» de texto',
    'p.id_de_escena_duplicado': 'Id de escena duplicado: «{sid}»',
    'p.la_escena_necesita_un_set': 'La escena «{sid}» necesita un «set» (escenario de la biblioteca)',
    'p.escena_desconocida': 'Escena desconocida «{scene}»',
    'p.un_plano_de_una_escena': 'Un plano de una escena no lleva «set»: usa el de la escena «{id}»',
    'p.el_guion_debe_ser_un': 'El guion debe ser un objeto JSON',
    'p.falta_el_campo': 'Falta el campo «{key}»',
    'p.fps_debe_ser_un_entero': '«fps» debe ser un entero positivo',
    'p.shots_debe_ser_una_lista': '«shots» debe ser una lista',
    'p.el_prop_debe_ser_un': 'El prop «{name}» debe ser un objeto',
    'p.el_plano_debe_ser_un': 'El plano debe ser un objeto',
    'p.el_plano_necesita_un_id': 'El plano necesita un «id» de texto',
    'p.la_duracion_debe_ser_un': 'La duración debe ser un número positivo, no {dur!r}',
    'p.escenario_desconocido': 'Escenario desconocido «{set_name}»',
    'p.error_inesperado_al_validar': 'Error inesperado al validar: {e!r}',
    'p.debe_ser_un_objeto': '«{kind}» debe ser un objeto',
    'p.el_tiempo_debe_ser_un_2': 'El tiempo debe ser un número, no {v!r}',
    'p.escenario_desconocido_en_la_escena': 'Escenario desconocido «{set}» en la escena «{sid}»',
    'p.id_no_valido': 'Id no válido: {item_id!r}',
    'p.debe_ser_una_lista_2': '«{section}» debe ser una lista',
    'p.el_miembro_del_reparto_debe': 'El miembro del reparto debe ser un objeto',
    'p.personaje_desconocido_no_esta_en': 'Personaje desconocido «{cid}» (no está en la biblioteca «characters»)',
    'p.start_debe_ser_un_objeto': '«start» debe ser un objeto',
    'p.la_utileria_debe_ser_un': 'La utilería debe ser un objeto',
    'p.prop_desconocido_no_esta_en': 'Prop desconocido «{lib}» (no está en la biblioteca «props»)',
    'p.spec_debe_ser_un_objeto': '«spec» debe ser un objeto sin «id» (el id va en el prop)',
    'p.debe_ser_una_lista_3': '«{section}» debe ser una lista',
    'p.usa_varios_valores_de_en': '«{id}» usa varios valores de «{own}» en el escenario «{set_name}»',
    'p.debe_ser_un_objeto_2': '«{section}» debe ser un objeto',
    'p.id_de_plano_duplicado': 'Id de plano duplicado: «{sid}»',
    'p.layer_order_debe_ser_un': '«layer_order» debe ser un objeto {{id de capa: número}}',
    'p.la_accion_debe_ser_un': 'La acción debe ser un objeto',
    'p.destino_desconocido_debe_ser_shot': 'Destino desconocido «{on}»: debe ser "shot" o el id de un actor o prop del plano',
    'p.verbo_desconocido_para': 'Verbo desconocido «{do}» para {kind} «{on}»',
    'p.el_archivo_no_es_json': 'El archivo {rel} no es JSON válido: {e}',
    'p.canal_desconocido_2': 'Canal desconocido «{k}»',
    'p.id_duplicado_en_la_escena': 'Id duplicado en la escena «{sid}»: «{item_id}»',
    'p.el_debe_ser_un_objeto': 'El {label} debe ser un objeto',
    'p.no_esta_en_de_la': '«{a}» no está en {place} de la escena «{id}»: {fix}',
    'p.debe_ser_un_objeto_3': '«{key}» debe ser un objeto',
    'p.lo_fija_la_escena_no': '«{own}» lo fija la escena «{id}» ({inherited}); no se cambia en el plano',
    'p.id_duplicado_en_el_plano': 'Id duplicado en el plano: «{item_id}»',
    'p.personaje_desconocido': 'Personaje desconocido «{cid}»',
    'p.canal_desconocido_en_start': 'Canal desconocido «{k}» en start',
    'p.no_se_pudo_crear_el': 'No se pudo crear el actor: {e!r}',
    'p.no_se_pudo_crear_el_2': 'No se pudo crear el prop: {e!r}',
    'p.fallo_sobre': 'Falló «{do}» sobre «{on}»: {e!r}',
    'p.no_es_una_capa_del': '«{k}» no es una capa del escenario «{set_name}»',
    'p.order_debe_ser_un_numero': '«order» debe ser un número, no {order!r}',
    'p.el_orden_de_la_capa': 'El orden de la capa «{k}» debe ser un número, no {v!r}',
    'a.no_se_pudo_codificar_la': 'No se pudo codificar la imagen',
    'a.pelicula_inexistente': 'Película inexistente',
    'a.serie_inexistente': 'Serie inexistente',
    'a.no_esta_declarado_en_el': '«{name}» no está declarado en el guion ({section})',
    'a.el_guion_debe_ser_un': 'El guion debe ser un objeto JSON',
    'a.el_rig_debe_ser_un': 'El rig debe ser un objeto JSON',
    'a.el_escenario_debe_ser_un': 'El escenario debe ser un objeto JSON',
    'a.recurso_mayor_a_20_mb': 'Recurso mayor a 20 MB',
    'a.no_existe_el_en_esa': 'No existe el {a} «{name}» en esa película',
    'a.kind_debe_ser_characters_sets': '«kind» debe ser characters, sets o props',
    'a.ese_elemento_ya_es_de': 'Ese elemento ya es de esta película: usa Duplicar',
    'a.falta_spec_sheet_imagen_de': 'Falta «spec.sheet» (imagen de la hoja, ya subida)',
    'a.no_existe_la_imagen': 'No existe la imagen {sheet}',
    'a.falta_el_titulo': 'Falta el título',
    'a.para_borrar_el_capitulo_escribe': 'Para borrar el capítulo escribe su id («{ep}») en «confirm»',
    'a.solo_los_capitulos_de_una': 'Sólo los capítulos de una serie pueden importar escenas',
    'a.capitulo_de_origen_inexistente': 'Capítulo de origen inexistente',
    'a.plano_inexistente': 'Plano inexistente',
    'a.el_ancho_debe_estar_entre': 'El ancho debe estar entre 160 y 1280',
    'a.tiempo_no_valido': 'Tiempo no válido',
    'a.la_pelicula_no_esta_compilada': 'La película no está compilada: guarda el guion primero',
    'a.falta_script': 'Falta «script»',
    'a.turn_debe_estar_entre_0': '«turn» debe estar entre 0 (frente) y 1 (tres cuartos)',
    'a.la_pelicula_no_tiene_planos': 'La película no tiene planos que renderizar',
    'a.ruta_inexistente': 'Ruta inexistente',
    'a.capitulo': '{message} (capítulo «{current}»)',
    'a.no_se_puede_cambiar_el': 'No se puede cambiar el id del guion',
    'a.no_es_valido': 'No es válido: {error}',
    'a.el_escenario_no_esta_en': 'El escenario «{target}» no está en la película',
    'a.categoria_no_valida_set_layer': 'Categoría no válida: set_layer o prop_sheet',
    'a.el_archivo_no_es_una': 'El archivo no es una imagen válida',
    'a.falta_data_en_base64': 'Falta «data» en base64',
    'a.la_utileria_no_es_un': 'La utilería no es un objeto',
    'a.ya_existe_en': 'Ya existe «{new_id}» en {kind}',
    'a.ya_existe_el_escenario': 'Ya existe el escenario «{name}»',
    'a.ya_existe_el_archivo_sets': 'Ya existe el archivo sets/{name}.json',
    'a.ya_existe_la_utileria': 'Ya existe la utilería «{name}»',
    'a.no_existe_el': 'No existe el {a} «{name}»',
    'a.no_se_puede_quitar_quita': 'No se puede quitar «{name}»: {shown}. Quita antes esos usos.',
    'a.limit_y_offset_deben_ser': '«limit» y «offset» deben ser enteros',
    'a.ancho_no_valido': 'Ancho no válido',
    'a.expresion_desconocida': 'Expresión desconocida',
    'a.el_ancho_debe_ser_un': 'El ancho debe ser un entero entre 160 y 3840',
    'a.el_archivo_de_render_ya': 'El archivo de render ya existe',
    'a.el_cambio_rompe_la_pelicula': 'El cambio rompe la película: {error}',
    'a.imagen_mayor_a_20_megapixeles': 'Imagen mayor a 20 megapíxeles',
    'a.el_archivo_no_es_una_2': 'El archivo no es una imagen válida ni un .txt/.md',
    'a.es_local_de_este_capitulo': '«{name}» es local de este capítulo: quítalo de su guion, no de la biblioteca de la serie',
    'a.ya_existe_projects': 'Ya existe projects/{sid}',
    'a.debe_ser_un_objeto': '«{key}» debe ser un objeto',
    'a.capitulo_inexistente': 'Capítulo inexistente',
    'p.what_character': 'el personaje «{cid}»',
    'p.what_set': 'el escenario «{name}»',
    'w.actor': 'actor',
    'w.prop': 'utilería',
    'w.series_id': 'id de la serie',
    'w.episode_id': 'id del capítulo',
    'w.scene_id': 'id de la escena',
    'w.global': '(global)',
    'p.path_message': '{path}: {message}',
    'p.fix_cast': 'añádelo al reparto de la escena',
    'p.fix_props': 'añádela a la utilería de la escena',
    'p.place_cast': 'el reparto',
    'p.place_props': 'la utilería',
    'p.use_burst_shot': 'lo usa «puff_burst» en el plano «{id}»',
    'p.use_scene_set': 'es el escenario de la escena «{id}»',
    'p.use_shot_set': 'es el escenario de el plano «{id}»',
    'p.use_scene_cast': 'está en el reparto de la escena «{id}»',
    'p.use_scene_props': 'está en la utilería de la escena «{id}»',
    'p.use_shot_member': 'aparece en el plano «{id}»',
    'a.invalid_ref_kind': 'Tipo de referencia no válido: {kinds}',
    'lib.characters': 'personaje',
    'lib.sets': 'escenario',
    'lib.props': 'utilería',
}

EN = {
    'p.es_local_del_capitulo_y': '«{k}» is local to the episode and hides the one in the series library',
    'p.el_guion_debe_tener_una': 'The script must have a «shots» list',
    'p.conflicto_de_revision_se_esperaba': 'Revision conflict: revision {expect_revision} was expected but the saved script is at {current}',
    'p.el_no_es_valido_usa': 'The {what} «{value}» is not valid: use letters, numbers, hyphen or underscore',
    'p.se_requiere_kind_series_y': 'kind "series" and schema_version 2 are required',
    'p.conflicto_de_revision_se_esperaba_2': 'Revision conflict: revision {expect_revision} was expected but the saved series is at {current}',
    'p.ya_existe_projects': 'projects/{sid} already exists',
    'p.no_es_una_serie_falta': '«{name}» is not a series (series.json is missing)',
    'p.ya_existe_el_capitulo': 'Episode «{ep}» already exists',
    'p.no_existe_el_capitulo': 'Episode «{ep}» does not exist',
    'p.ya_existe_el_capitulo_2': 'Episode «{new_id}» already exists',
    'p.no_existe_la_escena_en': 'Scene «{scene_id}» does not exist in the source episode',
    'p.ya_es_una_serie': '«{name}» is already a series',
    'p.no_existe_en': '{name} does not exist in {parent}',
    'p.no_es_json_valido': '{name} is not valid JSON: {e}',
    'p.la_ruta_de_debe_ser': 'The path of {what} must be a string',
    'p.la_ruta_de_sale_del': 'The path of {what} leaves the project: {rel}',
    'p.falta_la_imagen': 'Missing image: {rel}',
    'p.debe_ser_una_lista': '«{name}» must be a list',
    'p.scenes_debe_ser_una_lista': '«scenes» must be a list',
    'p.se_requiere_kind_script_y': 'kind "script" and schema_version 2 are required',
    'p.capitulo': '{message} (episode «{ep}»)',
    'p.falta_el_archivo_de': 'Missing file of {what}: {rel}',
    'p.falta_el_argumento_obligatorio_de': 'Missing required argument «{name}» of «{name2}»',
    'p.argumento_inesperado_en': 'Unexpected argument «{k}» in «{name}»',
    'p.el_tiempo_debe_ser_un': 'The time «{k}» must be a number, not {a!r}',
    'p.curva_desconocida_usa_una_de': 'Unknown curve «{a}»; use one of: {a2}',
    'p.canal_desconocido': 'Unknown channel «{channel}»',
    'p.expresion_desconocida_usa_una_de': 'Unknown expression «{name}»; use one of: {a}',
    'p.prop_desconocido_en_este_plano': 'Unknown prop «{prop}» in this shot',
    'p.la_escena_debe_ser_un': 'The scene must be an object',
    'p.la_escena_necesita_un_id': 'The scene needs a text «id»',
    'p.id_de_escena_duplicado': 'Duplicate scene id: «{sid}»',
    'p.la_escena_necesita_un_set': 'Scene «{sid}» needs a «set» (a set from the library)',
    'p.escena_desconocida': 'Unknown scene «{scene}»',
    'p.un_plano_de_una_escena': 'A shot inside a scene takes no «set»: it uses the one of scene «{id}»',
    'p.el_guion_debe_ser_un': 'The script must be a JSON object',
    'p.falta_el_campo': 'Missing field «{key}»',
    'p.fps_debe_ser_un_entero': '«fps» must be a positive integer',
    'p.shots_debe_ser_una_lista': '«shots» must be a list',
    'p.el_prop_debe_ser_un': 'The prop «{name}» must be an object',
    'p.el_plano_debe_ser_un': 'The shot must be an object',
    'p.el_plano_necesita_un_id': 'The shot needs a text «id»',
    'p.la_duracion_debe_ser_un': 'The duration must be a positive number, not {dur!r}',
    'p.escenario_desconocido': 'Unknown set «{set_name}»',
    'p.error_inesperado_al_validar': 'Unexpected error while validating: {e!r}',
    'p.debe_ser_un_objeto': '«{kind}» must be an object',
    'p.el_tiempo_debe_ser_un_2': 'The time must be a number, not {v!r}',
    'p.escenario_desconocido_en_la_escena': 'Unknown set «{set}» in scene «{sid}»',
    'p.id_no_valido': 'Invalid id: {item_id!r}',
    'p.debe_ser_una_lista_2': '«{section}» must be a list',
    'p.el_miembro_del_reparto_debe': 'The cast member must be an object',
    'p.personaje_desconocido_no_esta_en': 'Unknown character «{cid}» (not in the «characters» library)',
    'p.start_debe_ser_un_objeto': '«start» must be an object',
    'p.la_utileria_debe_ser_un': 'The prop entry must be an object',
    'p.prop_desconocido_no_esta_en': 'Unknown prop «{lib}» (not in the «props» library)',
    'p.spec_debe_ser_un_objeto': '«spec» must be an object without «id» (the id goes in the prop)',
    'p.debe_ser_una_lista_3': '«{section}» must be a list',
    'p.usa_varios_valores_de_en': '«{id}» uses several values of «{own}» in set «{set_name}»',
    'p.debe_ser_un_objeto_2': '«{section}» must be an object',
    'p.id_de_plano_duplicado': 'Duplicate shot id: «{sid}»',
    'p.layer_order_debe_ser_un': '«layer_order» must be an object {{layer id: number}}',
    'p.la_accion_debe_ser_un': 'The action must be an object',
    'p.destino_desconocido_debe_ser_shot': 'Unknown target «{on}»: it must be "shot" or the id of an actor or prop of the shot',
    'p.verbo_desconocido_para': 'Unknown verb «{do}» for {kind} «{on}»',
    'p.el_archivo_no_es_json': 'The file {rel} is not valid JSON: {e}',
    'p.canal_desconocido_2': 'Unknown channel «{k}»',
    'p.id_duplicado_en_la_escena': 'Duplicate id in scene «{sid}»: «{item_id}»',
    'p.el_debe_ser_un_objeto': 'The {label} must be an object',
    'p.no_esta_en_de_la': '«{a}» is not in {place} of scene «{id}»: {fix}',
    'p.debe_ser_un_objeto_3': '«{key}» must be an object',
    'p.lo_fija_la_escena_no': '«{own}» is set by scene «{id}» ({inherited}); it is not changed in the shot',
    'p.id_duplicado_en_el_plano': 'Duplicate id in the shot: «{item_id}»',
    'p.personaje_desconocido': 'Unknown character «{cid}»',
    'p.canal_desconocido_en_start': 'Unknown channel «{k}» in start',
    'p.no_se_pudo_crear_el': 'The actor could not be created: {e!r}',
    'p.no_se_pudo_crear_el_2': 'The prop could not be created: {e!r}',
    'p.fallo_sobre': '«{do}» failed on «{on}»: {e!r}',
    'p.no_es_una_capa_del': '«{k}» is not a layer of set «{set_name}»',
    'p.order_debe_ser_un_numero': '«order» must be a number, not {order!r}',
    'p.el_orden_de_la_capa': 'The order of layer «{k}» must be a number, not {v!r}',
    'a.no_se_pudo_codificar_la': 'The image could not be encoded',
    'a.pelicula_inexistente': 'Film does not exist',
    'a.serie_inexistente': 'Series does not exist',
    'a.no_esta_declarado_en_el': '«{name}» is not declared in the script ({section})',
    'a.el_guion_debe_ser_un': 'The script must be a JSON object',
    'a.el_rig_debe_ser_un': 'The rig must be a JSON object',
    'a.el_escenario_debe_ser_un': 'The set must be a JSON object',
    'a.recurso_mayor_a_20_mb': 'Asset larger than 20 MB',
    'a.no_existe_el_en_esa': 'The {a} «{name}» does not exist in that film',
    'a.kind_debe_ser_characters_sets': '«kind» must be characters, sets or props',
    'a.ese_elemento_ya_es_de': 'That item already belongs to this film: use Duplicate',
    'a.falta_spec_sheet_imagen_de': 'Missing «spec.sheet» (sheet image, already uploaded)',
    'a.no_existe_la_imagen': 'The image {sheet} does not exist',
    'a.falta_el_titulo': 'Missing title',
    'a.para_borrar_el_capitulo_escribe': 'To delete the episode type its id («{ep}») in «confirm»',
    'a.solo_los_capitulos_de_una': 'Only the episodes of a series can import scenes',
    'a.capitulo_de_origen_inexistente': 'Source episode does not exist',
    'a.plano_inexistente': 'Shot does not exist',
    'a.el_ancho_debe_estar_entre': 'The width must be between 160 and 1280',
    'a.tiempo_no_valido': 'Invalid time',
    'a.la_pelicula_no_esta_compilada': 'The film is not compiled: save the script first',
    'a.falta_script': 'Missing «script»',
    'a.turn_debe_estar_entre_0': '«turn» must be between 0 (front) and 1 (three-quarter)',
    'a.la_pelicula_no_tiene_planos': 'The film has no shots to render',
    'a.ruta_inexistente': 'Route does not exist',
    'a.capitulo': '{message} (episode «{current}»)',
    'a.no_se_puede_cambiar_el': 'The script id cannot be changed',
    'a.no_es_valido': 'Not valid: {error}',
    'a.el_escenario_no_esta_en': 'Set «{target}» is not in the film',
    'a.categoria_no_valida_set_layer': 'Invalid category: set_layer or prop_sheet',
    'a.el_archivo_no_es_una': 'The file is not a valid image',
    'a.falta_data_en_base64': 'Missing «data» in base64',
    'a.la_utileria_no_es_un': 'The prop is not an object',
    'a.ya_existe_en': '«{new_id}» already exists in {kind}',
    'a.ya_existe_el_escenario': 'Set «{name}» already exists',
    'a.ya_existe_el_archivo_sets': 'File sets/{name}.json already exists',
    'a.ya_existe_la_utileria': 'Prop «{name}» already exists',
    'a.no_existe_el': 'The {a} «{name}» does not exist',
    'a.no_se_puede_quitar_quita': '«{name}» cannot be removed: {shown}. Remove those uses first.',
    'a.limit_y_offset_deben_ser': '«limit» and «offset» must be integers',
    'a.ancho_no_valido': 'Invalid width',
    'a.expresion_desconocida': 'Unknown expression',
    'a.el_ancho_debe_ser_un': 'The width must be an integer between 160 and 3840',
    'a.el_archivo_de_render_ya': 'The render file already exists',
    'a.el_cambio_rompe_la_pelicula': 'The change breaks the film: {error}',
    'a.imagen_mayor_a_20_megapixeles': 'Image larger than 20 megapixels',
    'a.el_archivo_no_es_una_2': 'The file is not a valid image nor a .txt/.md',
    'a.es_local_de_este_capitulo': '«{name}» is local to this episode: remove it from its script, not from the series library',
    'a.ya_existe_projects': 'projects/{sid} already exists',
    'a.debe_ser_un_objeto': '«{key}» must be an object',
    'a.capitulo_inexistente': 'Episode does not exist',
    'p.what_character': 'character «{cid}»',
    'p.what_set': 'set «{name}»',
    'w.actor': 'actor',
    'w.prop': 'prop',
    'w.series_id': 'series id',
    'w.episode_id': 'episode id',
    'w.scene_id': 'scene id',
    'w.global': '(global)',
    'p.path_message': '{path}: {message}',
    'p.fix_cast': 'add it to the scene cast',
    'p.fix_props': 'add it to the scene props',
    'p.place_cast': 'the cast',
    'p.place_props': 'the props',
    'p.use_burst_shot': 'used by «puff_burst» in shot «{id}»',
    'p.use_scene_set': 'is the set of scene «{id}»',
    'p.use_shot_set': 'is the set of shot «{id}»',
    'p.use_scene_cast': 'is in the cast of scene «{id}»',
    'p.use_scene_props': 'is in the props of scene «{id}»',
    'p.use_shot_member': 'appears in shot «{id}»',
    'a.invalid_ref_kind': 'Invalid reference type: {kinds}',
    'lib.characters': 'character',
    'lib.sets': 'set',
    'lib.props': 'prop',
}

CATALOGS = {'es': ES, 'en': EN}
