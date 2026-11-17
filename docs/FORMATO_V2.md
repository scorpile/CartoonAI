> English version: [docs/en/FORMAT.md](en/FORMAT.md) · Volver al [README](../README.es.md)

# Formato de proyecto v2 (motor `celstudio/v2`)

Un proyecto v2 es una carpeta bajo `projects/<id>/`. La **fuente de verdad** es `script.json` (el guion como datos).
`film.json` es el resultado compilado (fotogramas clave ya calculados); no se edita a mano.

```
projects/taller-v3/
  script.json            guion declarativo (se edita)
  script.previous.json   copia de la versión anterior (la crea save())
  film.json              compilado, schema 2 (lo lee el motor)
  characters/luma.json   rig de cada personaje
  sets/valley.json       escenario
  assets/                imágenes: assets/<personaje>/, assets/sets/<escenario>/, assets/props/<utilería>/
  refs/                  referencias subidas
  papelera/              JSON de personajes y escenarios quitados de la biblioteca (nunca se borra nada)
  renders/               vídeos
```

Todas las rutas son relativas a la carpeta del proyecto, deben existir y no pueden salir de ella.

Comandos:

```
python -m celstudio.v2 compile projects/taller-v3     # script.json -> film.json (resumen JSON; error y código 1 si no es válido)
python -m celstudio.v2 render projects/taller-v3/film.json --output salida.mp4
python work/v3/build_film.py                          # regenera el piloto (en forma de escenas): lo graba en script.json y compila
```

API Python (`celstudio/v2/project.py`): `load(root)`, `compile_script(script, root)`, `check(script, root)` (lista de
`{"path", "message"}`, vacía si es válido), `save(root, script, expect_revision=None)`, `catalogue()`, `expand(script)` (forma plana de un guion con escenas), `group_scene(script, ...)` (la inversa, para scripts de generación) y `usage(script, kind, id)` (dónde se usa un elemento de la biblioteca). Los errores son
`ScriptError` con `.path` (por ejemplo `shots[2].actions[14]`) y mensaje en español.

## Personajes (`characters/<id>.json`)

Se generan con `work/v3/build_rig.py` a partir de las partes medidas en `assets/<id>/rig.json`; normalmente no se escriben a mano.
Campos principales (unidades del mundo: 1280x720, personaje a escala 1):

| Campo | Significado |
|---|---|
| `name`, `colors` | Nombre y paleta (`outline`, `skin`, `eye_white`, `pupil`, `mouth_inside`, `tongue`, `blush`, `sleeve`, `cuff`...) |
| `outline` | Grosor del contorno |
| `hip_height`, `hip_half`, `hip_joint_dy`, `ankle_h` | Altura de la cadera sobre el suelo, mitad de separación de los pies, ajustes de pierna |
| `foot` | `toe`, `heel`, `depth`: geometría del pie para el paso |
| `arm`, `leg` | Longitudes (`upper`/`fore`, `thigh`/`shin`), anchos por tramo `w`, `smooth`, bandas de color (`bands`), puño (`cuff`), brillos |
| `torso`, `hips` | Imagen (`file`), escala `upp` (unidades por píxel), `pivot`; el torso añade `shoulder` y `neck`; `"merge": false` en un dibujo de torso evita que el motor tape la raíz del brazo con el color del torso (útil cuando la ropa del hombro no es del color de la manga) |
| `hands` | Una imagen por pose de mano (`closed`, `open`, `point`...), con `upp`, `pivot` (centro del corte de la muñeca) y `dir` (hacia dónde apuntan los dedos). El dibujo principal es la palma; `back`, opcional y con los mismos campos, es el dorso. En ambos el pulgar va un cuarto de vuelta en sentido antihorario respecto a los dedos. El motor elige cara y espejo por anatomía |
| `boots` | Imagen de bota por vista (`side`...) y su boca de salida de la pierna |
| `head` | Vistas `front` y `3q`: imagen, máscara, `size`, `upp`, `pivot`, cara (`eye_*`, `brow_*`, `blush_*`, `mouth`, `bbox`) y apéndices (`ear_l`, `antenna`...: `base`, `tip`, `freq`, `damp`, `gain`) |
| `items` (opcional) | Objetos que se sostienen con la mano: `{"tenedor": {"file", "upp", "pivot", "dir", "rot"?, "front"?}}`. El canal `item_l` / `item_r` elige el objeto (`""` = mano vacía). Se dibuja en el espacio de la mano, sobre su punto `grip` (si la mano no lo tiene, su `pivot`), con el eje `dir` del objeto hacia el lado del pulgar; detrás de la mano salvo con `"front": true`, de modo que una mano de agarre con hueco lo rodea. Sigue la capa y el espejo del brazo |
| `wear` (opcional) | Prendas sobre el torso: `{"babero": {"front": {...}, "profile": {...}, "back3q": {...}}}` con `file`, `upp`, `pivot` y `at` (posición del pivote respecto al punto `neck` del torso). El canal `wear` elige la prenda; se deforma con el torso (curva, giro, bajo) y falta en las vistas sin dibujo |
| `defaults` (opcional) | Valores por defecto de canales para ese personaje |

