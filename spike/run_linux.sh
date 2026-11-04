#!/usr/bin/env bash
# Replay all operational pairs under Linux, then summarise. Needs no API keys.
set -u
E="/mnt/c/Users/chira/Downloads/AI safety challange"
cd "$HOME/agentabstain-spike" || exit 1
PYTHONUTF8=1 .venv/bin/python "$E/spike/run_spike.py" "$E/evidence/spike_all131_linux.json" 100 > all131.log 2>&1
echo "replay exit $?"
.venv/bin/python "$E/spike/summarise.py" "$E/evidence/spike_all131_linux.json"
