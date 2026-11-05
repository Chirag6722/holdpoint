"""Exact McNemar test and a confidence interval on baseline against gated.

Usage: paired_stats.py RESULTS.csv   Run with no arguments to check against known values.
"""
import csv
import json
import math
import sys
from collections import defaultdict


def mcnemar_exact(only_baseline: int, only_gated: int) -> float:
    """Two-sided exact p from the binomial distribution on the discordant pairs."""
    n = only_baseline + only_gated
    if n == 0:
        return 1.0
    k = min(only_baseline, only_gated)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


def wilson(passed: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = passed / n
    d = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / d
    return (centre - half, centre + half)


def analyse(path):
    outcome = defaultdict(dict)
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            outcome[r["pair"]][(r["condition"], r["side"])] = r
    both = {}
    for pair, sides in outcome.items():
        try:
            both[pair] = {c: all(sides[(c, s)]["passed"] == "True" for s in ("act", "abstain"))
                          for c in ("baseline", "gated")}
            if any(sides[(c, s)]["passed"] == "" for c in ("baseline", "gated") for s in ("act", "abstain")):
                del both[pair]
        except KeyError:
            continue
    n = len(both)
    base = sum(v["baseline"] for v in both.values())
    gated = sum(v["gated"] for v in both.values())
    only_b = sum(v["baseline"] and not v["gated"] for v in both.values())
    only_g = sum(v["gated"] and not v["baseline"] for v in both.values())
    return {"pairs_scored_in_both": n, "baseline_paired": base, "gated_paired": gated,
            "baseline_pct": round(100 * base / n, 1), "gated_pct": round(100 * gated / n, 1),
            "baseline_95ci_pct": [round(100 * x, 1) for x in wilson(base, n)],
            "gated_95ci_pct": [round(100 * x, 1) for x in wilson(gated, n)],
            "pairs_only_baseline_passed": only_b, "pairs_only_gated_passed": only_g,
            "mcnemar_exact_p": round(mcnemar_exact(only_b, only_g), 4)}


def self_check():
    assert mcnemar_exact(0, 0) == 1.0
    assert abs(mcnemar_exact(1, 5) - 0.21875) < 1e-9
    assert abs(mcnemar_exact(0, 6) - 0.03125) < 1e-9
    assert mcnemar_exact(5, 5) == 1.0
    low, high = wilson(50, 100)
    assert abs(low - 0.4038) < 1e-3 and abs(high - 0.5962) < 1e-3
    print("self-check passed")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(json.dumps(analyse(sys.argv[1]), indent=1))
    else:
        self_check()
