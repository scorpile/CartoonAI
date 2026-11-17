#!/bin/bash
cd /c/Proyectos/CartoonAI/work/osos/art/bears
for b in osito mama_osa papa_oso; do for p in heads body hands; do ./run_codex.sh $b $p & done; done
wait
