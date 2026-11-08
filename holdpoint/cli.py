"""Human side: list holds, approve one, accept changed tools, verify the audit log."""
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import yaml
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from .approval import Approvals
from .approve_ui import make_server
from .audit import latest_hash, verify
from .prove import prove
from .proxy import downstream_env, hint

MAX_TTL_SECONDS = 3600


def ttl(text: str) -> float:
    value = float(text)
    if not 0 < value <= MAX_TTL_SECONDS:
        raise argparse.ArgumentTypeError(f"must be more than 0 and at most {MAX_TTL_SECONDS} seconds")
    return value


def format_holds(holds: list[dict]) -> str:
    """What a person needs before approving: the exact call, why it was held, and how to approve it."""
    if not holds:
        return "Nothing is waiting for approval."
    blocks = []
    for h in sorted(holds, key=lambda h: h["at"]):
        when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(h["at"]))
        args = "\n".join(f"    {k} = {json.dumps(v)}" for k, v in sorted(h["args"].items())) or "    (no arguments)"
        blocks.append(f"Held at {when}\n  Would run: {h['tool']}\n{args}\n  Why held: {h['reason']}\n"
                      f"  To allow this exact call once: holdpoint approve {h['hold_id']}")
    return "\n\n".join(blocks)


def confirm_approval(holds: list[dict], hold_id: str, assume_yes: bool) -> None:
    """Show the exact call before approving it, so an agent's description of it is never what gets approved."""
    hold = next((h for h in holds if h["hold_id"] == hold_id), None)
    if hold is None:
        sys.exit(f"not approved: no hold {hold_id} is waiting")
    print(format_holds([hold]).rsplit("\n", 1)[0])
    if assume_yes:
        return
    if not sys.stdin.isatty():
        sys.exit("not approved: read the call above, then run again with --yes")
    if input("Approve this exact call once? Type yes: ").strip().lower() != "yes":
        sys.exit("not approved")


def draft_policy(tools) -> str:
    """Every tool starts as commit. Server hints are untrusted, so they only inform the person editing the file."""
    lines = ["# Change a tool to lookup or verify only after checking that it cannot change anything.",
             "# Change a tool to person if it must always wait for a human and never rely on the reviewer."]
    for t in sorted(tools, key=lambda t: t.name):
        read_only = hint(getattr(t, "annotations", None), "read_only_hint", "readOnlyHint")
        note = "  # the server claims this is read-only; check it" if read_only else ""
        lines.append(f"{json.dumps(t.name)}: commit{note}")
    return "\n".join(lines)


def prove_command(argv: list[str]) -> None:
    p = argparse.ArgumentParser(prog="holdpoint prove")
    p.add_argument("policy")
    p.add_argument("--tool", required=True)
    p.add_argument("--never", required=True, help='for example "amount > 500" or "to not in [Ann, Bob]"')
    p.add_argument("--even-with-approval", action="store_true", help="also rule out calls a person approved")
    a = p.parse_args(argv)
    with open(a.policy, encoding="utf-8") as f:
        policy = yaml.safe_load(f) or {}
    try:
        result = prove(policy, a.tool, a.never, a.even_with_approval)
    except (ValueError, RuntimeError) as exc:
        print(f"could not prove: {exc}", file=sys.stderr)
        sys.exit(2)
    who = "even with a person's approval" if a.even_with_approval else "without a person's approval"
    if result.proved:
        print(f"PROVED: no call to {a.tool} where {a.never} can run {who}.")
    else:
        print(f"ESCAPE: this call to {a.tool} runs {who}: {json.dumps(result.call)}")
    print("Assumes: " + "; ".join(result.assumptions) + ".")
    print("This covers the rules as written, not whether they are the right rules.")
    sys.exit(0 if result.proved else 1)


async def _list_tools(command: list[str]):
    async with Client(StdioTransport(command[0], command[1:], env=downstream_env(os.environ))) as client:
        return await client.list_tools()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["draft-policy"]:
        if "--" not in argv or not argv[argv.index("--") + 1:]:
            sys.exit("usage: holdpoint draft-policy -- COMMAND [ARG...]")
        print(draft_policy(asyncio.run(_list_tools(argv[argv.index("--") + 1:]))))
        return
    if argv[:1] == ["prove"]:
        return prove_command(argv[1:])
    p = argparse.ArgumentParser(prog="holdpoint")
    p.add_argument("--state-dir", help="the proxy's state directory; every command except prove and draft-policy needs it")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("prove", help="prove a limit holds for every possible call, or print one that breaks it")
    sub.add_parser("draft-policy", help="write a first policy from a server's tool list: draft-policy -- COMMAND")
    hp = sub.add_parser("holds", help="list calls waiting for a person")
    hp.add_argument("--json", action="store_true")
    ap = sub.add_parser("approve", help="show one held call, then allow it once")
    ap.add_argument("hold_id")
    ap.add_argument("--ttl", type=ttl, default=300.0, help=f"seconds the approval stays valid, at most {MAX_TTL_SECONDS}")
    ap.add_argument("--yes", action="store_true", help="skip the question; the call is still printed")
    vl = sub.add_parser("verify-log", help="check the audit log has not been changed")
    vl.add_argument("--expect", help="a latest hash saved earlier, outside the state directory")
    sub.add_parser("accept-tools", help="trust the tool definitions as they are now")
    rp = sub.add_parser("reject", help="refuse a held call, and cancel any approval for it")
    rp.add_argument("hold_id")
    sv = sub.add_parser("serve", help="open a local approval screen")
    sv.add_argument("--port", type=int, default=0)
    a = p.parse_args(argv)
    if a.cmd in ("prove", "draft-policy"):
        p.error(f"put {a.cmd} first: holdpoint {a.cmd} ...")
    if not a.state_dir:
        p.error("--state-dir is required for this command")
    key = os.environ.get("HOLDPOINT_KEY")
    key = key.encode("utf-8") if key else None
    state = Path(a.state_dir)
    if a.cmd == "verify-log":
        log = state / "audit.jsonl"
        ok, n = verify(log, key, a.expect)
        print(f"{'intact' if ok else 'BROKEN'} after {n} lines")
        if not key:
            print("Unsigned check: set HOLDPOINT_KEY. Without it, someone rewriting the whole log goes unnoticed.")
        if ok and n:
            print(f"Latest hash, save it outside this directory to catch a later rollback: {latest_hash(log)}")
        sys.exit(0 if ok else 1)
    if a.cmd == "accept-tools":
        (state / "tool_pins.json").unlink(missing_ok=True)
        print("Tool definitions will be trusted as they are at the next call.")
        return
    approvals = Approvals(state, key)
    if a.cmd == "holds":
        holds = approvals.list_holds()
        print(json.dumps(holds, indent=1) if a.json else format_holds(holds))
    elif a.cmd == "serve":
        if key is None:
            sys.exit("set HOLDPOINT_KEY first: approvals cannot be signed without it")
        server, url = make_server(approvals, a.port)
        print(f"Open this link. It is secret, because it can approve calls:\n{url}", flush=True)
        server.serve_forever()
    elif a.cmd == "reject":
        try:
            approvals.deny(a.hold_id)
        except ValueError as exc:
            sys.exit(f"not rejected: {exc}")
        print(f"rejected {a.hold_id}")
    else:
        confirm_approval(approvals.list_holds(), a.hold_id, a.yes)
        try:
            approvals.approve(a.hold_id, a.ttl)
        except ValueError as exc:
            sys.exit(f"not approved: {exc}")
        print(f"approved {a.hold_id} for {a.ttl:.0f} seconds, one use")


if __name__ == "__main__":
    main()
