#!/usr/bin/env bash
E="/mnt/c/Users/chira/Downloads/AI safety challange"
cd "$HOME/agentabstain-spike" || exit 1
PYTHONUTF8=1 .venv-era/bin/python "$E/bench/harness_check.py" > harness_era.log 2>&1
echo "harness check exit $?"
grep -nE "harness ok|Error|error:|HELD|assert" harness_era.log | cut -c1-220 | head -30
wc -l harness_era.log
