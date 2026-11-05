#!/usr/bin/env bash
cd "$HOME/agentabstain-spike" || exit 1
echo "user: $(id -un)"
echo "node: $(command -v node) $(node --version 2>/dev/null)"
echo "npm: $(command -v npm)"
echo "claude cli: $(command -v claude) $(claude --version 2>/dev/null)"
grep -iE "^claude" "/mnt/c/Users/chira/Downloads/AI safety challange/bench/requirements.era.lock"
S=.venv-era/lib/python3.11/site-packages/claude_code_sdk
grep -n "which\|node_modules\|CLINotFound\|npm install" "$S/_internal/transport/subprocess_cli.py" | head -12 | cut -c1-140
echo "--- runner"
grep -n "add_argument\|results_root\|results/" eval/runner.py | head -20 | cut -c1-140
grep -n "provider" abstention_factory/src/utils/call_llm.py | head -10 | cut -c1-140
grep -n "provider\|judge_models\|results" eval/config.py | head -12 | cut -c1-140
