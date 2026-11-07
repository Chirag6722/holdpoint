"""Hard rules on a call's arguments. They read the call itself, so forged tool output cannot sway them.

A policy entry is a label, or a mapping:

    send_payment:
      label: commit
      rules:
        - {arg: amount, over: 500, then: deny}     # no approval can clear this
        - {arg: amount, over: 50, then: person}    # waits for a human, skips the reviewer
        - {arg: to, not_in: [Ann, Bob], then: person}
        - {arg: "*", pattern: "sk-[A-Za-z0-9]{8}", then: deny}
      session_total: {arg: amount, over: 200, then: person}

Anything a rule cannot read counts as a match, so a missing or malformed argument never slips past.
"""
import json
import re

AUTO_LABEL = "auto"  # Runs with no reviewer or person, but only while every hard rule is satisfied.
OUTCOMES = {"deny": 2, "person": 1}
RULE_KEYS = {"arg", "over", "not_in", "pattern", "then"}
ENTRY_KEYS = {"label", "rules", "session_total"}


def label_of(entry):
    return entry.get("label", "commit") if isinstance(entry, dict) else entry


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _within(value, limit) -> bool:
    # Written so that NaN, which compares false with everything, does not count as within.
    return _is_number(value) and value <= limit


def validate(policy: dict) -> None:
    """Refuse to start on a rule we cannot enforce, rather than silently ignoring it."""
    for tool, entry in policy.items():
        if label_of(entry) == AUTO_LABEL and not (isinstance(entry, dict) and (entry.get("rules") or entry.get("session_total"))):
            raise ValueError(f"{tool}: the auto label needs rules, or it would run anything")
        if not isinstance(entry, dict):
            continue
        if set(entry) - ENTRY_KEYS:
            raise ValueError(f"{tool}: unknown keys {sorted(set(entry) - ENTRY_KEYS)}")
        for rule in entry.get("rules", []):
            tests = {"over", "not_in", "pattern"} & set(rule)
            if set(rule) - RULE_KEYS or "arg" not in rule or len(tests) != 1 or rule.get("then") not in OUTCOMES:
                raise ValueError(f"{tool}: bad rule {rule}")
            if "over" in rule and not _is_number(rule["over"]):
                raise ValueError(f"{tool}: 'over' must be a number in {rule}")
            if "pattern" in rule:
                re.compile(rule["pattern"])
        total = entry.get("session_total")
        if total is not None and (set(total) != {"arg", "over", "then"} or total["then"] not in OUTCOMES
                                  or not _is_number(total["over"])):
            raise ValueError(f"{tool}: bad session_total {total}")


def _matches(rule: dict, args: dict) -> bool:
    if "pattern" in rule:
        text = json.dumps(args, default=str) if rule["arg"] == "*" else str(args.get(rule["arg"], ""))
        return re.search(rule["pattern"], text) is not None
    value = args.get(rule["arg"])
    if "over" in rule:
        return not _within(value, rule["over"])
    return value not in rule["not_in"]


def amount_of(entry, args: dict) -> float:
    """What this call adds to the session total. Unreadable amounts add nothing, because they are already held."""
    total = entry.get("session_total") if isinstance(entry, dict) else None
    value = args.get(total["arg"]) if total else None
    # Size, not sign: otherwise a negative amount would lower the total and open room for a larger one.
    return abs(value) if _within(value, float("inf")) else 0


def check(entry, args: dict, spent: float = 0) -> tuple[str, str] | None:
    """Return the strictest (outcome, reason) that applies, or None."""
    if not isinstance(entry, dict):
        return None
    hits = [(r["then"], f"rule on {r['arg']}: {_describe(r)}") for r in entry.get("rules", []) if _matches(r, args)]
    total = entry.get("session_total")
    if total:
        value = args.get(total["arg"])
        if not _is_number(value) or not _within(spent + abs(value), total["over"]):
            hits.append((total["then"], f"session total of {total['arg']} would pass {total['over']}"))
    return max(hits, key=lambda hit: OUTCOMES[hit[0]]) if hits else None


def _describe(rule: dict) -> str:
    if "over" in rule:
        return f"must be a number no more than {rule['over']}"
    if "not_in" in rule:
        return "must be on the allowed list"
    return "must not match the blocked pattern"
