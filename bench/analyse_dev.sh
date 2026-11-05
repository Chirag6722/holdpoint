#!/usr/bin/env bash
E="/mnt/c/Users/chira/Downloads/AI safety challange"
cd "$HOME/agentabstain-spike" || exit 1
PYTHONUTF8=1 .venv-era/bin/python "$E/bench/analyse_dev.py" "$E/evidence/dev_run.csv" runs/gated
