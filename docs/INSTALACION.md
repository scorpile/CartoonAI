> English: [docs/en/INSTALL.md](en/INSTALL.md) · Volver al [README](../README.es.md)

# Instalación y configuración de agentes

## Requisitos

- **Python 3.10 o superior.** Desarrollado y probado con 3.13. (El núcleo necesita `numpy>=2`, que pide 3.9+; el servidor MCP opcional necesita el paquete `mcp`, que pide 3.10+.)
- **FFmpeg** en el `PATH`, solo para renderizar videos MP4 (los fotogramas, las hojas de contacto y la vista previa del estudio web funcionan sin él).
- Windows, macOS o Linux. Solo CPU, no hace falta GPU.

Instalar FFmpeg:

| Sistema | Comando |
|---|---|
| Windows | `winget install Gyan.FFmpeg` (o `choco install ffmpeg`), luego abre una terminal nueva |
| macOS | `brew install ffmpeg` |
| Debian / Ubuntu | `sudo apt install ffmpeg` |
| Fedora | `sudo dnf install ffmpeg` (requiere RPM Fusion) |

Comprueba con `ffmpeg -version`.

## Instalar

```bash
git clone https://github.com/scorpile/CartoonAI.git
cd CartoonAI

# opcional pero recomendable: un entorno virtual
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

python -m pip install -r requirements.txt        # Pillow, numpy, skia-python
python -m pip install -r requirements-mcp.txt    # opcional: servidor MCP para agentes de IA
python -m pip install -r requirements-dev.txt    # opcional: pytest + scipy (pruebas, scripts de arte)
```

El núcleo **no** necesita `mcp`. Si usas un entorno virtual, los agentes deben lanzar el servidor con el Python de ese entorno (ver abajo).

## Abrir el estudio web

```bash
python -m celstudio serve --open        # http://127.0.0.1:8768/  (--port N si está ocupado)
```

En Windows puedes hacer doble clic en `ABRIR_CEL_STUDIO.cmd`. El servidor solo escucha en `127.0.0.1`. La interfaz está en español e inglés (selector en la cabecera). Las demos de `projects/` (`taller-v3`, `tres-osos`) traen su arte, así que puedes abrirlas y renderizarlas enseguida.

## Ejecutar las pruebas

```bash
python -m pytest tests -q
```

`tests/test_mcp.py` se omite si `mcp` no está instalado; las pruebas de render de video necesitan FFmpeg.

## Configurar agentes (servidor MCP y skill)

El servidor MCP `cel-studio` permite que cualquier cliente MCP lea y edite guiones, mire fotogramas y lance renders sin pasar por el estudio web. Funciona por **stdio**:

```bash
python -m celstudio.mcp [--projects DIR] [--lang es|en]
```

- `--projects DIR` (o la variable de entorno `CELSTUDIO_PROJECTS`): carpeta raíz de proyectos. Por defecto, `projects/` del repositorio. Toda ruta a la que llegue un agente queda dentro de ella.
- `--lang`: idioma de los mensajes de error, `en` (por defecto) o `es`.
- No hace llamadas de red ni usa ningún LLM.

Herramientas: `list_projects`, `get_series`, `list_episodes`, `create_series`, `create_episode`, `get_script`, `check_script`, `save_script`, `apply_actions`, `library`, `character_info`, `list_verbs`, `render_frame`, `contact_sheet`, `render_video`, `render_status`. El id de proyecto es `"<película>"` para una película suelta y `"<serie>/<capítulo>"` para un capítulo.

`save_script` y `apply_actions` comprueban la revisión del guion, así que un agente no puede pisar lo que una persona guardó desde el estudio web entretanto. `render_video` corre en segundo plano y devuelve un id de trabajo; consulta `render_status`. En las configuraciones de abajo usa rutas absolutas, y `python3` en lugar de `python` si así se llama en tu sistema (o la ruta completa al Python del entorno virtual).

### Claude Code

Para tu usuario:

```bash
claude mcp add cel-studio -e PYTHONPATH=/ruta/absoluta/a/CartoonAI -- python -m celstudio.mcp --projects /ruta/absoluta/a/CartoonAI/projects
```