Capas delanteras entre actores: una capa con `"front": true` tapa a todos los actores; si además tiene `"order": N`, se dibuja después de los actores con `order` < N y antes de los demás (la manta tapa solo a quien duerme debajo, el marco de la puerta solo a quien la cruza). Un plano puede cambiarlo con `"layer_order": {"<id de capa>": N}`. El orden de un actor también puede animarse con claves en el canal `order` (con `ease` `step`), que prevalece sobre su campo `order` fijo: así un personaje pasa por delante del marco de una puerta mientras camina por el sendero y por detrás al cruzar el umbral.

Canales por ojo: `lid_l` y `lid_r` se suman a `lid` (con `lid` 1 y `lid_r` −1 el personaje duerme con un ojo abierto).

Los puntos de anclaje que usa la utilería (`tip_antenna`, `tip_ear_r`) vienen de los apéndices de la cabeza.

## Escenarios (`sets/<nombre>.json`)

`work/v3/valley_set.py` genera `sets/valley.json`. Claves:

| Clave | Contenido |
|---|---|
| `color` | Color de fondo |
| `ground_y` | Línea de suelo (y del mundo; los actores usan `y` = suelo) |
| `layers` | Capas de imagen, de lejos a cerca: `id`, `image`, `x`, `y`, `w` (ancho en mundo), `depth` (paralaje: `.03` casi fija, `1.0` = plano de los actores, `>1` primer plano), `blur` (desenfoque por profundidad de campo), `front` (se dibuja delante de los actores), `opacity`, `drift` (`vx`, `wrap`: nubes que se desplazan), `sway` (`deg`, `period`, `phase`, `anchor`: balanceo) |
| `lights` | Luces blandas: `x`, `y`, `depth`, `radius`, `color`, `opacity`, `pulse`, `period`, `flicker`, `front` |
| `smoke` | Humo: `x`, `y`, `depth`, `rate`, `rise`, `life`, `size`, `drift`, `opacity` |
| `particles` | `kind` (`motes`, `leaves`), `count`, `area` [x0,y0,x1,y1], `depth`, `color`, `size`, `opacity`, `speed` |
| `rays` | Rayos de luz: origen, `count`, `length`, `spread_deg`, `direction_deg`, `color`, `opacity` |
| `light` | Iluminación de personajes: `ambient` (`color`, `amount`), `rim` y `shade` (`dir`, `color`, `opacity`, `width`), `shadow` con `contact` (elipse en el suelo) y `cast` (sombra proyectada: `shear`, `squash`, `blur`...) |
| `post` | `bloom`, `grade` (contraste, saturación, temperatura, lift, gain), `vignette`, `grain` |

El compilador copia cada escenario dentro de `film.json`. Si un plano necesitara `light` o `post` propios, hoy no hay verbo para ello.

## Utilería (`props` de `script.json`)

