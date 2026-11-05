#!/usr/bin/env bash
# One real development pair, baseline and gated, to measure actual cost. Stops if no key is set.
set -u
E="/mnt/c/Users/chira/Downloads/AI safety challange"
cd "$HOME/agentabstain-spike" || exit 1
PY=.venv-era/bin/python
export PYTHONUTF8=1 HOLDPOINT_AGENT_BACKEND=anthropic HOLDPOINT_RUNS_DIR=runs/gated
grep -q '^ANTHROPIC_API_KEY=.' .env 2>/dev/null || { echo "no key in .env"; exit 2; }
grep -q '^HOLDPOINT_REVIEWER_PROVIDER=' .env || echo 'HOLDPOINT_REVIEWER_PROVIDER=anthropic' >> .env
grep -q '^HOLDPOINT_REVIEWER_MODEL=' .env || echo 'HOLDPOINT_REVIEWER_MODEL=claude-sonnet-4-6' >> .env
set -a; . ./.env; set +a
head -7 "$E/bench/tasks_dev.yaml" | tr -d '\r' > tasks_one.yaml
cat tasks_one.yaml
for c in baseline gated; do
  $PY "$E/bench/run_gated.py" $c --runtime-config "$E/bench/configs/${c}_claude_haiku.yaml" --task-config tasks_one.yaml --multi-run > "first_$c.log" 2>&1
  echo "$c inference exit $?"; grep -E '"(succeeded|failed|completed|errors?)"' "first_$c.log" | head -5
  $PY -m eval.runner --provider openaisdk --model claude-haiku-4-5 --results-root "results_$c" --judge-config "$E/bench/configs/judge_claude.yaml" >> "first_$c.log" 2>&1
  echo "$c eval exit $?"
done
$PY "$E/bench/report.py" "$E/evidence/first_pair" baseline=results_baseline gated=results_gated --model claude-haiku-4-5 --tasks tasks_one.yaml
