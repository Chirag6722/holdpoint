#!/usr/bin/env bash
E="/mnt/c/Users/chira/Downloads/AI safety challange"
cd "$HOME/agentabstain-spike" || exit 1
PYTHONUTF8=1 .venv/bin/python "$E/bench/harness_check.py" 2>&1 | grep -v "Starting MCP\|with transport" | tail -25
echo "harness check exit ${PIPESTATUS[0]}"