Biblioteca de utilería con nombre: `props.<nombre>` es la especificación de una hoja de sprites. Campos: `sheet` (imagen),
`cells` (recuadros `[x0,y0,x1,y1]` de cada fotograma), `pivot`, `upp`, `layer` (`front`), `shadow` (`ground`, `width`), `id` por defecto.
En un plano se coloca con `{"id": "butterfly", "prop": "butterfly", "spec": {...}}`: `spec` se mezcla sobre la biblioteca
(por ejemplo `anchor`: `{"actor": "pip", "point": "tip_antenna", "dx": 2, "dy": -3}` pega la utilería a un punto del personaje cuando
su canal `attach` vale 1). Canales de utilería habituales: `x`, `y`, `scale`, `rot`, `opacity`, `frame`, `facing`, `attach`, `shadow`.
Las nubes de polvo de `puff_burst` usan el prop `puff` de la biblioteca y reciben ids `puff<t>-<i>`.

## Biblioteca y escenas

Tres niveles: **biblioteca** (proyecto) → **escena** → **plano**.

- La **biblioteca** son `characters`, `sets` y `props` del guion: lo que existe en la película.
- Una **escena** (`scenes`, lista opcional) elige un escenario, un **reparto** (instancias de personajes de la biblioteca; puede haber varias del mismo personaje con ids distintos) y la utilería disponible. `start` del reparto son los valores por defecto de la escena.
- Un **plano** pertenece a una escena (`scene`) y usa un subconjunto de su reparto y utilería. El orden de la película es el de `shots`, así que las escenas pueden alternarse; el orden de `scenes` es sólo organizativo.

```json
"scenes": [{"id": "taller", "title": "El taller al atardecer", "description": "...", "set": "valley",
  "cast":  [{"id": "luma", "character": "luma", "start": {"y": 690.0, "scale": 0.66}},
            {"id": "pip",  "character": "pip",  "start": {"x": 838, "y": 690.0, "scale": 0.66}}],
  "props": [{"id": "butterfly", "prop": "butterfly", "spec": {}}]}],
"shots": [{"id": "s02", "scene": "taller", "duration": 3.8, "description": "...",
  "actors": [{"id": "pip", "start": {"facing": 1}}], "props": [], "actions": []}]
```

Reglas: `actors[i].id` es un id del reparto y su `start` se mezcla clave a clave sobre el de la escena (gana el del plano); `character` se hereda y no se cambia en el plano. Igual para la utilería (`spec` del plano sobre `spec` de la escena sobre la biblioteca; mezcla superficial). Los verbos que usan la biblioteca directamente (`puff_burst`) no necesitan que el prop esté en la escena. Los guiones sin `scenes` (planos con `set` y reparto propios) siguen funcionando igual y ambas formas pueden mezclarse. `expand()` convierte la forma de escenas a la plana y `compile_script` compila esa forma, así que las dos dan el mismo `film.json`.

Las escenas se validan con ruta (`scenes[1].cast[0]`, `shots[3].actors[1]`): escena desconocida, escenario/personaje/prop desconocido, ids duplicados (reparto y utilería comparten espacio de ids), actor o prop que no está en la escena, canal desconocido en `start`, escena sin `set`, plano con `scene` y `set`.

**Operaciones de biblioteca** (las hace el servidor en disco y devuelven el elemento cambiado y la nueva `revision`; la página las mezcla en su guion sin perder ediciones sin guardar y sin conflicto de revisión, como la subida de referencias):

- *Importar* de otra película de `projects/`: copia el JSON y todas las imágenes que referencia a `assets/<id>/`, `assets/sets/<id>/` o `assets/props/<id>/`, reescribe las rutas (la copia es autónoma) y elige otro id (`id-2`) si hay colisión.
- *Duplicar* dentro del proyecto con otro id (un escenario con otra luz o menos capas es un escenario nuevo legítimo).
- *Escenario vacío* (color liso, sin capas) al que se suben capas (`assets/sets/<id>/`) y se reordenan; *utilería nueva* con la hoja subida (`cells`, `pivot`, `upp` se ajustan en su JSON).
- *Quitar*: se rechaza si lo usa alguna escena o plano (indica dónde; comprueba también el guion sin guardar del navegador). Sólo lo da de baja: el JSON de un personaje o escenario pasa a `papelera/` y las imágenes se quedan.
- *Película nueva*: `projects/<id>/` con un guion mínimo válido (bibliotecas vacías, sin escenas ni planos).
- Crear un personaje nuevo desde arte no se hace en la app: requiere `work/v3/prep_parts.py` y `build_rig.py`.

## Series y capítulos

