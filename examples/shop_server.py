"""A sandbox shop for examples/support_demo.py. Nothing here is real. Records every action in a ledger file."""
import json
import sys
from pathlib import Path

from fastmcp import FastMCP

LEDGER = Path(sys.argv[1])
mcp = FastMCP("shop")


def record(**entry) -> None:
    done = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else []
    LEDGER.write_text(json.dumps([*done, entry]), encoding="utf-8")


@mcp.tool
def read_ticket(ticket: str) -> str:
    """Read a customer's support ticket."""
    return f"Ticket {ticket}"


@mcp.tool
def issue_refund(order: str, amount: float) -> str:
    """Refund an order."""
    if order == "O-105":
        raise ValueError("payment gateway returned 504")
    record(action="refund", order=order, amount=amount)
    return "refunded"


@mcp.tool
def send_email(to: str, body: str) -> str:
    """Email someone."""
    record(action="email", to=to)
    return "sent"


if __name__ == "__main__":
    mcp.run(show_banner=False)
