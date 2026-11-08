"""Problems found by a judge-style review on 8 Nov 2026. Each test reproduced its problem before the fix."""
import asyncio

from fastmcp import Client, FastMCP

from holdpoint import rules
from holdpoint.gate import Gate
from holdpoint.proxy import build

KEY = b"judge-test-key"


def test_a_negative_amount_breaks_an_over_limit():
    entry = {"label": "auto", "rules": [{"arg": "amount", "over": 500, "then": "deny"}]}
    gate = Gate({"pay": entry}, intent="pay")
    assert gate.decide("pay", {"amount": 100}, {}, []).allow
    decision = gate.decide("pay", {"amount": -100000}, {}, [])
    assert not decision.allow and decision.by == "floor"


def test_allowlist_cannot_skip_a_deny_rule():
    entry = {"label": "commit", "rules": [{"arg": "amount", "over": 500, "then": "deny"}]}
    gate = Gate({"pay": entry}, intent="pay", allow=frozenset({"pay"}))
    assert gate.decide("pay", {"amount": 10}, {}, []).allow
    assert gate.decide("pay", {"amount": 9999}, {}, []).by == "floor"


def test_tools_that_share_a_budget_share_one_session_total():
    cap = {"arg": "amount", "over": 100, "then": "person", "budget": "money"}
    policy = {"refund": {"label": "auto", "session_total": cap}, "credit": {"label": "auto", "session_total": cap}}
    gate = Gate(policy, intent="pay")
    assert gate.decide("refund", {"amount": 80}, {}, []).allow
    assert not gate.decide("credit", {"amount": 80}, {}, []).allow


def test_a_bad_budget_name_is_refused():
    bad = {"pay": {"label": "commit", "session_total": {"arg": "amount", "over": 1, "then": "deny", "budget": 7}}}
    try:
        rules.validate(bad)
    except ValueError:
        return
    raise AssertionError("a budget that is not a name was accepted")


def timeout_server(ran):
    mcp = FastMCP("supplier")

    def place_order(supplier: str, amount: int, reference: str) -> str:
        ran.append(reference)
        if len(ran) == 1:
            raise TimeoutError("no reply, though the order went through")
        return "ordered"
    mcp.tool(place_order)
    return mcp


def test_after_a_call_with_no_clear_result_a_changed_retry_still_waits(tmp_path):
    ran = []
    policy = {"place_order": {"label": "auto", "rules": [{"arg": "amount", "over": 5000, "then": "person"}]}}

    async def go(state):
        async with Client(build(timeout_server(ran), policy, state, "Order parts", None, frozenset(), KEY)) as c:
            first = await c.call_tool("place_order", {"supplier": "N", "amount": 3000, "reference": "PO-1"},
                                      raise_on_error=False)
            assert first.is_error
            for changed in ({"reference": "PO-1 "}, {"amount": 3000.01}, {"reference": "PO-2"}):
                retry = await c.call_tool("place_order", {"supplier": "N", "amount": 3000, "reference": "PO-1",
                                                          **changed}, raise_on_error=False)
                assert retry.is_error and "HELD" in retry.content[0].text, changed
    asyncio.run(go(tmp_path))
    assert ran == ["PO-1"]


def test_any_failed_write_call_makes_the_next_one_wait(tmp_path):
    ran = []
    mcp = FastMCP("supplier")

    def place_order(amount: int) -> str:
        ran.append(amount)
        if amount == 1:
            raise ValueError("amount too small")
        return "ordered"
    mcp.tool(place_order)
    policy = {"place_order": {"label": "auto", "rules": [{"arg": "amount", "over": 5000, "then": "person"}]}}

    async def go(state):
        async with Client(build(mcp, policy, state, "Order parts", None, frozenset(), KEY)) as c:
            assert (await c.call_tool("place_order", {"amount": 1}, raise_on_error=False)).is_error
            retry = await c.call_tool("place_order", {"amount": 2}, raise_on_error=False)
            assert retry.is_error and "may still have gone through" in retry.content[0].text
    asyncio.run(go(tmp_path))
    assert ran == [1]


def test_the_request_file_is_read_again_on_every_call(tmp_path):
    mcp = FastMCP("shop")

    def refund(amount: int) -> str:
        return "refunded"
    mcp.tool(refund)
    intent = tmp_path / "request.txt"
    seen = []
    reviewer = (lambda request, *_: (seen.append(request), (True, "ok"))[1])
    proxy = build(mcp, {"refund": "commit"}, tmp_path / "state", None, reviewer, frozenset(), KEY, intent_file=intent)

    async def go():
        async with Client(proxy) as c:
            assert (await c.call_tool("refund", {"amount": 1}, raise_on_error=False)).is_error
            intent.write_text("Refund order A", encoding="utf-8")
            assert not (await c.call_tool("refund", {"amount": 2}, raise_on_error=False)).is_error
            intent.write_text("Refund order B", encoding="utf-8")
            assert not (await c.call_tool("refund", {"amount": 3}, raise_on_error=False)).is_error
    asyncio.run(go())
    assert seen == ["Refund order A", "Refund order B"]


def run_cli(*args):
    from holdpoint.cli import main
    try:
        main(list(args))
    except SystemExit as stop:
        return stop.code
    return 0


def test_approve_shows_the_exact_call_and_will_not_approve_blind(tmp_path, monkeypatch, capsys):
    from holdpoint.approval import Approvals
    monkeypatch.setenv("HOLDPOINT_KEY", KEY.decode())
    approvals = Approvals(tmp_path, KEY)
    hold_id = approvals.record_hold("send_payment", {"to": "Mallory", "amount": 9999}, "held")
    assert "--yes" in str(run_cli("--state-dir", str(tmp_path), "approve", hold_id))
    assert '"Mallory"' in capsys.readouterr().out and not list(approvals.tokens.glob("*.json"))
    assert run_cli("--state-dir", str(tmp_path), "approve", hold_id, "--yes") == 0
    assert len(list(approvals.tokens.glob("*.json"))) == 1


def test_an_approval_cannot_last_more_than_an_hour(tmp_path, monkeypatch):
    from holdpoint.approval import Approvals
    monkeypatch.setenv("HOLDPOINT_KEY", KEY.decode())
    hold_id = Approvals(tmp_path, KEY).record_hold("send_payment", {"amount": 1}, "held")
    assert run_cli("--state-dir", str(tmp_path), "approve", hold_id, "--ttl", "99999999", "--yes") == 2


def test_help_lists_every_command(capsys):
    run_cli("--help")
    out = capsys.readouterr().out
    assert all(name in out for name in ("prove", "draft-policy", "holds", "approve", "reject", "serve"))


def test_the_demo_card_filter_catches_any_separator():
    import pathlib

    import yaml
    policy = yaml.safe_load(pathlib.Path(__file__).parent.parent.joinpath("examples/shop_policy.yaml").read_text(encoding="utf-8"))
    entry = policy["send_email"]
    for card in ("4111 1111 1111 1111", "4111.1111.1111.1111", "4111/1111/1111/1111", "4111_1111_1111_1111",
                 "4111 - 1111 - 1111 - 1111", "4111111111111111"):
        assert rules.check(entry, {"to": "customer@shop.example", "body": f"card {card}"})[0] == "deny", card
    assert rules.check(entry, {"to": "customer@shop.example", "body": "Refund for O-101 on 2026-11-08, ticket 5521"}) is None
