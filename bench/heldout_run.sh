#!/usr/bin/env bash
# The once-only held-out run. Refuses to start if results already exist.
set -u
E="${HOLDPOINT_REPO:-$PWD}"   # run from the repo root
cd "${AGENTABSTAIN_DIR:-$HOME/agentabstain}" || exit 1
PY=.venv-era/bin/python
MODEL=claude-haiku-4-5
AGENT_LIMIT=12.00
TASKS="$E/bench/tasks_held_out.yaml"
export PYTHONUTF8=1 HOLDPOINT_AGENT_BACKEND=anthropic HOLDPOINT_RUNS_DIR=runs/heldout_gated
set -a; . ./.env; set +a
if [ -e results_heldout_baseline ] || [ -e results_heldout_gated ]; then
  echo "STOPPED: held-out results already exist. This run happens once."; exit 5
fi
mkdir -p runs
for c in baseline gated; do
  CFG="runs/heldout_$c.yaml"
  sed "s#results_$c/#results_heldout_$c/#" "$E/bench/configs/${c}_claude_haiku.yaml" | tr -d '\r' > "$CFG"
  echo "== $c $(date +%T)"
  $PY "$E/bench/run_gated.py" $c --runtime-config "$CFG" --task-config "$TASKS" --workers 3 > "heldout_$c.log" 2>&1
  echo "inference exit $?"
  $PY -m eval.runner --provider openaisdk --model $MODEL --results-root "results_heldout_$c" --judge-config "$E/bench/configs/judge_claude.yaml" --workers 3 >> "heldout_$c.log" 2>&1
  echo "eval exit $?"
  $PY "$E/bench/report.py" "$E/evidence/heldout_$c" "$c=results_heldout_$c" --model $MODEL --tasks "$TASKS" --runs runs/heldout_gated > /dev/null
  COST=$($PY -c "import json;print(json.load(open('$E/evidence/heldout_$c.summary.json'))['$c']['agent_cost_usd'])")
  echo "$c agent cost: \$$COST"
  if ! $PY -c "import sys;sys.exit(0 if $COST <= $AGENT_LIMIT else 1)"; then
    echo "STOPPED: agent cost above \$$AGENT_LIMIT"; exit 3
  fi
done
$PY "$E/bench/report.py" "$E/evidence/heldout" baseline=results_heldout_baseline gated=results_heldout_gated --model $MODEL --tasks "$TASKS" --runs runs/heldout_gated
$PY "$E/bench/analyse_dev.py" "$E/evidence/heldout.csv" runs/heldout_gated | cut -c1-300
echo "== done $(date +%T)"
