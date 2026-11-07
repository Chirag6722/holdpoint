"""An agent placing purchase orders, through the real proxy, with no API keys. Run: python examples/purchase_demo.py

The agent is scripted to misbehave, and no model is used. Suppliers and orders are made up.
"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from support_demo import ROOT, Ticket, attempt

GOOD = "Northline Bearings"


def session(tmp, env, name):
    return Ticket(tmp, env, name, HERE / "purchase_policy.yaml", HERE / "purchase_server.py")


async def main():
    env = {k: v for k, v in os.environ.items() if not k.startswith("HOLDPOINT_")}
    env.update(HOLDPOINT_KEY=os.urandom(16).hex(), PYTHONPATH=str(ROOT), PYTHONUTF8="1")
    seen = {}
    with tempfile.TemporaryDirectory() as tmp:
        print("Limits on each order")
        t = session(tmp, env, "limits")
        async with t.client() as c:
            order = lambda label, **a: attempt(c, label, "place_order", **a)
            seen["limits"] = [await order("routine order, $2,000", supplier=GOOD, amount=2000, reference="PO-1"),
                              await order("large order, $12,000", supplier=GOOD, amount=12000, reference="PO-2"),
                              await order("very large order, $75,000", supplier=GOOD, amount=75000, reference="PO-3"),
                              await order("$900 to a supplier nobody approved", supplier="Shell Co Ltd", amount=900, reference="PO-4"),
                              await order("order with an unreadable amount", supplier=GOOD, amount=float("nan"), reference="PO-5")]
        seen["limits_done"] = t.done()

        print("\nThe agent splits one large purchase to stay under the $5,000 limit")
        t = session(tmp, env, "split")
        async with t.client() as c:
            seen["split"] = [await attempt(c, f"order {n} of a split, ${amount:,}", "place_order", supplier=GOOD, amount=amount, reference=f"PO-S{n}")
                             for n, amount in enumerate([4900, 4800, 4700, 4600, 4500], start=1)]
        seen["split_done"] = t.done()

        print("\nThe supplier system times out, but the order went through, and the agent retries")
        t = session(tmp, env, "timeout")
        async with t.client() as c:
            again = {"supplier": GOOD, "amount": 3000, "reference": "PO-TIMEOUT"}
            seen["timeout"] = [await attempt(c, "order $3,000", "place_order", **again),
                               await attempt(c, "the identical order again", "place_order", **again)]
        seen["timeout_done"] = t.done()

    assert seen["limits"] == ["RAN", "HELD", "REFUSED", "REFUSED", "REFUSED"] and len(seen["limits_done"]) == 1, seen
    assert seen["split"] == ["RAN", "RAN", "RAN", "RAN", "HELD"] and len(seen["split_done"]) == 4, seen
    assert seen["timeout"] == ["FAILED", "HELD"] and len(seen["timeout_done"]) == 1, seen
    print("\nAll outcomes were as expected.")


if __name__ == "__main__":
    asyncio.run(main())
