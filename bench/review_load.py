"""Exploratory, not in the measurement plan: what a person would have been asked to review.

The benchmark has no person, so a hold simply ends the attempt. Run from the benchmark checkout:
review_load.py RUNS_DIR OUT.json
"""
import json
import sys
from pathlib import Path

runs, out = Path(sys.argv[1]), sys.argv[2]
result = {}
for side in ("act", "abstain"):
    held = allowed = tasks_with_hold = tasks_with_commit = 0
    for path in runs.glob(f"*.{side}.*/audit.jsonl"):
        events = [json.loads(line)["event"] for line in path.read_text(encoding="utf-8").splitlines()]
        gated = [e for e in events if e["by"] in ("reviewer", "checks", "gate")]
        held += sum(not e["allow"] for e in gated)
        allowed += sum(e["allow"] for e in gated)
        tasks_with_commit += bool(gated)
        tasks_with_hold += any(not e["allow"] for e in gated)
    result[side] = {"commit_attempts": held + allowed, "held": held, "allowed_without_a_person": allowed,
                    "tasks_with_a_commit_attempt": tasks_with_commit, "tasks_with_a_hold": tasks_with_hold}
Path(out).write_text(json.dumps(result, indent=1), encoding="utf-8", newline="\n")
print(json.dumps(result, indent=1))
