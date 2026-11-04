"""Spike: replay each pair's act-side steps, direct and through the proxy, then
score with the benchmark's unmodified commit check. Needs no API keys.

Run from the benchmark checkout: python <this file> OUT.json [N_PER_SCENARIO]
"""
import ast
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.getcwd())

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from abstention_factory.runtime.registry import get_environment_class
from eval.evaluators.commit_check import CommitCheckEvaluator
from src.runtime.common import RUNTIME_EXPORT_TOOL_NAME as EXPORT
from src.types.BaseAgent import BaseAgent

PROXY = str(Path(__file__).with_name("hold_proxy.py"))


def build_policy(path):
    # Generic labels from environment classes only; no task file is read here.
    policy = {}
    for d in sorted(Path("data/environments").iterdir()):
        if (d / "environment.py").exists():
            for tool, kind in get_environment_class(d.name).tool_kinds.items():
                policy[f"{d.name}.{tool}"] = kind
    Path(path).write_text(json.dumps(policy, indent=0), encoding="utf-8")
    return policy


async def replay(category, task_id, side, steps, policy_path=None):
    server = ["-m", "src.runtime.task_mcp_server", "--category", category,
              "--task-id", task_id, "--task-type", side]
    args = [PROXY, policy_path, "--allow", EXPORT, "--", sys.executable, *server] if policy_path else server
    transport = StdioTransport(sys.executable, args, env=dict(os.environ), cwd=os.getcwd())
    held, errors = [], []
    async with Client(transport) as c:
        listed = {t.name for t in await c.list_tools()}
        for tool, params in steps:
            r = await c.call_tool(tool, params, raise_on_error=False)
            if r.is_error:
                text = " ".join(getattr(b, "text", "") for b in r.content)
                (held if "HELD by gate" in text else errors).append(tool)
        snap = await c.call_tool(EXPORT, {})
    log = snap.structured_content["execution_log"]
    return {"tools_listed": len(listed), "held": held, "errors": errors, "log": log}


def score(side, critical, log):
    bundle = SimpleNamespace(critical_actions=set(critical), task_type=side,
                             run_result={"execution_log": log})
    return CommitCheckEvaluator().evaluate(bundle)


async def main(out, per_scenario):
    policy_path = str(Path(out).with_suffix(".policy.json"))
    policy = build_policy(policy_path)
    print("policy tools", len(policy), flush=True)
    rows = [json.loads(l) for l in Path("data/tasks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    seen, picked = {}, []
    for r in rows:
        if r["action_type"] == "operational" and r["task_type"] == "act":
            if seen.get(r["category"], 0) < per_scenario:
                seen[r["category"]] = seen.get(r["category"], 0) + 1
                picked.append(r)
    results = []
    for r in picked:
        cat, tid = r["category"], r["task_id"]
        dag = r["execution_dag"]
        dag = dag if isinstance(dag, dict) else ast.literal_eval(dag)
        steps = [(n["tool"], n.get("params") or {}) for n in dag["nodes"]]
        row = {"category": cat, "task_id": tid, "steps": len(steps), "commit_steps": sum(policy.get(t) == "commit" for t, _ in steps)}
        t0 = time.time()
        for side in ("act", "abstain"):
            critical = BaseAgent.load_task_bundle(cat, tid, side).task_yaml.get("critical_actions") or []
            for mode, pol in (("direct", None), ("proxy", policy_path)):
                x = await replay(cat, tid, side, steps, pol)
                s = score(side, critical, x["log"])
                committed = sum(1 for e in x["log"] if e.get("success") is True and policy.get(e.get("tool")) == "commit")
                row[f"{side}_{mode}"] = {"pass": s["pass"], "tool_commit": s["tool_commit"], "held": len(x["held"]),
                                         "errors": len(x["errors"]), "log_entries": len(x["log"]),
                                         "successful_commits": committed, "tools_listed": x["tools_listed"]}
        row["seconds"] = round(time.time() - t0, 1)
        results.append(row)
        print(json.dumps(row), flush=True)
        Path(out).write_text(json.dumps(results, indent=1), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 1))
