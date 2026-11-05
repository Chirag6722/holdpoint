"""Full path with no keys: real sandboxes, real stdio proxy, stub reviewer over HTTP.

Replays each development pair's act-side steps. This is a script, not an agent, so
it measures the deterministic checks and the plumbing, not agent behaviour.

Only the development split is read. Run from the benchmark checkout:
  python dry_run.py OUT.json [--pairs N]
"""
import ast
import asyncio
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.getcwd())
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from gated_args import EXPORT_TOOL, wrap

from eval.evaluators.commit_check import CommitCheckEvaluator
from src.runtime.common import build_runtime_server_args
from src.types.BaseAgent import BaseAgent, TaskBundle  # noqa: F401

CAPTURED = []


class Stub(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        CAPTURED.append(body)
        decision = "hold" if self.path.startswith("/hold") else "proceed"
        reply = {"choices": [{"message": {"content": json.dumps({"decision": decision, "reason": f"stub {decision}"})}}]}
        data = json.dumps(reply).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def score(side, critical, log):
    bundle = SimpleNamespace(critical_actions=set(critical), task_type=side, run_result={"execution_log": log})
    return CommitCheckEvaluator().evaluate(bundle)


async def replay(bundle, steps, port, mode):
    env = {**os.environ, "HOLDPOINT_REVIEWER_KEY": "stub", "HOLDPOINT_REVIEWER_MODEL": "stub",
           "HOLDPOINT_REVIEWER_BASE_URL": f"http://127.0.0.1:{port}/{mode}"}
    args = wrap(build_runtime_server_args(bundle), bundle.task_yaml["instruction"], "runs/dry")
    reasons = []
    async with Client(StdioTransport(sys.executable, args, env=env, cwd=os.getcwd())) as c:
        for tool, params in steps:
            r = await c.call_tool(tool, params, raise_on_error=False)
            if r.is_error:
                text = " ".join(getattr(b, "text", "") for b in r.content)
                if text.startswith("HELD") or "HELD:" in text:
                    reasons.append(text.split("Reason: ", 1)[1].split(" Nothing was changed")[0])
        snap = await c.call_tool(EXPORT_TOOL, {})
    return snap.structured_content["execution_log"], reasons


async def main(out, limit):
    split = json.loads((HERE / "split.json").read_text(encoding="utf-8"))
    dev = set(split["dev"])
    rows = [json.loads(line) for line in Path("data/tasks.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    act = sorted((r for r in rows if r["pair_id"] in dev and r["task_type"] == "act"), key=lambda r: r["pair_id"])[:limit]
    server = HTTPServer(("127.0.0.1", 0), Stub)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    results = []
    for r in act:
        dag = r["execution_dag"]
        dag = dag if isinstance(dag, dict) else ast.literal_eval(dag)
        steps = [(n["tool"], n.get("params") or {}) for n in dag["nodes"]]
        row = {"pair": r["pair_id"], "category": r["category"]}
        for side in ("act", "abstain"):
            bundle = BaseAgent.load_task_bundle(r["category"], r["task_id"], side)
            critical = bundle.task_yaml.get("critical_actions") or []
            for mode in ("proceed", "hold"):
                log, reasons = await replay(bundle, steps, port, mode)
                row[f"{side}_{mode}"] = {"pass": score(side, critical, log)["pass"], "reasons": reasons}
        results.append(row)
        print(json.dumps({k: (v if k in ("pair",) else (v["pass"] if isinstance(v, dict) else None))
                          for k, v in row.items() if k != "category"}), flush=True)
        Path(out).write_text(json.dumps(results, indent=1), encoding="utf-8", newline="\n")
    forbidden = ["abstention_trigger", "critical_actions", "abstain_escalated_tool", "task_type", "transformation_dimension"]
    forbidden += sorted({r["category"] for r in rows})
    leaks = {w: sum(w in json.dumps(b) for b in CAPTURED) for w in forbidden}
    n = len(results)
    summary = {
        "pairs": n, "reviewer_requests": len(CAPTURED), "answer_field_leaks": {k: v for k, v in leaks.items() if v},
        "reviewer_proceed": {
            "act_pass": sum(x["act_proceed"]["pass"] for x in results),
            "abstain_pass_by_checks_alone": sum(x["abstain_proceed"]["pass"] for x in results),
            "paired": sum(x["act_proceed"]["pass"] and x["abstain_proceed"]["pass"] for x in results)},
        "reviewer_hold": {
            "act_pass": sum(x["act_hold"]["pass"] for x in results),
            "abstain_pass": sum(x["abstain_hold"]["pass"] for x in results)},
    }
    print(json.dumps(summary, indent=1))
    Path(out).with_suffix(".summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    limit = int(sys.argv[sys.argv.index("--pairs") + 1]) if "--pairs" in sys.argv else 10_000
    asyncio.run(main(sys.argv[1], limit))
