#!/bin/bash
# usage: run_codex.sh <bear> <part>
cd /c/Proyectos/CartoonAI/work/osos/art/bears
CX="${CODEX_BIN:-$(ls "$LOCALAPPDATA"/OpenAI/Codex/bin/*/codex.exe 2>/dev/null | head -1)}"
"$CX" exec --skip-git-repo-check -s workspace-write -C 'c:\Proyectos\CartoonAI\work\osos\art\bears' -i "c:\Proyectos\CartoonAI\work\osos\art\bears\$1-model.png" -i 'c:\Proyectos\CartoonAI\projects\taller-v3\source\luma-sheet.png' -o $1-$2-result.txt - < $1-$2-prompt.md > $1-$2.log 2>&1