Un proyecto puede ser una **película suelta** (`projects/<id>/script.json`, todo lo anterior) o una **serie**: una biblioteca compartida con muchos capítulos. Los guiones pertenecen a los capítulos; todo lo de la biblioteca se puede usar desde cualquiera. Una carpeta con `series.json` es una serie; una con `script.json` y sin `series.json`, una película (compatible sin cambios).

```
projects/mi-serie/
  series.json              id, title, revision, notes, bible, style, fps/width/height, references, library
  characters/<id>.json     rigs (rutas relativas a la raíz de la serie)
  sets/<id>.json           escenarios
  assets/<id>/  assets/sets/<id>/  assets/props/<id>/   imágenes de la biblioteca
  refs/  papelera/         referencias subidas; elementos y capítulos quitados (nunca se borra nada)
  episodes/ep01/
    script.json            guion del capítulo: title, notes, story, scenes, shots (sin biblioteca propia)
    film.json              compilado; incluye "root": "../.." (la raíz de los assets, relativa a su carpeta)
    renders/               vídeos del capítulo
```

`series.json`: `{"schema_version": 2, "kind": "series", "id", "title", "revision", "notes", "bible", "style", "fps", "width", "height", "references": [], "library": {"characters": {id: ruta}, "sets": {id: ruta}, "props": {id: especificación}}}`. Las rutas de los assets son relativas a la **raíz de la serie**, no a la del capítulo.

- **Biblioteca efectiva** de un capítulo = biblioteca de la serie + bloque local opcional `characters` / `sets` / `props` en su `script.json`, para elementos que sólo existen en ese capítulo (el local gana si el id coincide; `project.warnings()` y la app lo avisan). `fps`, `width`, `height`, `style` y `bible` se heredan de la serie si el capítulo no los define; las `references` de la serie se suman a las del capítulo.
- `project.load(<carpeta del capítulo>)` devuelve el guion efectivo (con la biblioteca mezclada) y `project.save()` lo guarda sin copiar la biblioteca de la serie al capítulo. `compile_script` / `check` / `save` aceptan la carpeta del capítulo (`projects/<serie>/episodes/<cap>`); el compilado sólo incluye los elementos que el capítulo usa, así que un elemento roto que nadie usa no rompe los demás capítulos. `Stage` / `load_film` leen `root` de `film.json`; el render es el mismo.
- Las **escenas** siguen siendo del capítulo (escenario + reparto + utilería + sus planos). `project.import_scene(destino, origen, id, nuevo_id)` copia una escena y sus planos de otro capítulo (o del mismo, para duplicarla); los ids que chocan reciben sufijo (`id-2`) y los elementos locales del origen que faltan se copian al bloque local.
- `project.usage_table(script)`, `series_usage(raíz)` (qué capítulos, escenas y planos usan cada personaje, escenario y utilería), `usage_in_series` y `library_catalogue(raíz, q, kind, used, episode, limit, offset)` (listado compacto, filtrable y paginado para cientos de elementos).
- Quitar un elemento de la biblioteca de la serie se rechaza mientras lo use algún capítulo (el mensaje nombra los capítulos). Borrar un capítulo mueve su carpeta a `papelera/episodes/`.

Comandos:

```
python -m celstudio.v2 new-series mi-serie --title "Mi serie"        # projects/mi-serie/series.json con biblioteca vacía
python -m celstudio.v2 new-episode mi-serie ep01 --title "Piloto"    # projects/mi-serie/episodes/ep01/
python -m celstudio.v2 compile projects/mi-serie/episodes/ep01       # (o .../script.json) -> film.json del capítulo
python -m celstudio.v2 render projects/mi-serie/episodes/ep01/film.json --output salida.mp4
python -m celstudio.v2 series-convert projects/<película>            # película suelta -> serie con el capítulo ep01
```

`series-convert` mueve la biblioteca a `series.json` y el guion a `episodes/ep01/` (también `renders/`), y recompila; no borra nada más.

