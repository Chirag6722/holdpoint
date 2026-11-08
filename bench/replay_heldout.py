"""Replay the measured held-out gated run through today's gate, with no model calls.

The gate has changed since the tag heldout-v1. This asks, for every decision recorded in that run,
whether today's gate would decide the same way. Each recorded call goes back through the gate with
the trace it had then, rebuilt from the run's own transcript. Where the measured gate asked the
reviewer, the reviewer's recorded verdict is replayed, so no model is called. If today's gate would
ask the reviewer where the measured one did not, the verdict is unknown and is reported as such.

The tool list a run's server offered is not recorded. It is taken from the policy, limited to the
tool groups the run used, and only matters when the user's request names a tool.

Run from the benchmark checkout, with holdpoint importable:
replay_heldout.py RUNS_DIR RESULTS_DIR POLICY OUT.json
"""
import json
import sys
from pathlib import Path

import yaml

from holdpoint.gate import Gate

EXPORT_TOOL = "__runtime_export_snapshot"


class Unknown(BaseException):
    """Today's gate asked the reviewer about a call the measured gate never sent to it.

    Not an Exception, because the gate turns any reviewer Exception into a hold, which would hide it."""


class RecordedReviewer:
    def __init__(self):
        self.verdict = None

    def __call__(self, *_):
        if self.verdict is None:
            raise Unknown
        return self.verdict


def transcript(results: Path, key: tuple) -> list[tuple[str, bool]]:
    cat, task, side = key
    path = next(results.glob(f"*/*/{cat}/{task}/{side}/*/trajectory.json"))
    steps = json.loads(path.read_text(encoding="utf-8"))["steps"]
    ran = []
    for i, step in enumerate(steps):
        if step["type"] == "tool_call":
            result = next(r for r in steps[i + 1:] if r["type"] == "tool_result" and r["tool"] == step["tool"])
            ran.append((step["tool"], result["success"]))
    return ran


def replay(run: Path, results: Path, policy: dict) -> dict:
    key = tuple(run.name.split(".")[:3])
    events = [json.loads(line)["event"] for line in (run / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    events = [e for e in events if e["by"] != "outcome"]
    ran = transcript(results, key)
    groups = {e["tool"].split(".")[0] for e in events} | {t.split(".")[0] for t, _ in ran}
    inventory = {t: {} for t in policy if t.split(".")[0] in groups}
    reviewer = RecordedReviewer()
    gate = Gate(policy, reviewer=reviewer, intent=(run / "intent.txt").read_text(encoding="utf-8"),
                allow=frozenset({EXPORT_TOOL}))
    trace, changes, unmatched = [], [], 0
    for e in events:
        reviewer.verdict = (e["allow"], e["reason"]) if e["by"] == "reviewer" else None
        try:
            now = gate.decide(e["tool"], e["args"], inventory, list(trace))
            if now.allow != e["allow"]:
                changes.append({"tool": e["tool"], "measured": f"{'ran' if e['allow'] else 'held'} by {e['by']}",
                                "today": f"{'ran' if now.allow else 'held'} by {now.by}: {now.reason}"})
        except Unknown:
            changes.append({"tool": e["tool"], "measured": f"{'ran' if e['allow'] else 'held'} by {e['by']}",
                            "today": "sent to the reviewer, verdict unknown"})
        if e["allow"] and e["tool"] != EXPORT_TOOL:
            short = e["tool"].rsplit(".", 1)[-1]
            match = next((i for i, (t, _) in enumerate(ran) if t.rsplit(".", 1)[-1] == short), None)
            # A call that ran but is missing from the transcript raised an error, which the transcript drops.
            # The measured gate's own reasons name those calls as failed.
            unmatched += match is None
            trace.append({"tool": e["tool"], "ok": False if match is None else ran.pop(match)[1], "text": ""})
    return {"run": "/".join(key), "decisions": len(events), "changes": changes, "unmatched": unmatched}


def main(runs_dir: str, results_dir: str, policy_file: str, out: str) -> None:
    policy = yaml.safe_load(Path(policy_file).read_text(encoding="utf-8"))
    rows = [replay(run, Path(results_dir), policy) for run in sorted(Path(runs_dir).iterdir()) if run.is_dir()]
    summary = {"runs": len(rows), "decisions": sum(r["decisions"] for r in rows),
               "decisions_that_change": sum(len(r["changes"]) for r in rows),
               "calls_missing_from_transcript_counted_as_failed": sum(r["unmatched"] for r in rows),
               "runs_that_change": [r for r in rows if r["changes"]]}
    Path(out).write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "runs_that_change"}, indent=1))
    for r in summary["runs_that_change"]:
        print(r["run"], json.dumps(r["changes"]))


if __name__ == "__main__":
    main(*sys.argv[1:5])
