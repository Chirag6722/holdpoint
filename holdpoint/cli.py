"""Human side: list holds, approve one, verify the audit log."""
import argparse
import json
import os
import sys
from pathlib import Path

from .approval import Approvals
from .audit import verify


def main(argv=None):
    p = argparse.ArgumentParser(prog="holdpoint")
    p.add_argument("--state-dir", required=True)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("holds")
    ap = sub.add_parser("approve")
    ap.add_argument("hold_id")
    ap.add_argument("--ttl", type=float, default=300.0)
    sub.add_parser("verify-log")
    a = p.parse_args(argv)
    if a.cmd == "verify-log":
        ok, n = verify(Path(a.state_dir) / "audit.jsonl")
        print(f"{'intact' if ok else 'BROKEN'} after {n} lines")
        sys.exit(0 if ok else 1)
    key = os.environ.get("HOLDPOINT_KEY")
    approvals = Approvals(a.state_dir, key.encode("utf-8") if key else None)
    if a.cmd == "holds":
        for h in approvals.list_holds():
            print(json.dumps(h, indent=1))
    else:
        approvals.approve(a.hold_id, a.ttl)
        print(f"approved {a.hold_id} for {a.ttl:.0f} seconds, one use")


if __name__ == "__main__":
    main()