API (`/api/v2`): `GET films` lista películas (`kind` `film`) y series (`kind` `series`, con `episodes` y `library`). Un capítulo se dirige como una película con `films/<serie>/episodes/<cap>/...` y admite las mismas acciones (`GET`/`POST` del guion, `check`, `frame`, `preview`, `pose`, `setframe`, `characters/<id>`, `sets/<id>`, `upload`, `render`, `importable`, `library/*`); además `POST films/<serie>/episodes/<cap>/scenes/import` `{episode, scene, as?, script?}` devuelve la escena, sus planos y los elementos locales por añadir (no escribe nada). En un capítulo, las operaciones de biblioteca (`library/import|duplicate|remove|set|prop`) actúan sobre la biblioteca de la serie. Series: `POST series` (crear), `GET|POST series/<id>` (título, notas, biblia, capítulos), `GET series/<id>/library?q=&kind=&used=&episode=&limit=&offset=`, `GET series/<id>/usage?kind=&id=`, `GET series/<id>/importable`, `GET series/<id>/pose|setframe`, `POST series/<id>/library/<op>`, `POST series/<id>/upload` (capas y hojas), `POST series/<id>/episodes` (crear) y `POST series/<id>/episodes/<cap>/duplicate|rename|delete` (`delete` exige `confirm` igual al id).

App: el selector de proyecto agrupa «Series» y «Películas». Dentro de una serie aparece el selector de capítulo y dos vistas: **Capítulos** (crear, abrir, duplicar, renombrar, borrar con confirmación; título, notas y biblia de la serie) y **Biblioteca de la serie** (búsqueda, filtros por tipo, uso y capítulo, miniaturas, capítulos que usan cada elemento, duplicar, quitar si no se usa, importar de otras series o películas). Las demás vistas (referencias, guion, personajes, escenarios, escenas, planos, render) trabajan sobre el capítulo abierto; los cambios de biblioteca se guardan en la serie. La vista Escenas permite importar o duplicar una escena de otro capítulo.

## Referencias

`references` (lista, hoy vacía) está reservada para imágenes o notas de referencia; el motor y el compilador la ignoran.

## Guion (`script.json`)

Campos de primer nivel: `schema_version` (2), `kind` ("script"), `id`, `title`, `revision` (la sube `save()`), `fps`, `width`,
`height`, `story` (texto libre), `style` (`hold`, `contour`, `boil`, `boil_hold`: dibujo a pasos, grosor de línea, temblor), `bible`
(estilo, historia, continuidad), `characters` (id -> ruta), `sets` (nombre -> ruta), `props`, `references`, `scenes` (opcional), `shots`.

Cada plano:

```json
{"id": "s01", "duration": 6.0, "set": "valley", "description": "...",
 "actors": [{"id": "luma", "character": "luma", "start": {"x": -60, "y": 690, "scale": 0.66, "look_x": 0.55}}],
 "props":  [{"id": "butterfly", "prop": "butterfly", "spec": {"anchor": {"actor": "pip", "point": "tip_antenna"}}}],
 "actions": [
   {"on": "shot",  "do": "cam",  "t": 0, "x": 612, "y": 388, "zoom": 1.04},
   {"on": "luma",  "do": "walk", "t0": 0.7, "t1": 7.4, "x0": -70, "x1": 482, "scale": 0.66, "step": 56, "lift": 14},
   {"on": "butterfly", "do": "path", "t0": 3.0, "t1": 6.6, "points": [[400, 330], [520, 440]], "flutter": 6, "seed": 1.3}]}
```

- `duration` en segundos (se redondea a fotogramas). `set` es una clave de `sets` (un plano de una escena no lleva `set`: usa el de la escena).
- `actors[].start`: valores de canal en t=0. Los canales válidos son los de la tabla de abajo (`catalogue()["channels"]`).
- Los ids de actores y utilería son únicos dentro del plano; `shot` está reservado.
- `actions` es **una lista ordenada** por plano: el orden importa porque algunos verbos leen lo escrito antes (`to` parte del valor actual,
  `track` lee la trayectoria de la utilería, `pulse` vuelve al valor previo).
- `on` es `"shot"`, un actor o una utilería; `do` es el verbo; el resto de claves son argumentos con nombre. Los verbos con
  `*args` (`blink`) reciben una lista: `{"on": "pip", "do": "blink", "times": [3.8, 4.05]}`.
