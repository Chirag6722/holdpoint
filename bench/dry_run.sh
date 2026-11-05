#!/usr/bin/env bash
# Keyless dry run on the development split under Linux, in the release-date environment.
set -u
E="/mnt/c/Users/chira/Downloads/AI safety challange"
cd "$HOME/agentabstain-spike" || exit 1
export PYTHONUTF8=1
.venv-era/bin/python "$E/bench/export_policy.py" "$E/bench/policy.yaml"
.venv-era/bin/python "$E/bench/make_taskfiles.py"
.venv-era/bin/python "$E/bench/dry_run.py" "$E/evidence/dry_run_dev.json" "$@" > dry_run.log 2> dry_run.err
echo "dry run exit $?"
tail -22 dry_run.log | cut -c1-200
echo "--- last error lines"
grep -nE "^[A-Za-z_.]*(Error|Exception)|Timed out" dry_run.err | tail -6 | cut -c1-220