`PYTHONPATH` permite que el servidor encuentre el paquete `celstudio` desde cualquier carpeta (el proyecto no es un paquete de pip). O bien a nivel de proyecto: el repositorio ya trae un `.mcp.json` en su raíz, que se usa al abrir Claude Code dentro del repositorio:

```json
{
  "mcpServers": {
    "cel-studio": {
      "command": "python",
      "args": ["-m", "celstudio.mcp"]
    }
  }
}
```

Abre Claude Code dentro del repositorio y aprueba el servidor cuando lo pida. Requiere `pip install -r requirements-mcp.txt`. Comprueba con `/mcp` o `claude mcp list`.

Skill: para tener el flujo de trabajo disponible, enlaza o copia la carpeta `skills/cartoon-production` (su `SKILL.md` enlaza a la documentación, por eso un enlace va mejor que una copia):

```bash
# dentro del repositorio (skill del proyecto)
mkdir -p .claude/skills && ln -s ../../skills/cartoon-production .claude/skills/cartoon-production
# o para todos tus proyectos
ln -s "$(pwd)/skills/cartoon-production" ~/.claude/skills/cartoon-production
```

En PowerShell de Windows: `New-Item -ItemType Junction -Path "$HOME\.claude\skills\cartoon-production" -Target "<repo>\skills\cartoon-production"`. Hay una versión en español en `SKILL.es.md`.

### Codex CLI

```bash
codex mcp add cel-studio --env PYTHONPATH=/ruta/absoluta/a/CartoonAI -- python -m celstudio.mcp --projects /ruta/absoluta/a/CartoonAI/projects
```

o edita `~/.codex/config.toml`:

```toml
[mcp_servers.cel-studio]
command = "python"
args = ["-m", "celstudio.mcp", "--projects", "/ruta/absoluta/a/CartoonAI/projects"]
env = { PYTHONPATH = "/ruta/absoluta/a/CartoonAI" }
```

Codex lee `AGENTS.md` en la raíz del repositorio, que ya apunta a `skills/cartoon-production/SKILL.md`. Otros agentes pueden leer la skill desde esa ruta.

### Claude Desktop

Edita `claude_desktop_config.json` (Ajustes, Desarrollador, Editar configuración; en Windows `%APPDATA%\Claude\`, en macOS `~/Library/Application Support/Claude/`) y reinicia la aplicación:

```json
{
  "mcpServers": {
    "cel-studio": {
      "command": "python",
      "args": ["-m", "celstudio.mcp", "--projects", "/ruta/absoluta/a/CartoonAI/projects"],
      "env": { "PYTHONPATH": "/ruta/absoluta/a/CartoonAI" }
    }
  }
}
```

Si la aplicación no encuentra `python`, usa la ruta completa del intérprete (en un entorno virtual: `/ruta/absoluta/a/CartoonAI/.venv/bin/python`, en Windows `...\.venv\Scripts\python.exe`). En Windows escribe las barras invertidas dobles en el JSON.

### Cualquier otro cliente MCP

Lanza `python -m celstudio.mcp --projects <carpeta>` como servidor stdio desde la raíz del repositorio (o con `PYTHONPATH` apuntando a ella) y habla MCP por su stdin/stdout. No se escribe nada más en stdout. `work/mcp_smoke.py` es un cliente pequeño que hace `initialize`, `tools/list` y algunas llamadas.

## Generar arte nuevo (opcional)

Cel Studio no genera imágenes por sí mismo. El arte de `projects/` se hizo una vez por recurso con un modelo de imágenes (OpenAI Codex `image_gen`; los prompts están en `work/v3/art` y `work/osos/art`) y luego unos scripts lo recortaron y midieron. Para crear personajes, escenarios o utilería **nuevos** necesitas un modelo de imágenes o tus propios dibujos, y los scripts de preparación de `work/`. Para editar, dirigir y renderizar con el arte existente (las demos, o cualquier serie que ya tenga biblioteca) no necesitas nada de eso. Ver [ESTUDIO_V3.md](ESTUDIO_V3.md) y [FORMATO_V2.md](FORMATO_V2.md).