- Los verbos con "+ canales" aceptan además cualquier canal del personaje como argumento (`{"do": "to", "t": 1, "dur": 0.3, "lean": 5, "head_rot": -3}`).
  Un valor de texto (`"open"`, `"point"`) se aplica de golpe.
- Las curvas válidas (`ease`) y las expresiones (`face`) salen de `catalogue()["eases"]` y `catalogue()["expressions"]`.

Canales de personaje: posición/escala (`x`, `y`, `scale`, `facing`, `lift`), cuerpo (`hip_dx`, `hip_dy`, `lean`, `bend`, `body_yaw`,
`torso_sx/sy`), cabeza (`head_rot`, `head_dx/dy`, `face_x/y`, `look_x/y`), cara (`smile`, `mouth_open`, `mouth_w`, `mouth_round`,
`brow_y`, `brow_rot`, `eye_open`, `squint`, `lid`, `pupil`, `blush`), brazos (`arm_l_x/y`, `arm_r_x/y`, `arm_*_bend`, `hand_*_rot`,
`hand_l`, `hand_r`, `shoulder_*_dy`), piernas (`foot_*_x/y/rot/roll`, `knee`), `life` (respiración), `opacity`, `shadow`. Los `arm_*_x/y` y
`foot_*_x` parten de valores derivados del rig (alcance del brazo, separación de los pies).

### Verbos

Parámetros con `=valor` son opcionales (valor por defecto); `*` indica lista de valores. Tabla generada con `project.catalogue()`
(las descripciones están escritas a mano). Si se añaden verbos, hay que volver a generar la columna de parámetros con esa función.

| Destino | Verbo | Parámetros | Qué hace |
|---|---|---|---|
| actor | `auto_blink` | enabled=true | Activa o desactiva el parpadeo automático |
| actor | `blink` | times* | Parpadeos en los instantes dados |
| actor | `face` | t, name, dur=0.22, ease="soft" + canales | Pasa a una expresión de `EXPRESSIONS`; los canales extra la retocan |
| actor | `gasp` | t, amount=1.0 | Inhalación brusca |
| actor | `hop` | t, height=22, air=0.34, squash=1.0 | Salto con anticipación y aterrizaje (aterriza en t+0.19+air) |
| actor | `key` | t, channel, value, ease="smooth" | Fotograma clave directo en un canal |
| actor | `laugh` | t, dur=1.4, beats=5, strength=1.0 | Rebote de hombros y torso al reír |
| actor | `look` | t, x, y=0.0, dur=0.1, head=0.0 | Mirada (-1..1); `head` arrastra la cabeza |
| actor | `look_at` | t, target, x, facing, dur=0.1, head=0.45 | Mira a un punto del mundo `[x, y]` desde la posición `x` |
| actor | `nod` | t, count=2, depth=9, period=0.34 | Asentir |
| actor | `pulse` | t, up=0.15, hold=0.1, down=0.3, ease="out", back="inout" + canales | Va a los valores y vuelve al previo |
| actor | `set` | t + canales | Valores de golpe (sin interpolar) |
| actor | `to` | t, dur=0.4, ease="inout", overlap=1.0 + canales | Mantiene el valor hasta t y llega al destino tras `dur` (con retardo por familia) |
| actor | `track` | prop, t0, t1, x, facing, step=0.14, head=0.5 | Ojos y cabeza siguen una utilería (su id) |
| actor | `turn_around` | t, facing | Giro pasando por el frente y cambio de `facing` |
| actor | `walk` | t0, t1, x0, x1, scale=1.0, step=46, duty=0.6, lift=15, swing=17, ease=0.22, phase=0.0, bob=2.6, lean=4.0, strike=16, push=34, drop=5.0 | Caminata con pies plantados de x0 a x1 |
| actor | `wave` | t, side="l", cycles=3, period=0.36, out=-78, up=-50 | Saludo con el brazo `l` o `r` |
| prop | `flap` | t0, t1, rate=9.0, frames=[0, 1, 2, 1] | Ciclo de alas por fotogramas de la hoja |
| prop | `key` | t, channel, value, ease="smooth" | Fotograma clave en un canal |
| prop | `path` | t0, t1, points, flutter=5.0, seed=0.0, facing=true | Vuelo por puntos del mundo (Catmull-Rom) con aleteo |
| prop | `perch` | t0, t1, period=1.5 | Respiración lenta de alas en reposo |
| prop | `to` | t, dur, ease="inout" + canales | Interpola canales de la utilería |
| shot | `cam` | t, x=null, y=null, zoom=null, ease="inout" + extras | Clave de cámara (`x`, `y`, `zoom` y extras como `shake`) |
| shot | `dof` | value | Profundidad de campo: número o claves `[[t, valor, ease?], ...]` |
| shot | `fade_in` | dur=0.6, color="#000000" | Entrada desde color |
| shot | `fade_out` | dur=0.8, color="#000000" | Salida a color |
| shot | `overlay` | + extras | Capa gráfica libre (`kind`: `fade`, `title`...) con sus claves |
| shot | `puff_burst` | t, x, y, direction=-1, count=3, spread=30, size=1.0 | Nubecillas de polvo (requiere el prop `puff`) |

