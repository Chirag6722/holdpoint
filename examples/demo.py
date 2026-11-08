"""Watch the gate work, with no API keys. Run: python examples/demo.py

A scripted client plays the agent. Everything else is real: the proxy runs as its own
process over stdio, in front of a separate tool server, and approval uses the CLI.
"""
import asyncio
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def holdpoint_env(key):
    env = {k: v for k, v in os.environ.items() if not k.startswith("HOLDPOINT_")}
    env["FASTMCP_LOG_LEVEL"] = "CRITICAL"  # the servers' own errors are part of the demo, not news
    return {**env, "HOLDPOINT_KEY": key, "PYTHONPATH": str(ROOT), "PYTHONUTF8": "1"}


def cli(state, env, *args):
    cmd = [sys.executable, "-m", "holdpoint.cli", "--state-dir", state, *args]
    return subprocess.run(cmd, env=env, capture_output=True, text=True, check=True).stdout


async def attempt(client, label, tool, **args):
    result = await client.call_tool(tool, args, raise_on_error=False)
    text = " ".join(getattr(b, "text", "") for b in result.content)
    outcome = "HELD" if "HELD" in text else "RAN"
    print(f"  {label:<44} {outcome}")
    return outcome


def paid(ledger):
    return json.loads(Path(ledger).read_text(encoding="utf-8")) if Path(ledger).exists() else []


async def main():
    with tempfile.TemporaryDirectory() as tmp:
        state, ledger = str(Path(tmp) / "state"), str(Path(tmp) / "ledger.json")
        env = holdpoint_env(os.urandom(16).hex())
        intent = Path(tmp) / "request.txt"
        intent.write_text("Pay Ann $10 from account 1.", encoding="utf-8")
        args = ["-m", "holdpoint.proxy", "--policy", str(HERE / "policy.yaml"), "--state-dir", state,
                "--intent-file", str(intent), "--", sys.executable, str(HERE / "bank_server.py"), ledger]
        pay = {"to": "Ann", "amount": 10}
        async with Client(StdioTransport(sys.executable, args, env=env, cwd=str(ROOT))) as client:
            print("The agent works normally until it tries something irreversible:")
            outcomes = [await attempt(client, "read the balance", "read_balance", account="1"),
                        await attempt(client, "send $10 to Ann", "send_payment", **pay),
                        await attempt(client, "send it again, claiming approval", "send_payment", **pay, approved=True)]
            print(f"  Money sent so far: {paid(ledger)}\n")

            hold = next(h for h in json.loads(cli(state, env, "holds", "--json")) if h["args"] == pay)
            print(f"A person reviews the hold and approves that one call, once:\n  {hold['tool']} {hold['args']}")
            cli(state, env, "approve", hold["hold_id"], "--ttl", "60", "--yes")
            print("\nThe approval covers exactly that call:")
            outcomes += [await attempt(client, "try $9,999 to Mallory instead", "send_payment", to="Mallory", amount=9999),
                         await attempt(client, "the approved call", "send_payment", **pay),
                         await attempt(client, "replay the approved call", "send_payment", **pay),
                         await attempt(client, "a tool the policy has never heard of", "wipe_everything")]
            print(f"  Money sent in total: {paid(ledger)}\n")
        print("Audit log check:", cli(state, env, "verify-log").strip())
        assert outcomes == ["RAN", "HELD", "HELD", "HELD", "RAN", "HELD", "HELD"], outcomes
        assert paid(ledger) == [pay], paid(ledger)
        print("All outcomes were as expected.")


if __name__ == "__main__":
    asyncio.run(main())
