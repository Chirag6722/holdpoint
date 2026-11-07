"""The proof must agree with the real gate. A proof of the wrong model is worse than no proof."""
import random
from pathlib import Path

import pytest
import yaml

from holdpoint.cli import prove_command
from holdpoint.prove import model_says_runs, parse_claim, prove, real_gate_runs

pytest.importorskip("z3")

SHOP = yaml.safe_load((Path(__file__).parent.parent / "examples" / "shop_policy.yaml").read_text(encoding="utf-8"))
SEED = 20261107
DIFFERENTIAL_CASES = 2000


def test_shop_policy_refund_over_the_limit_can_never_run_without_a_person():
    assert prove(SHOP, "issue_refund", "amount > 50").proved is True


def test_shop_policy_refund_over_the_hard_cap_can_never_run_even_with_approval():
    assert prove(SHOP, "issue_refund", "amount > 500", even_with_approval=True).proved is True


def test_person_can_approve_between_the_limits_so_that_claim_escapes_and_is_real():
    result = prove(SHOP, "issue_refund", "amount > 50", even_with_approval=True)
    assert result.proved is False
    assert real_gate_runs(SHOP, "issue_refund", result.call, even_with_approval=True) is True
    assert result.call["amount"] > 50


def test_loosening_a_limit_returns_the_exact_call_that_escapes():
    loose = yaml.safe_load(yaml.safe_dump(SHOP))
    loose["issue_refund"]["rules"][1]["over"] = 80
    loose["issue_refund"]["session_total"]["over"] = 1000
    result = prove(loose, "issue_refund", "amount > 50")
    assert result.proved is False and 50 < result.call["amount"] <= 80
    assert real_gate_runs(loose, "issue_refund", result.call) is True


def test_recipient_claim_is_proved_and_breaks_when_the_rule_is_removed():
    assert prove(SHOP, "send_email", "to not in [customer@shop.example]").proved is True
    loose = {"send_email": {"label": "auto", "rules": [{"arg": "body", "pattern": "x", "then": "deny"}]}}
    assert prove(loose, "send_email", "to not in [customer@shop.example]").proved is False


def test_a_person_label_never_runs_without_a_person_whatever_the_call():
    assert prove({"pay": "person"}, "pay", "amount > 0").proved is True
    assert prove({"pay": "person"}, "pay", "amount > 0", even_with_approval=True).proved is False


@pytest.mark.parametrize("policy", [{"pay": "commit"}, {}, {"pay": "lookup"}])
def test_no_rules_means_no_proof(policy):
    assert prove(policy, "pay", "amount > 0").proved is False


def test_a_rule_that_is_only_a_pattern_is_not_relied_on():
    policy = {"pay": {"rules": [{"arg": "amount", "pattern": "^9", "then": "deny"}]}}
    assert prove(policy, "pay", "amount > 0").proved is False


def test_session_total_also_bounds_a_single_call_in_both_directions():
    policy = {"pay": {"session_total": {"arg": "amount", "over": 100, "then": "person"}}}
    assert prove(policy, "pay", "amount > 100").proved is True
    assert prove(policy, "pay", "amount < -100").proved is True
    assert prove(policy, "pay", "amount == 100").proved is False


def test_deny_session_total_holds_even_with_approval():
    policy = {"pay": {"session_total": {"arg": "amount", "over": 100, "then": "deny"}}}
    assert prove(policy, "pay", "amount > 100", even_with_approval=True).proved is True


def test_claims_that_cannot_be_read_are_refused():
    with pytest.raises(ValueError, match="cannot read"):
        parse_claim("amount is big")


def test_boolean_is_looked_up_the_way_python_does():
    policy = {"pay": {"rules": [{"arg": "flag", "not_in": [1], "then": "deny"}]}}
    assert real_gate_runs(policy, "pay", {"flag": True}) is True
    assert model_says_runs(policy, "pay", {"flag": True}) is True
    assert model_says_runs(policy, "pay", {"flag": False}) is False


