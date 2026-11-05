#!/usr/bin/env bash
# One gated tuning round on the development split. Usage: dev_round.sh ROUND_NUMBER
set -u
E="${HOLDPOINT_REPO:-$PWD}"   # run from the repo root
R="$1"
cd "${AGENTABSTAIN_DIR:-$HOME/agentabstain}" || exit 1
PY=.venv-era/bin/python
MODEL=claude-haiku-4-5
export PYTHONUTF8=1 HOLDPOINT_AGENT_BACKEND=anthropic HOLDPOINT_RUNS_DIR="runs/gated_r$R"
set -a; . ./.env; set +a
TASKS="$E/bench/tasks_dev.yaml"
CFG="runs/gated_r$R.yaml"
mkdir -p runs
sed "s#results_gated/#results_gated_r$R/#" "$E/bench/configs/gated_claude_haiku.yaml" | tr -d '\r' > "$CFG"
echo "== round $R gated $(date +%T)"
$PY "$E/bench/run_gated.py" gated --runtime-config "$CFG" --task-config "$TASKS" --workers 3 > "dev_r$R.log" 2>&1
echo "inference exit $?"
$PY -m eval.runner --provider openaisdk --model $MODEL --results-root "results_gated_r$R" --judge-config "$E/bench/configs/judge_claude.yaml" --workers 3 >> "dev_r$R.log" 2>&1
echo "eval exit $?"
$PY "$E/bench/report.py" "$E/evidence/rounds/round$R" baseline=results_baseline gated="results_gated_r$R" --model $MODEL --tasks "$TASKS" --runs "runs/gated_r$R"
$PY "$E/bench/analyse_dev.py" "$E/evidence/rounds/round$R.csv" "runs/gated_r$R" | cut -c1-300
echo "== done $(date +%T)"
