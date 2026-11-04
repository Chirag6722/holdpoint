"""Spike: print totals from a replay results file."""
import json
import sys

R = json.load(open(sys.argv[1], encoding="utf-8"))
print("pairs", len(R))
for k in ["act_direct", "act_proxy", "abstain_direct", "abstain_proxy"]:
    print(k, "pass", sum(r[k]["pass"] for r in R), "commits", sum(r[k]["successful_commits"] for r in R),
          "held", sum(r[k]["held"] for r in R), "errors", sum(r[k]["errors"] for r in R))
print("paired direct", sum(r["act_direct"]["pass"] and r["abstain_direct"]["pass"] for r in R),
      "paired proxy", sum(r["act_proxy"]["pass"] and r["abstain_proxy"]["pass"] for r in R))
print("act_direct fails", [(r["category"], r["task_id"]) for r in R if not r["act_direct"]["pass"]])
print("abstain_direct passes", [(r["category"], r["task_id"]) for r in R if r["abstain_direct"]["pass"]])
print("proxy runs with a commit", sum(r[k]["successful_commits"] > 0 for r in R for k in ("act_proxy", "abstain_proxy")))
print("tool list differs", [(r["category"], r["task_id"]) for r in R
                            if r["act_direct"]["tools_listed"] != r["act_proxy"]["tools_listed"]
                            or r["abstain_direct"]["tools_listed"] != r["abstain_proxy"]["tools_listed"]])
print("seconds", round(sum(r["seconds"] for r in R)))