def test_cli_exit_codes(tmp_path, capsys):
    path = tmp_path / "p.yaml"
    path.write_text(yaml.safe_dump(SHOP), encoding="utf-8")
    with pytest.raises(SystemExit) as stop:
        prove_command([str(path), "--tool", "issue_refund", "--never", "amount > 50"])
    assert stop.value.code == 0 and "PROVED" in capsys.readouterr().out
    with pytest.raises(SystemExit) as stop:
        prove_command([str(path), "--tool", "issue_refund", "--never", "amount > 50", "--even-with-approval"])
    assert stop.value.code == 1 and "ESCAPE" in capsys.readouterr().out
    with pytest.raises(SystemExit) as stop:
        prove_command([str(path), "--tool", "issue_refund", "--never", "nonsense"])
    assert stop.value.code == 2


WORDS = ["Ann", "Bob", "Cy", "", "__x__"]
NUMBERS = [0, 1, -1, 2, 10, 50, 50.5, 100, 500, 1000, -500, 0.1, 3.25]


def random_policy(rng):
    rule_list = []
    for _ in range(rng.randint(0, 3)):
        then = rng.choice(["deny", "person"])
        if rng.random() < 0.6:
            rule_list.append({"arg": rng.choice(["a", "b"]), "over": rng.choice(NUMBERS), "then": then})
        else:
            items = rng.sample(WORDS, rng.randint(0, 3)) + rng.sample(NUMBERS, rng.randint(0, 2)) + ([True] if rng.random() < 0.1 else [])
            rule_list.append({"arg": rng.choice(["a", "b"]), "not_in": items, "then": then})
    entry = {"label": rng.choice(["commit", "lookup", "verify", "person"]), "rules": rule_list}
    if rule_list and rng.random() < 0.3:
        entry["label"] = "auto"
    if rng.random() < 0.4:
        entry["session_total"] = {"arg": rng.choice(["a", "b"]), "over": rng.choice([n for n in NUMBERS if n >= 0]), "then": rng.choice(["deny", "person"])}
        if entry["label"] == "auto":
            entry["rules"] = rule_list
    if entry["label"] == "auto" and not (entry["rules"] or entry.get("session_total")):
        entry["label"] = "commit"
    return {"t": entry}


def random_call(rng):
    args = {}
    for name in ("a", "b"):
        roll = rng.random()
        if roll < 0.55:
            args[name] = rng.choice(NUMBERS + [n + 0.5 for n in NUMBERS])
        elif roll < 0.8:
            args[name] = rng.choice(WORDS + ["other"])
        elif roll < 0.9:
            args[name] = rng.choice([True, False])
    return args


@pytest.mark.parametrize("even_with_approval", [False, True])
def test_model_and_real_gate_agree_on_random_policies_and_calls(even_with_approval):
    rng = random.Random(SEED + even_with_approval)
    for _ in range(DIFFERENTIAL_CASES):
        policy, args = random_policy(rng), random_call(rng)
        real = real_gate_runs(policy, "t", args, even_with_approval)
        model = model_says_runs(policy, "t", args, even_with_approval)
        assert real == model, (policy, args, even_with_approval)


def test_nothing_the_solver_rules_out_ever_runs_and_every_escape_really_runs():
    rng = random.Random(SEED + 7)
    proved = escaped = 0
    for _ in range(DIFFERENTIAL_CASES):
        policy = random_policy(rng)
        limit = rng.choice(NUMBERS)
        even = rng.random() < 0.3
        result = prove(policy, "t", f"a > {limit}", even)
        if result.proved:
            proved += 1
            for _ in range(8):
                args = random_call(rng)
                args["a"] = limit + abs(rng.choice(NUMBERS)) + 0.25
                assert real_gate_runs(policy, "t", args, even) is False, (policy, args, limit, even)
        else:
            escaped += 1
            assert real_gate_runs(policy, "t", result.call, even) is True
            assert result.call["a"] > limit
    assert proved > 100 and escaped > 100, (proved, escaped)
