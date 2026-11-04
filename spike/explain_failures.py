"""Spike: show why direct replay failed. Run from the benchmark checkout."""
import ast
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())

from fastmcp import Client
from fastmcp.client.transports import StdioTransport


async def show(cat, tid, side, steps):
    args = ["-m", "src.runtime.task_mcp_server", "--category", cat, "--task-id", tid, "--task-type", side]
    async with Client(StdioTransport(sys.executable, args, env=dict(os.environ), cwd=os.getcwd())) as c:
        for tool, params in steps:
            r = await c.call_tool(tool, params, raise_on_error=False)
            if r.is_error:
                print(f"  {side} ERROR {tool} params={str(params)[:120]}")
                print("     ", " ".join(getattr(b, "text", "") for b in r.content)[:260])


async def main(results_path):
    R = json.loads(Path(results_path).read_text(encoding="utf-8"))
    rows = [json.loads(l) for l in Path("data/tasks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    act = {(r["category"], r["task_id"]): r for r in rows if r["task_type"] == "act"}
    for r in R:
        sides = [s for s, want in (("act", not r["act_direct"]["pass"]), ("abstain", r["abstain_direct"]["pass"])) if want]
        if not sides:
            continue
        print(r["category"], r["task_id"], "sides needing explanation:", sides, flush=True)
        dag = act[(r["category"], r["task_id"])]["execution_dag"]
        dag = dag if isinstance(dag, dict) else ast.literal_eval(dag)
        steps = [(n["tool"], n.get("params") or {}) for n in dag["nodes"]]
        for s in sides:
            await show(r["category"], r["task_id"], s, steps)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
