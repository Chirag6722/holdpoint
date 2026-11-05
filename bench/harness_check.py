"""Drive each real harness class through the gate, with a stub reviewer and no model.

Harnesses launch MCP servers with a restricted environment and a 5-second request
limit by default. This proves that under the patched limit the gate starts, a
review slower than 5 seconds survives, the commit runs, and scoring export works.
Run from the benchmark checkout.
"""
import ast
import asyncio
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, os.getcwd())
sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness_patch

harness_patch.apply()

from gated_args import wrap
from google.adk.tools.mcp_tool.mcp_session_manager import StdioServerParameters

from src.runtime import googleadk, openaisdk
from src.runtime.common import RUNTIME_EXPORT_TOOL_NAME, build_runtime_server_args, normalize_runtime_export_payload
from src.types.BaseAgent import BaseAgent

CATEGORY, TASK = "ambiguous_action_specification", "preview_003"
REVIEW_SECONDS = 8


class SlowStub(BaseHTTPRequestHandler):
    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        time.sleep(REVIEW_SECONDS)
        verdict = json.dumps({"decision": "proceed", "reason": "stub"})
        data = json.dumps({"choices": [{"message": {"content": verdict}}]}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def args_for(bundle):
    return wrap(build_runtime_server_args(bundle), bundle.task_yaml["instruction"], "runs/harness")


def commit_call(bundle):
    tool = bundle.task_yaml["critical_actions"][0]
    pair = f"{CATEGORY}/{TASK}"
    for line in Path("data/tasks.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line) if line.strip() else {}
        if row.get("pair_id") == pair and row.get("task_type") == "act":
            dag = row["execution_dag"]
            dag = dag if isinstance(dag, dict) else ast.literal_eval(dag)
            return tool, next(n.get("params") or {} for n in dag["nodes"] if n["tool"] == tool)
    raise LookupError(pair)


def committed(log, tool):
    return [e for e in log if e["tool"] == tool and e["success"] is True]


async def check_openai(bundle):
    tool, params = commit_call(bundle)
    server = openaisdk._NameSafeMCPServer(
        name="task_env", params={"command": sys.executable, "args": args_for(bundle), "cwd": os.getcwd()},
        tool_filter={"blocked_tool_names": [RUNTIME_EXPORT_TOOL_NAME]})
    await server.connect()
    try:
        names = {t.name for t in await server.list_tools()}
        assert RUNTIME_EXPORT_TOOL_NAME not in names
        started = time.time()
        await server.call_tool(tool.replace(".", "__"), params)
        took = time.time() - started
        log = (await openaisdk._export_runtime_snapshot(server))["execution_log"]
        assert committed(log, tool), log
        print(f"openai harness ok: tools {len(names)}, commit ran after {took:.1f}s review, export ok")
    finally:
        await server.cleanup()


async def check_adk(bundle):
    tool, params = commit_call(bundle)
    toolset = googleadk.RuntimeMcpToolset(
        connection_params=StdioServerParameters(command=sys.executable, args=args_for(bundle), cwd=os.getcwd()),
        hidden_tool_names={RUNTIME_EXPORT_TOOL_NAME})
    try:
        names = {t.name for t in await toolset.get_tools()}
        assert RUNTIME_EXPORT_TOOL_NAME not in names
        started = time.time()
        await toolset.call_hidden_tool(tool, params)
        took = time.time() - started
        snap = await toolset.call_hidden_tool(RUNTIME_EXPORT_TOOL_NAME, {})
        log = normalize_runtime_export_payload(snap.structuredContent)["execution_log"]
        assert committed(log, tool), log
        print(f"adk harness ok: tools {len(names)}, commit ran after {took:.1f}s review, export ok")
    finally:
        await toolset.close()


async def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), SlowStub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env_file = Path("runs/harness/stub.env").resolve()
    env_file.parent.mkdir(parents=True, exist_ok=True)
    env_file.write_text("HOLDPOINT_REVIEWER_KEY=stub\nHOLDPOINT_REVIEWER_MODEL=stub\n"
                        f"HOLDPOINT_REVIEWER_BASE_URL=http://127.0.0.1:{server.server_address[1]}\n", encoding="utf-8")
    os.environ["HOLDPOINT_ENV_FILE"] = str(env_file)
    bundle = BaseAgent.load_task_bundle(CATEGORY, TASK, "act")
    await check_openai(bundle)
    await check_adk(bundle)


if __name__ == "__main__":
    asyncio.run(main())
