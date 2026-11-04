"""Freeze the development and held-out split of the 131 operational pairs.

Stratified by scenario with a fixed seed. Reads only pair ids, scenario and
action type. Usage: make_split.py TASKS_JSONL OUT_JSON
"""
import collections
import hashlib
import json
import random
import sys

SEED = 20261104
DEV_TOTAL = 40


def split(pairs_by_scenario, seed=SEED, dev_total=DEV_TOTAL):
    rng = random.Random(seed)
    total = sum(map(len, pairs_by_scenario.values()))
    dev, held = [], []
    for scenario in sorted(pairs_by_scenario):
        ids = sorted(pairs_by_scenario[scenario])
        rng.shuffle(ids)
        n = round(len(ids) * dev_total / total)
        dev += ids[:n]
        held += ids[n:]
    return sorted(dev), sorted(held)


def main(tasks_path, out_path):
    with open(tasks_path, "rb") as f:
        raw = f.read()
    groups = collections.defaultdict(set)
    for line in raw.decode("utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if r["action_type"] == "operational":
                groups[r["category"]].add(r["pair_id"])
    dev, held = split(groups)
    assert not set(dev) & set(held)
    assert len(dev) + len(held) == sum(map(len, groups.values())) == 131
    out = {"seed": SEED, "tasks_jsonl_sha256": hashlib.sha256(raw).hexdigest(), "dev": dev, "held_out": held}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print("dev", len(dev), "held_out", len(held), "sha256", out["tasks_jsonl_sha256"])
    print({s: sum(p in dev for p in groups[s]) for s in sorted(groups)})


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
