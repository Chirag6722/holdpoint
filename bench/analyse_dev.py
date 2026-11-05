"""Break down a baseline against gated run. Usage: analyse_dev.py RESULTS.csv [RUNS_DIR_FOR_REASONS]"""
import collections
import csv
import json
import sys
from pathlib import Path

rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
T = lambda v: v == "True"
by = collections.defaultdict(dict)
for r in rows:
    by[(r["pair"], r["scenario"])][(r["condition"], r["side"])] = r


def outcome(r):
    if r is None or r.get("passed") == "":
        return "unscored"
    return "pass" if T(r["passed"]) else "fail"


print("transition per side (baseline to gated):")
for side in ("act", "abstain"):
    c = collections.Counter((outcome(v.get(("baseline", side))), outcome(v.get(("gated", side)))) for v in by.values())
    print(" ", side, dict(c))

print("\nby scenario: paired baseline, paired gated, act b/g, abstain b/g, n")
scen = collections.defaultdict(collections.Counter)
for (pair, s), v in by.items():
    c = scen[s]
    c["n"] += 1
    for cond in ("baseline", "gated"):
        a, b = outcome(v.get((cond, "act"))), outcome(v.get((cond, "abstain")))
        c[f"{cond}_act"] += a == "pass"
        c[f"{cond}_abstain"] += b == "pass"
        c[f"{cond}_paired"] += a == "pass" and b == "pass"
for s, c in sorted(scen.items()):
    print(f"  {s[:30]:<31} paired {c['baseline_paired']:>2}->{c['gated_paired']:<2} act {c['baseline_act']:>2}->{c['gated_act']:<2} "
          f"abstain {c['baseline_abstain']:>2}->{c['gated_abstain']:<2} n={c['n']}")

print("\ncommit attempts that succeeded, by side and condition (commit check view):")
for cond in ("baseline", "gated"):
    for side in ("act", "abstain"):
        rs = [r for r in rows if r["condition"] == cond and r["side"] == side]
        print(f"  {cond} {side}: commit_pass={sum(T(r['commit']) for r in rs)} judge_pass={sum(T(r['judge']) for r in rs)} of {len(rs)}")

print("\nsides that changed, with gate holds:")
for (pair, s), v in sorted(by.items()):
    for side in ("act", "abstain"):
        b, g = v.get(("baseline", side)), v.get(("gated", side))
        if outcome(b) != outcome(g):
            print(f"  {pair[:48]:<49} {side:<8} {outcome(b)}->{outcome(g)} commit {b['commit']}->{g['commit']} judge {b['judge']}->{g['judge']} held={g['held']} reviews={g['reviewer_calls']}")

if len(sys.argv) > 2:
    print("\nheld calls by layer and reason, should-act side (each is a possible false hold):")
    n = collections.Counter()
    for path in sorted(Path(sys.argv[2]).glob("*.act.*/audit.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            e = json.loads(line)["event"]
            if not e["allow"]:
                n[e["by"]] += 1
                print(f"  {path.parent.name[:44]:<45} {e['by']:<9} {e['tool'][:40]:<41} {str(e['reason'])[:150]}")
    print(" ", dict(n))
    n = collections.Counter()
    for path in Path(sys.argv[2]).glob("*.abstain.*/audit.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            e = json.loads(line)["event"]
            n[(e["by"], e["allow"])] += 1
    print("should-abstain decisions (layer, allowed):", dict(n))
