> Spanish: [docs/INSTALACION.md](../INSTALACION.md) · Back to [README](../../README.md)

# Installation and agent setup

## Requirements

- **Python 3.10 or newer.** Developed and tested on 3.13. (The core needs `numpy>=2`, which needs 3.9+; the optional MCP server needs the `mcp` package, which needs 3.10+.)
- **FFmpeg** on your `PATH`, only to render MP4 videos (frames, contact sheets and the web studio preview work without it).
- Windows, macOS or Linux. CPU only, no GPU needed.

Install FFmpeg:

| OS | Command |
|---|---|
| Windows | `winget install Gyan.FFmpeg` (or `choco install ffmpeg`), then open a new terminal |
| macOS | `brew install ffmpeg` |
| Debian / Ubuntu | `sudo apt install ffmpeg` |
| Fedora | `sudo dnf install ffmpeg` (needs RPM Fusion) |

Check with `ffmpeg -version`.

## Install

```bash
git clone https://github.com/scorpile/CartoonAI.git
cd CartoonAI

# optional but recommended: a virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

python -m pip install -r requirements.txt        # Pillow, numpy, skia-python
python -m pip install -r requirements-mcp.txt    # optional: MCP server for AI agents
python -m pip install -r requirements-dev.txt    # optional: pytest + scipy (tests, art-prep scripts)
```

The core install does **not** need `mcp`. If you use a virtual environment, agents must start the server with that environment's Python (see below).

## Run the web studio

```bash
python -m celstudio serve --open        # http://127.0.0.1:8768/  (--port N if busy)
```

On Windows you can double-click `ABRIR_CEL_STUDIO.cmd`. The server listens on `127.0.0.1` only. The interface is available in English and Spanish (selector in the header). The demos in `projects/` (`taller-v3`, `tres-osos`) ship with their art, so you can open and render them right away.

## Run the tests

```bash
python -m pytest tests -q
```

`tests/test_mcp.py` is skipped if `mcp` is not installed; video render tests need FFmpeg.

## Agent setup (MCP server and skill)

The MCP server `cel-studio` lets any MCP client read and edit scripts, look at frames and start renders, without going through the web studio. It runs over **stdio**:

```bash
python -m celstudio.mcp [--projects DIR] [--lang es|en]
```

- `--projects DIR` (or the environment variable `CELSTUDIO_PROJECTS`): the projects root. Default: `projects/` of the repository. Every path an agent can reach stays inside it.
- `--lang`: language of error messages, `en` (default) or `es`.
- It makes no network calls and calls no LLM.

Tools: `list_projects`, `get_series`, `list_episodes`, `create_series`, `create_episode`, `get_script`, `check_script`, `save_script`, `apply_actions`, `library`, `character_info`, `list_verbs`, `render_frame`, `contact_sheet`, `render_video`, `render_status`. Project ids are `"<film>"` for a standalone film and `"<series>/<episode>"` for an episode.

`save_script` and `apply_actions` check the script revision, so an agent cannot overwrite what a person saved from the web studio in the meantime. `render_video` runs in the background and returns a job id; poll `render_status`. Use absolute paths in the configs below, and `python3` instead of `python` if that is what your system calls it (or the full path to the virtual environment's Python).

### Claude Code

Add it for your user:

```bash
claude mcp add cel-studio -e PYTHONPATH=/absolute/path/to/CartoonAI -- python -m celstudio.mcp --projects /absolute/path/to/CartoonAI/projects
```

`PYTHONPATH` lets the server find the `celstudio` package from any directory (the project is not a pip package). Or add it at project scope: the repository already contains an `.mcp.json` at its root, used when you start Claude Code inside the repository:

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

Open Claude Code inside the repository and approve the server when asked. It requires `pip install -r requirements-mcp.txt`. Check with `/mcp` or `claude mcp list`.

Skill: make the workflow available by linking or copying the folder `skills/cartoon-production` (its `SKILL.md` links to the docs, so a link works better than a copy):

```bash
# inside the repository (project skill)
mkdir -p .claude/skills && ln -s ../../skills/cartoon-production .claude/skills/cartoon-production
# or for all your projects
ln -s "$(pwd)/skills/cartoon-production" ~/.claude/skills/cartoon-production
```

On Windows PowerShell: `New-Item -ItemType Junction -Path "$HOME\.claude\skills\cartoon-production" -Target "<repo>\skills\cartoon-production"`. A Spanish version is in `SKILL.es.md`.

### Codex CLI

```bash
codex mcp add cel-studio --env PYTHONPATH=/absolute/path/to/CartoonAI -- python -m celstudio.mcp --projects /absolute/path/to/CartoonAI/projects
```

or edit `~/.codex/config.toml`:

```toml
[mcp_servers.cel-studio]
command = "python"
args = ["-m", "celstudio.mcp", "--projects", "/absolute/path/to/CartoonAI/projects"]
env = { PYTHONPATH = "/absolute/path/to/CartoonAI" }
```

Codex reads `AGENTS.md` at the repository root, which already points to `skills/cartoon-production/SKILL.md`. Skills for other agents can simply be read from that path.

### Claude Desktop

Edit `claude_desktop_config.json` (Settings, Developer, Edit Config; on Windows `%APPDATA%\Claude\`, on macOS `~/Library/Application Support/Claude/`) and restart the app:

```json
{
  "mcpServers": {
    "cel-studio": {
      "command": "python",
      "args": ["-m", "celstudio.mcp", "--projects", "/absolute/path/to/CartoonAI/projects"],
      "env": { "PYTHONPATH": "/absolute/path/to/CartoonAI" }
    }
  }
}
```

If `python` is not found by the app, use the full path of the interpreter (for a virtual environment: `/absolute/path/to/CartoonAI/.venv/bin/python`, on Windows `...\.venv\Scripts\python.exe`). On Windows, write backslashes doubled in JSON.

### Any other MCP client

Start `python -m celstudio.mcp --projects <dir>` as a stdio server from the repository root (or with `PYTHONPATH` set to it) and speak MCP over its stdin/stdout. Nothing else is written to stdout. `work/mcp_smoke.py` is a small client that does `initialize`, `tools/list` and a few calls.

## Generating new art (optional)

Cel Studio does not generate images itself. The art in `projects/` was made once per resource with an image model (OpenAI Codex `image_gen`; the prompts are in `work/v3/art` and `work/osos/art`) and then cut and measured by scripts. To make **new** characters, sets or props you need an image model or your own drawings, plus the preparation scripts in `work/`. To edit, direct and render with the existing art (the demos, or any series that already has a library) you need none of that. See [ENGINE.md](ENGINE.md) and [FORMAT.md](FORMAT.md).
