#!/usr/bin/env bash
E="/mnt/c/Users/chira/Downloads/AI safety challange"
cd "$HOME/agentabstain-spike" || exit 1
PYTHONUTF8=1 .venv-era/bin/python "$E/bench/review_load.py" runs/heldout_gated "$E/evidence/heldout_review_load.json"
