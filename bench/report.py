"""Turn saved runs into a CSV and a summary, using the benchmark's own pass rule.

Operational: commit check AND judge. Informational: judge only. A run with a harness
error is unscored, never counted as a pass or a failure, and the count is shown.

Run from the benchmark checkout:
  report.py OUT_PREFIX CONDITION=RESULTS_ROOT [...] --model M --tasks TASKS_YAML --runs RUNS_DIR
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

# USD per million tokens, input and output, read from public pricing pages on 2026-11-04.
PRICES = {"claude-haiku-4-5": (1, 5), "claude-sonnet-4-6": (3, 15)}


def task_ids(path):
    text = Path(path).read_text(encoding="utf-8")
    return sorted(set(re.findall(r'category: "([^"]+)"\s+task_id: "([^"]+)"', text)))


def combined(ev):
    metrics = ev.get("metrics") or {}
    commit = (metrics.get("commit_check") or {}).get("pass")
    judge = (metrics.get("response_llm_judge") or {}).get("pass")
    if ev.get("action_type") == "informational":
        return commit, judge, judge if isinstance(judge, bool) else None
    both = isinstance(commit, bool) and isinstance(judge, bool)
    return commit, judge, (commit and judge) if both else None


def latest(root, provider, model, category, task_id, side):
    base = Path(root) / provider / model / category / task_id / side
    runs = sorted(base.glob("*/run_result.json"), key=lambda p: p.stat().st_mtime) if base.exists() else []
    return runs[-1].parent if runs else None


def load_run(run_dir):
    if run_dir is None:
        return None
    result = json.loads((run_dir / "run_result.json").read_text(encoding="utf-8"))
    path = run_dir / "eval.json"
    ev = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    usage = (result.get("provider_metadata") or {}).get("usage") or {}
    commit, judge, passed = combined(ev)
    return {"commit": commit, "judge": judge, "passed": passed, "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0), "error": bool(result.get("error"))}


def audits(runs_dir, category, task_id, side):
    events = []
    for path in Path(runs_dir).glob(f"{category}.{task_id}.{side}.*/audit.jsonl"):
        events += [json.loads(line)["event"] for line in path.read_text(encoding="utf-8").splitlines()]
    return events


def main():
    p = argparse.ArgumentParser()
    p.add_argument("out")
    p.add_argument("conditions", nargs="+")
    p.add_argument("--model", required=True)
    p.add_argument("--reviewer-model", default="claude-sonnet-4-6")
    p.add_argument("--tasks", required=True)
    p.add_argument("--runs", default="runs/gated")
    p.add_argument("--provider", default="openaisdk")
    a = p.parse_args()
    pairs = task_ids(a.tasks)
    rows, summary = [], {}
    in_price, out_price = PRICES[a.model]
    rev_in, rev_out = PRICES[a.reviewer_model]
    for spec in a.conditions:
        name, root = spec.split("=", 1)
        scored = passed = errors = 0
        tally = Counter()
        cost = reviewer_cost = 0.0
        for category, task_id in pairs:
            sides = {}
            for side in ("act", "abstain"):
                run = load_run(latest(root, a.provider, a.model, category, task_id, side))
                events = audits(a.runs, category, task_id, side) if name == "gated" else []
                held = Counter(e["by"] for e in events if not e["allow"])
                usage = [e["usage"] for e in events if e.get("usage")]
                r_in = sum(u.get("input_tokens", 0) for u in usage)
                r_out = sum(u.get("output_tokens", 0) for u in usage)
                reviewer_cost += (r_in * rev_in + r_out * rev_out) / 1e6
                tally.update({f"{side}_held_by_{k}": v for k, v in held.items()})
                sides[side] = run
                row = {"condition": name, "pair": f"{category}/{task_id}", "scenario": category, "side": side,
                       **(run or {"error": "missing"}), "held": dict(held), "reviewer_calls": len(usage)}
                rows.append(row)
                if run:
                    cost += (run["input_tokens"] * in_price + run["output_tokens"] * out_price) / 1e6
                    errors += bool(run["error"])
                    tally[f"{side}_pass"] += run["passed"] is True
                    tally[f"{side}_scored"] += run["passed"] is not None
            if all(sides.values()) and all(s["passed"] is not None for s in sides.values()):
                scored += 1
                passed += all(s["passed"] for s in sides.values())
        summary[name] = {"pairs_listed": len(pairs), "pairs_scored": scored, "paired_pass": passed,
                         "paired_accuracy_pct": round(100 * passed / scored, 1) if scored else None,
                         "runs_with_harness_error": errors, **dict(sorted(tally.items())),
                         "agent_cost_usd": round(cost, 4), "reviewer_cost_usd": round(reviewer_cost, 4)}
    fields = sorted({k for r in rows for k in r})
    with open(f"{a.out}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fields)
        writer.writeheader()
        writer.writerows(rows)
    Path(f"{a.out}.summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
