"""Problems found by an independent attack review on 8 Nov 2026. Each test reproduced its problem before the fix."""
import asyncio
import http.client
import json
import threading
from urllib.parse import urlsplit

import pytest
from fastmcp import Client, FastMCP

from holdpoint import rules
from holdpoint.approval import Approvals, call_hash
from holdpoint.approve_ui import make_server, render
from holdpoint.gate import Gate
from holdpoint.proxy import build

KEY = b"review-test-key"


def refund_server(ran):
    mcp = FastMCP("shop")

    def refund(order: str, amount: int) -> str:
        ran.append((order, amount))
        return "refunded"
    mcp.tool(refund)
    return mcp


async def hold_for(approvals, args):
    for _ in range(200):
        if [h for h in approvals.list_holds() if h["args"] == args]:
            break
        await asyncio.sleep(0.05)
    else:
        raise AssertionError(f"{args} was never held, so it ran without a person")
    return next(h for h in approvals.list_holds() if h["args"] == args)["hold_id"]


async def answered_while_waiting(client, approvals, args, approve):
    task = asyncio.create_task(client.call_tool("refund", args, raise_on_error=False))
    hold_id = await hold_for(approvals, args)
    if approve:
        approvals.approve(hold_id, 60)
    else:
        approvals.deny(hold_id)
    return await task


def test_deny_session_cap_holds_when_calls_are_approved_while_waiting(tmp_path):
    ran = []
    policy = {"refund": {"label": "commit", "session_total": {"arg": "amount", "over": 150, "then": "deny"}}}
    proxy = build(refund_server(ran), policy, tmp_path, "Refund orders", None, frozenset(), KEY, wait_seconds=10)
    approvals = Approvals(tmp_path, KEY)

    async def go():
        async with Client(proxy) as c:
            assert not (await answered_while_waiting(c, approvals, {"order": "A", "amount": 100}, True)).is_error
            second = await c.call_tool("refund", {"order": "B", "amount": 100}, raise_on_error=False)
            assert second.is_error and "No approval can clear this" in second.content[0].text
    asyncio.run(go())
    assert sum(a for _, a in ran) == 100


def test_amount_approved_while_waiting_counts_toward_the_session_total(tmp_path):
    ran = []
    policy = {"refund": {"label": "auto", "rules": [{"arg": "amount", "over": 100, "then": "person"}],
                         "session_total": {"arg": "amount", "over": 150, "then": "person"}}}
    proxy = build(refund_server(ran), policy, tmp_path, "Refund orders", None, frozenset(), KEY, wait_seconds=10)
    approvals = Approvals(tmp_path, KEY)

    async def go():
        async with Client(proxy) as c:
            assert not (await c.call_tool("refund", {"order": "A", "amount": 100}, raise_on_error=False)).is_error
            assert not (await answered_while_waiting(c, approvals, {"order": "B", "amount": 100}, True)).is_error
            # 200 has already gone out, so a small refund must now wait for a person, and here is rejected.
            assert (await answered_while_waiting(c, approvals, {"order": "C", "amount": 50}, False)).is_error
    asyncio.run(go())
    assert ran == [("A", 100), ("B", 100)]


def test_call_approved_while_waiting_cannot_then_repeat_unseen(tmp_path):
    ran, answers = [], [TimeoutError(), (True, "yes"), (True, "yes")]

    def reviewer(*_args):
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    proxy = build(refund_server(ran), {"refund": "commit"}, tmp_path, "Refund", reviewer, frozenset(), KEY, wait_seconds=10)
    approvals = Approvals(tmp_path, KEY)
    args = {"order": "A", "amount": 40}

    async def go():
        async with Client(proxy) as c:
            # The review is down, so a person approves the first refund while it waits.
            assert not (await answered_while_waiting(c, approvals, args, True)).is_error
            # The same refund again must not slip through, even though the reviewer now says yes.
            assert (await answered_while_waiting(c, approvals, args, False)).is_error
    asyncio.run(go())
    assert ran == [("A", 40)]


def test_waiting_does_not_call_the_reviewer_again_and_again(tmp_path):
    calls = []

    def outage(*_args):
        calls.append(1)
        raise TimeoutError

    proxy = build(refund_server([]), {"refund": "commit"}, tmp_path, "Refund", outage, frozenset(), KEY, wait_seconds=1)

    async def go():
        async with Client(proxy) as c:
            assert (await c.call_tool("refund", {"order": "A", "amount": 1}, raise_on_error=False)).is_error
    asyncio.run(go())
    assert len(calls) == 1


@pytest.mark.parametrize(("claim", "limit"), [("amount > 9007199254740995", 9007199254740996),
                                              ("amount > 99.99999999999999999", 100)])
