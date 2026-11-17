# Contributing / Contribuir

[English](#english) · [Español](#español)

---

## English

Thanks for helping. Cel Studio is alpha software and contributions of any size are welcome: bug fixes, new verbs, docs, tests, translations, art-pipeline tools.

### Set up

```bash
git clone https://github.com/scorpile/CartoonAI.git
cd CartoonAI
python -m pip install -r requirements-dev.txt    # runtime deps + pytest + scipy (for the art-prep scripts)
```

You also need [FFmpeg](https://ffmpeg.org/) on your `PATH` to render videos. Run the studio with `python -m celstudio serve --open`. Full setup: [docs/en/INSTALL.md](docs/en/INSTALL.md). For the MCP server (`celstudio/mcp_server.py`) also run `python -m pip install -r requirements-mcp.txt`; `tests/test_mcp.py` is skipped without it. A new tool must reuse `project.py` / `api.py` (no duplicated logic), stay inside the projects root and make no network or LLM calls.

### Run the tests

```bash
python -m pytest tests -q
```

Please run them before opening a PR, and add a test for anything you fix or add.

### Rules of the project

- **The renderer stays deterministic.** A frame is a pure function of `(film, shot, time)`. No LLM calls, no network, no model inference and no unseeded randomness in the render path (`celstudio/v2/stage.py`, `puppet.py`, `gfx.py`, `fx.py`). Noise such as line boil or flutter must be seeded from the data.
- **Art is generated per resource, never per frame.** New characters, parts, hands, set layers and props come from an image model (or any other source) once, are stored under `projects/<id>/assets/`, and are then cut and measured by scripts. Keep the prompts next to the result (see `work/v3/art` and `work/osos/art`).
- **The script is the source of truth.** `script.json` is data, `film.json` is compiled output. A new verb must be added to the Python layer (`direct.py` / the catalogue in `project.py`) so that `check()` validates it with a path, and documented in `docs/FORMATO_V2.md` and `docs/en/FORMAT.md`.
- **If the catalogue cannot do something, say what is missing** (art, pose, rig or clip) instead of faking it with repeated cycles.
- **Passing tests is not artistic quality.** For visual changes, attach a contact sheet (`python -m celstudio.v2 sheet ...`) or a motion strip before/after.
- Do not commit rendered videos (they are release assets), credentials or personal data.

### Style of changes

- Small, focused pull requests. One idea per PR.
- Match the surrounding code style; keep the engine free of heavy dependencies.
- User-facing strings of the web studio and API messages go through the i18n dictionaries (`celstudio/v2/i18n.py`, `web/`), with both Spanish and English entries.
- Docs are bilingual: if you change a doc that has an English and a Spanish version, update both, or say in the PR which one still needs translating.

### Issues and pull requests

1. Open an issue first for large changes or new features, so we can agree on the approach.
2. For bugs include: what you ran (command or script), what you expected, what happened, your OS and Python version, and a minimal `script.json` or a frame if it is visual.
3. Fork, create a branch, make the change, run the tests, open a PR describing what and why, and link the issue.

### Good first issues

- Add an acting verb in `celstudio/v2/direct.py` (anticipation, double-take, shiver...) with a test.
- Add an interface language (new dictionary) or improve the English wording.
- Add tests: determinism of a frame across runs, validation errors with the right path, series operations.
- Improve error messages from `check()`.
- Write a tutorial: "make your first 10-second episode".
- Tools for the art pipeline: automatic checks of generated sheets (size, transparent background, missing parts), prompt templates.

Bigger projects: back views and mouth charts, audio / lip-sync, GPU rendering, a timeline editor in the web studio, rigs for non-biped characters.

---

## Español

Gracias por ayudar. Cel Studio es software alfa y se agradecen contribuciones de cualquier tamaño: correcciones, verbos nuevos, documentación, pruebas, traducciones, herramientas para la cadena de arte.

### Preparar el entorno

```bash
git clone https://github.com/scorpile/CartoonAI.git
cd CartoonAI
python -m pip install -r requirements-dev.txt    # dependencias + pytest + scipy (para los scripts de preparación de arte)
```

También necesitas [FFmpeg](https://ffmpeg.org/) en el `PATH` para renderizar videos. Abre el estudio con `python -m celstudio serve --open`. Instalación completa: [docs/INSTALACION.md](docs/INSTALACION.md). Para el servidor MCP (`celstudio/mcp_server.py`) ejecuta también `python -m pip install -r requirements-mcp.txt`; `tests/test_mcp.py` se omite sin él. Una herramienta nueva debe reutilizar `project.py` / `api.py` (sin duplicar lógica), quedarse dentro de la carpeta de proyectos y no hacer llamadas de red ni a un LLM.

### Ejecutar las pruebas

```bash
python -m pytest tests -q
```

Ejecútalas antes de abrir un PR y añade una prueba por cada cosa que corrijas o agregues.

### Reglas del proyecto

- **El renderizador sigue siendo determinista.** Un fotograma es una función pura de `(film, plano, tiempo)`. Nada de llamadas a un LLM, red, inferencia de modelos ni aleatoriedad sin semilla en el camino de render (`celstudio/v2/stage.py`, `puppet.py`, `gfx.py`, `fx.py`). El ruido (vibración de línea, aleteo) debe salir de una semilla guardada en los datos.
- **El arte se genera por recurso, nunca por fotograma.** Personajes, piezas, manos, capas de escenario y utilería nuevos se obtienen una vez de un modelo de imágenes (o de otra fuente), se guardan en `projects/<id>/assets/` y los scripts los recortan y miden. Guarda los prompts junto al resultado (ver `work/v3/art` y `work/osos/art`).
- **El guion es la fuente de verdad.** `script.json` son datos y `film.json` es salida compilada. Un verbo nuevo debe añadirse en la capa de Python (`direct.py` / el catálogo de `project.py`) para que `check()` lo valide con ruta, y documentarse en `docs/FORMATO_V2.md` y `docs/en/FORMAT.md`.
- **Si el catálogo no permite algo, di qué falta** (arte, pose, rig o clip) en lugar de disimularlo con ciclos repetidos.
- **Pasar las pruebas no es calidad artística.** En cambios visuales adjunta una hoja de contacto (`python -m celstudio.v2 sheet ...`) o una tira de movimiento antes/después.
- No subas videos renderizados (son archivos de release), credenciales ni datos personales.

### Estilo de los cambios

- Pull requests pequeños y centrados: una idea por PR.
- Sigue el estilo del código cercano; mantén el motor sin dependencias pesadas.
- Los textos de la interfaz web y los mensajes de la API pasan por los diccionarios de i18n (`celstudio/v2/i18n.py`, `web/`), con entradas en español y en inglés.
- La documentación es bilingüe: si cambias un documento con versión en inglés y en español, actualiza ambas, o indica en el PR cuál falta por traducir.

### Issues y pull requests

1. Abre primero un issue para cambios grandes o funciones nuevas, para acordar el enfoque.
2. En los errores incluye: qué ejecutaste (comando o script), qué esperabas, qué pasó, tu sistema operativo y versión de Python, y un `script.json` mínimo o un fotograma si es visual.
3. Haz un fork, crea una rama, haz el cambio, ejecuta las pruebas, abre un PR que explique qué y por qué, y enlaza el issue.

### Buenas primeras tareas

- Añadir un verbo de actuación en `celstudio/v2/direct.py` (anticipación, doble toma, escalofrío...) con su prueba.
- Añadir un idioma de interfaz (nuevo diccionario) o mejorar la redacción en inglés.
- Añadir pruebas: determinismo de un fotograma entre ejecuciones, errores de validación con la ruta correcta, operaciones de series.
- Mejorar los mensajes de error de `check()`.
- Escribir un tutorial: «haz tu primer capítulo de 10 segundos».
- Herramientas para la cadena de arte: comprobaciones automáticas de las hojas generadas (tamaño, fondo transparente, piezas que faltan), plantillas de prompts.

Proyectos mayores: vistas de espalda y cartas de bocas, audio / lip-sync, render por GPU, editor de línea de tiempo en el estudio web, rigs para personajes no bípedos.