## Validación

`check()` devuelve errores con ruta (también de escenas, ver arriba) para: verbo o destino desconocido, personaje/escenario/prop inexistente, archivo o imagen que falta,
argumento obligatorio ausente o inesperado, tiempo que no es número, curva o expresión desconocida, ids duplicados y canales
desconocidos (en `start`, en `key` y en los argumentos de `set`/`to`/`pulse`/`face`).

## Aplicación

`python -m celstudio serve --open` (o `ABRIR_CEL_STUDIO.cmd`) abre el estudio v2 en `http://127.0.0.1:8768/`.
Cada carpeta `projects/<id>/` con un `script.json` (película) o un `series.json` (serie, ver «Series y capítulos») aparece en el selector. La lógica está en `celstudio/v2/api.py` (rutas `/api/v2/films/...`; biblioteca: `POST films`, `GET <id>/importable`, `POST <id>/library/{import,duplicate,remove,set,prop}`, `GET <id>/setframe`; `POST <id>/upload` acepta `category` `set_layer` o `prop_sheet` para capas y hojas).

| Vista | Qué edita | Dónde escribe |
|---|---|---|
| (barra lateral) | Selector de película y «＋ Nueva película» | `projects/<id>/` nuevo con `script.json` mínimo |
| Referencias | Sube imágenes o texto (estilo, personaje, escenario, guion) y sus notas; quitar una referencia sólo la saca de la lista | `refs/` y `references` de `script.json` (la subida guarda al instante) |
| Guion | `title`, `story`, `bible`, `style` (fps y tamaño son de sólo lectura) | `script.json` (botón Guardar o Ctrl+S) |
| Personajes | Importar de otra película, duplicar, quitar; dónde se usa cada uno; vistas de pose, colores, proporciones y JSON del rig | `characters/<id>.json` (copia `<id>.previous.json`), recompila `film.json`; importar, duplicar y quitar guardan al instante la biblioteca en `script.json` |
| Escenarios y utilería | Escenario vacío, importar, duplicar, quitar; capas (subir, reordenar, quitar), luces, partículas, `light`, `post`; biblioteca `props` (crear con hoja, importar, duplicar, quitar) | `sets/<id>.json` (con `.previous.json`); `props` en `script.json`; capas en `assets/sets/<id>/` |
| Escenas | Crear, duplicar, eliminar (si ningún plano la usa) y reordenar escenas; por escena: id, título, descripción, escenario con vista previa, reparto (instancias, `start` por defecto) y utilería | `script.json` (`scenes`; guardar valida y recompila) |
| Planos | Lista con la escena de cada plano y filtro por escena; «＋ Nuevo» crea dentro de la escena filtrada; quién del reparto aparece (casilla + `start` propio; al desmarcar un actor con acciones se avisa y se borran); tabla ordenada de acciones (destinos: el plano, sus actores y su utilería); vista previa del guion sin guardar | `script.json` (guardar valida, sube `revision`, copia `script.previous.json` y recompila `film.json`) |
| Render | Película completa o un plano, con ancho elegido; progreso, cancelar y reproductor | `renders/<idtrabajo>-<plano|pelicula>.mp4` (nunca sobrescribe) |

Guardar con una `revision` antigua devuelve un conflicto; guardar un guion con errores devuelve la ruta del primer error. El render usa el guion guardado.
