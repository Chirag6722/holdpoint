#!/usr/bin/env bash
# Rebuild the environment as of the benchmark's release, since its requirements are unpinned
# and later mcp and fastmcp major versions break the harnesses' score export.
set -u
E="/mnt/c/Users/chira/Downloads/AI safety challange"
ERA_DATE="2026-07-17"
cd "$HOME/agentabstain-spike" || exit 1
export PATH="$HOME/.local/bin:$PATH"
uv venv -q --python 3.11 .venv-era
uv pip install -q --python .venv-era/bin/python --exclude-newer "$ERA_DATE" -r requirements.txt pytest 2>&1 | tail -5
uv pip freeze --python .venv-era/bin/python | tr -d '\r' > "$E/bench/requirements.era.lock"
grep -iE "^(fastmcp|mcp|openai-agents|google-adk|google-genai|openai)==" "$E/bench/requirements.era.lock"
echo "--- bypass suite in era environment"
cd "$E" && PYTHONPATH="$E" PYTHONUTF8=1 "$HOME/agentabstain-spike/.venv-era/bin/python" -m pytest -q -p no:cacheprovider tests/test_bypass.py 2>&1 | tail -12
echo "--- harness check in era environment"
cd "$HOME/agentabstain-spike" && PYTHONUTF8=1 .venv-era/bin/python "$E/bench/harness_check.py" 2>&1 | grep -v "Starting MCP\|with transport" | tail -14
echo "harness check exit ${PIPESTATUS[0]}"
