#!/bin/bash
# usage: run_codex.sh <prompt.md> <ref1> [ref2]
# Codex desktop binary: set CODEX_BIN, or the first codex.exe under %LOCALAPPDATA%\OpenAI\Codex\bin is used
CX="${CODEX_BIN:-$(ls "$LOCALAPPDATA"/OpenAI/Codex/bin/*/codex.exe 2>/dev/null | head -1)}"
P="$1"; OUT="${P%.md}.result.txt"; LOG="${P%.md}.log"
"$CX" exec --skip-git-repo-check -s workspace-write -C 'c:\Proyectos\CartoonAI' -i 'projects/taller-v3/assets/set/main.png' -i 'projects/taller-v3/source/valley-studio.png' -o "$OUT" - < "$P" > "$LOG" 2>&1
