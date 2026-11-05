#!/usr/bin/env bash
E="${HOLDPOINT_REPO:-$PWD}"   # run from the repo root
cd "${AGENTABSTAIN_DIR:-$HOME/agentabstain}" || exit 1
PYTHONUTF8=1 .venv-era/bin/python "$E/bench/harness_check.py" 2>&1 | grep -v "Starting MCP\|with transport" | tail -25
echo "harness check exit ${PIPESTATUS[0]}"
