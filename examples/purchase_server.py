"""A sandbox purchasing system for examples/purchase_demo.py. Nothing here is real."""
import json
import sys
from pathlib import Path

from fastmcp import FastMCP

LEDGER = Path(sys.argv[1])
mcp = FastMCP("purchasing")


@mcp.tool
def list_suppliers() -> str:
    """List approved suppliers."""
    return "Northline Bearings, Kestrel Valves"


@mcp.tool
def place_order(supplier: str, amount: float, reference: str) -> str:
    """Place a purchase order."""
    done = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else []
    LEDGER.write_text(json.dumps([*done, {"supplier": supplier, "amount": amount, "reference": reference}]), encoding="utf-8")
    if reference == "PO-TIMEOUT":
        raise TimeoutError("no reply from the supplier system, though the order went through")
    return "placed"


if __name__ == "__main__":
    mcp.run(show_banner=False)
