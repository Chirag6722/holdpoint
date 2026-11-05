#!/usr/bin/env bash
E="/mnt/c/Users/chira/Downloads/AI safety challange"
cd "$HOME/agentabstain-spike" || exit 1
PYTHONUTF8=1 .venv-era/bin/python "$E/bench/inspect_runs.py"
echo "=== stderr markers in gated log"
grep -nE "Traceback|Error:|error:" first_gated.log | tail -6 | cut -c1-200
