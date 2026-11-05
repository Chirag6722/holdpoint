#!/usr/bin/env bash
set -u
E="/mnt/c/Users/chira/Downloads/AI safety challange"
cd "$HOME/agentabstain-spike" || exit 1
set -a; . ./.env; set +a
PYTHONUTF8=1 .venv-era/bin/python "$E/bench/injection_suite.py" "$E/evidence/injection_suite.json"
echo "exit $?"
