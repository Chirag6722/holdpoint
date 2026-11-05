#!/usr/bin/env bash
# Development split, baseline then gated, with cost guards. Never prints the key.
set -u
E="${HOLDPOINT_REPO:-$PWD}"   # run from the repo root
cd "${AGENTABSTAIN_DIR:-$HOME/agentabstain}" || exit 1
PY=.venv-era/bin/python
MODEL=claude-haiku-4-5
BASELINE_AGENT_LIMIT=8.00
export PYTHONUTF8=1 HOLDPOINT_AGENT_BACKEND=anthropic HOLDPOINT_RUNS_DIR=runs/gated
set -a; . ./.env; set +a
TASKS="$E/bench/tasks_dev.yaml"

report() { $PY "$E/bench/report.py" "$E/evidence/dev_run" "$@" --model $MODEL --tasks "$TASKS"; }

echo "== baseline $(date +%T)"
$PY "$E/bench/run_gated.py" baseline --runtime-config "$E/bench/configs/baseline_claude_haiku.yaml" --task-config "$TASKS" --workers 3 > dev_baseline.log 2>&1
echo "inference exit $?"
$PY -m eval.runner --provider openaisdk --model $MODEL --results-root results_baseline --judge-config "$E/bench/configs/judge_claude.yaml" --workers 3 >> dev_baseline.log 2>&1
echo "eval exit $?"
report baseline=results_baseline > /dev/null
COST=$($PY -c "import json;print(json.load(open('$E/evidence/dev_run.summary.json'))['baseline']['agent_cost_usd'])")
echo "baseline agent cost: \$$COST"
if ! $PY -c "import sys;sys.exit(0 if $COST <= $BASELINE_AGENT_LIMIT else 1)"; then
  echo "STOPPED: baseline cost above \$$BASELINE_AGENT_LIMIT"; exit 3
fi

echo "== reviewer check $(date +%T)"
if ! PYTHONPATH="$E" $PY -c "
from holdpoint.reviewer import reviewer_from_env
r = reviewer_from_env()
print(type(r).__name__, r('Pay Ann 10 from account 1.', 'send_payment', {'to': 'Ann', 'amount': 10}, []), r.last_usage)
"; then
  echo "STOPPED: reviewer call failed, gated run not started"; exit 4
fi

echo "== gated $(date +%T)"
$PY "$E/bench/run_gated.py" gated --runtime-config "$E/bench/configs/gated_claude_haiku.yaml" --task-config "$TASKS" --workers 3 > dev_gated.log 2>&1
echo "inference exit $?"
$PY -m eval.runner --provider openaisdk --model $MODEL --results-root results_gated --judge-config "$E/bench/configs/judge_claude.yaml" --workers 3 >> dev_gated.log 2>&1
echo "eval exit $?"
report baseline=results_baseline gated=results_gated
echo "== done $(date +%T)"