def test_proof_uses_the_claims_exact_number(claim, limit):
    pytest.importorskip("z3")
    from holdpoint.prove import prove, real_gate_runs
    policy = {"pay": {"label": "auto", "rules": [{"arg": "amount", "over": limit, "then": "person"}]}}
    result = prove(policy, "pay", claim)
    assert result.proved is False
    assert real_gate_runs(policy, "pay", result.call)


@pytest.mark.parametrize("over", [float("inf"), float("nan"), float("-inf")])
def test_a_limit_that_is_not_a_finite_number_stops_startup(over):
    with pytest.raises(ValueError):
        rules.validate({"pay": {"rules": [{"arg": "amount", "over": over, "then": "deny"}]}})
    with pytest.raises(ValueError):
        rules.validate({"pay": {"session_total": {"arg": "amount", "over": over, "then": "deny"}}})


def test_proof_refuses_values_it_cannot_model_instead_of_crashing():
    pytest.importorskip("z3")
    from holdpoint.prove import prove
    with pytest.raises(ValueError, match="cannot model"):
        prove({"pay": {"rules": [{"arg": "to", "not_in": [["a"]], "then": "deny"}]}}, "pay", "amount > 1")


def test_same_number_written_differently_is_the_same_call():
    assert call_hash("refund", {"amount": 100}) == call_hash("refund", {"amount": 100.0})
    assert call_hash("refund", {"amount": 0}) == call_hash("refund", {"amount": -0.0})
    assert call_hash("refund", {"x": [1.0, {"y": 2.0}]}) == call_hash("refund", {"x": [1, {"y": 2}]})
    assert call_hash("refund", {"amount": 100}) != call_hash("refund", {"amount": 100.5})
    assert call_hash("refund", {"flag": True}) != call_hash("refund", {"flag": 1})


def test_duplicate_guard_sees_100_and_100_point_0_as_one_call():
    gate = Gate({"refund": {"label": "auto", "rules": [{"arg": "amount", "over": 100, "then": "person"}]}})
    assert gate.decide("refund", {"order": "A", "amount": 100}, {}, []).allow is True
    assert gate.decide("refund", {"order": "A", "amount": 100.0}, {}, []).allow is False


DENY_EVIL = {"rules": [{"arg": "to", "pattern": r"@evil\.com$", "then": "deny"}]}


@pytest.mark.parametrize("to", [["x@evil.com"], ["ok@shop.example", "x@evil.com"], {"primary": "x@evil.com"}])
def test_pattern_reaches_inside_lists_and_objects(to):
    assert rules.check(DENY_EVIL, {"to": to})[0] == "deny"


def test_star_pattern_matches_text_that_is_not_english():
    star = {"rules": [{"arg": "*", "pattern": "пароль", "then": "deny"}]}
    assert rules.check(star, {"body": "мой пароль 1234"})[0] == "deny"


def test_missing_argument_matches_a_pattern_rule():
    assert rules.check(DENY_EVIL, {})[0] == "deny"


def test_negative_control_pattern_still_lets_clean_values_through():
    assert rules.check(DENY_EVIL, {"to": ["ok@shop.example"]}) is None
    star = {"rules": [{"arg": "*", "pattern": "пароль", "then": "deny"}]}
    assert rules.check(star, {"body": "hello"}) is None


@pytest.mark.parametrize("by", ["floor", "pins", "labels"])
def test_hold_that_no_approval_can_clear_is_not_offered_for_approval(tmp_path, by):
    approvals = Approvals(tmp_path, KEY)
    hold_id = approvals.record_hold("refund", {"amount": 9999}, "refused", by=by)
    with pytest.raises(ValueError, match="cannot be approved"):
        approvals.approve(hold_id, 60)
    page = render(approvals.list_holds(), "tok")
    assert "Approve this exact call once" not in page and "cannot be approved" in page


def test_negative_control_ordinary_hold_is_still_offered_for_approval(tmp_path):
    approvals = Approvals(tmp_path, KEY)
    approvals.record_hold("refund", {"amount": 1}, "held", by="rules")
    assert "Approve this exact call once" in render(approvals.list_holds(), "tok")


def test_approval_screen_survives_a_bad_content_length(tmp_path):
    server, url = make_server(Approvals(tmp_path, KEY))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    parts = urlsplit(url)
    try:
        for bad in ("-5", "lots"):
            connection = http.client.HTTPConnection(parts.hostname, parts.port, timeout=5)
            connection.putrequest("POST", "/approve", skip_host=True)
            connection.putheader("Host", "127.0.0.1")
            connection.putheader("Content-Length", bad)
            connection.endheaders()
            assert connection.getresponse().status in (400, 403)
    finally:
        server.shutdown()


def test_hold_records_say_why_they_were_held(tmp_path):
    approvals = Approvals(tmp_path, KEY)
    approvals.record_hold("refund", {"amount": 1}, "held", by="rules")
    assert json.loads(next(approvals.pending.glob("*.json")).read_text(encoding="utf-8"))["by"] == "rules"
