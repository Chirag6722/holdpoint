"""Prove a limit for every possible call, or return the exact call that breaks it.

    holdpoint prove policy.yaml --tool issue_refund --never "amount > 500"

This turns a tool's hard rules into formulas and asks the z3 solver whether any call can run while
the claim is true. It covers every value, not a sample. Rules are the only thing it can reason about:
`pattern` rules are treated as passing anything, and the reviewer as saying yes to anything, so a
PROVED result never relies on either. It proves what someone wrote down, not that an agent is safe.

Reference: de Moura and Bjorner, Z3: An Efficient SMT Solver, TACAS 2008.
"""
import re
from dataclasses import dataclass

from . import rules
from .gate import PERSON_LABEL, Gate

OTHER = "__any_other_value__"
_NUMBER_CLAIM = re.compile(r"^\s*(\w+)\s*(>=|<=|>|<|==|!=)\s*(-?\d+(?:\.\d+)?)\s*$")
_LIST_CLAIM = re.compile(r"^\s*(\w+)\s+(not in|in)\s+\[(.*)\]\s*$")
ASSUMPTIONS = ("pattern rules are assumed to pass anything", "the reviewer is assumed to say yes to anything",
               "--allow flags are not considered, because they skip the rules on purpose")


@dataclass
class Result:
    proved: bool
    call: dict | None
    assumptions: tuple = ASSUMPTIONS


class _Encoder:
    """One argument is a number, one of the exact values the rules name, or anything else."""

    def __init__(self, z3, names: dict[str, list]):
        self.z3, self.tokens, self.number, self.value, self.choice = z3, {}, {}, {}, {}
        self.base = []
        for arg, items in names.items():
            # True equals 1 in Python, so booleans are their own values and are looked up as Python does.
            words = [i for i in items if not isinstance(i, (int, float)) or isinstance(i, bool)]
            if any(not isinstance(w, (str, bool)) and w is not None for w in words):
                raise ValueError(f"cannot model the allowed values of {arg}: only text, numbers and booleans are covered")
            self.tokens[arg] = [*dict.fromkeys(words + [True, False]), OTHER]
            self.number[arg] = z3.Bool(f"{arg}_is_number")
            self.value[arg] = z3.Real(f"{arg}_value")
            self.choice[arg] = z3.Int(f"{arg}_choice")
            self.base += [self.choice[arg] >= 0, self.choice[arg] < len(self.tokens[arg])]

    def within(self, arg, limit):
        return self.z3.And(self.number[arg], self.value[arg] <= limit)

    def size_within(self, arg, limit):
        value = self.value[arg]
        return self.z3.And(self.number[arg], value <= limit, -value <= limit)

    def listed(self, arg, items):
        z3 = self.z3
        numeric = [i for i in items if isinstance(i, (int, float))]
        words = [z3.And(z3.Not(self.number[arg]), self.choice[arg] == n)
                 for n, token in enumerate(self.tokens[arg]) if token != OTHER and token in items]
        return z3.Or(*[z3.And(self.number[arg], self.value[arg] == z3.RealVal(str(i))) for i in numeric if not isinstance(i, bool)],
                     *[z3.And(self.number[arg], self.value[arg] == int(i)) for i in numeric if isinstance(i, bool)], *words)

    def concrete(self, arg):
        if self.number_is_true(arg):
            value = self.model[self.value[arg]]
            as_float = float(value.numerator_as_long()) / float(value.denominator_as_long()) if value is not None else 0.0
            return int(as_float) if as_float == int(as_float) else as_float
        return self.tokens[arg][self.model.eval(self.choice[arg], model_completion=True).as_long()]

    def number_is_true(self, arg):
        return self.z3.is_true(self.model.eval(self.number[arg], model_completion=True))


def _import_z3():
    try:
        import z3
    except ImportError as exc:
        raise RuntimeError('the prover needs z3: pip install "holdpoint[prove]"') from exc
    return z3


def _named_args(entry, claim_arg=None, claim_items=()) -> dict[str, list]:
    names: dict[str, list] = {}
    if isinstance(entry, dict):
        for rule in entry.get("rules", []):
            if "pattern" not in rule:
                names.setdefault(rule["arg"], []).extend(rule.get("not_in", []))
        if entry.get("session_total"):
            names.setdefault(entry["session_total"]["arg"], [])
    if claim_arg:
        names.setdefault(claim_arg, []).extend(claim_items)
    return names


def _can_run(enc: _Encoder, entry, even_with_approval: bool):
    """The formula for: this call could run. Over-approximates only where ASSUMPTIONS says it does."""
    z3 = enc.z3
    if not isinstance(entry, dict):
        return z3.BoolVal(even_with_approval or rules.label_of(entry) != PERSON_LABEL)
    holds = []
    for rule in entry.get("rules", []):
        if "pattern" in rule or (even_with_approval and rule["then"] != "deny"):
            continue
        arg = rule["arg"]
        holds.append(enc.within(arg, z3.RealVal(str(rule["over"]))) if "over" in rule else enc.listed(arg, rule["not_in"]))
    total = entry.get("session_total")
    if total and (not even_with_approval or total["then"] == "deny"):
        # Any call that passes with something already spent also passes as the first call, so nothing spent is exact.
        holds.append(enc.size_within(total["arg"], z3.RealVal(str(total["over"]))))
    if not even_with_approval and rules.label_of(entry) == PERSON_LABEL:
        holds.append(z3.BoolVal(False))
    return z3.And(*holds) if holds else z3.BoolVal(True)


def parse_claim(claim: str):
    match = _NUMBER_CLAIM.match(claim)
    if match:
        # Kept as written: reading it as a float would round it, and could prove a claim that is false.
        return match.group(1), match.group(2), match.group(3)
    match = _LIST_CLAIM.match(claim)
    if match:
        items = [part.strip().strip("'\"") for part in match.group(3).split(",") if part.strip()]
        return match.group(1), match.group(2), items
    raise ValueError(f'cannot read the claim {claim!r}: use "amount > 500" or "to not in [Ann, Bob]"')


def _claim_formula(enc: _Encoder, parsed):
    z3 = enc.z3
    arg, op, operand = parsed
    if isinstance(operand, list):
        listed = enc.listed(arg, operand)
        return listed if op == "in" else z3.Not(listed)
    value, limit = enc.value[arg], z3.RealVal(str(operand))
    compare = {">": value > limit, ">=": value >= limit, "<": value < limit, "<=": value <= limit,
               "==": value == limit, "!=": value != limit}[op]
    return z3.And(enc.number[arg], compare)


def real_gate_runs(policy: dict, tool: str, args: dict, even_with_approval: bool = False) -> bool:
    """Ask the real gate on a fresh session, with a reviewer that says yes to anything."""
    class AlwaysApproved:
        @staticmethod
        def consume(_tool, _args):
            return "approved"
    approvals = AlwaysApproved() if even_with_approval else None
    reviewer = (lambda *_args: (True, "assumed yes"))
    return Gate(policy, approvals, reviewer, "any request").decide(tool, args, {}, []).allow


PLAIN_TEXT = ("", "ok", "x", "0", "plain text")


def _with_pattern_args(policy: dict, tool: str, call: dict, even_with_approval: bool) -> dict:
    """The model lets pattern rules pass anything, so a counterexample needs real text that passes them.

    A missing argument matches a pattern rule, so leaving it out would make the call fail on the real gate.
    """
    entry = policy.get(tool)
    names = [r["arg"] for r in entry.get("rules", []) if "pattern" in r and r["arg"] != "*"] if isinstance(entry, dict) else []
    for name in dict.fromkeys(names):
        if name in call:
            continue
        for text in PLAIN_TEXT:
            if real_gate_runs(policy, tool, {**call, name: text}, even_with_approval):
                call = {**call, name: text}
                break
    return call


def prove(policy: dict, tool: str, claim: str, even_with_approval: bool = False) -> Result:
    """PROVED means no call can run while the claim is true. Otherwise returns one that does, checked on the real gate."""
    z3 = _import_z3()
    rules.validate(policy)
    entry = policy.get(tool)
    parsed = parse_claim(claim)
    items = parsed[2] if isinstance(parsed[2], list) else []
    enc = _Encoder(z3, _named_args(entry, parsed[0], items))
    solver = z3.Solver()
    solver.add(*enc.base, _can_run(enc, entry, even_with_approval), _claim_formula(enc, parsed))
    answer = solver.check()
    if answer == z3.unsat:
        return Result(True, None)
    if answer != z3.sat:
        raise RuntimeError(f"the solver could not decide: {answer}")
    enc.model = solver.model()
    call = {arg: enc.concrete(arg) for arg in enc.tokens}
    call = _with_pattern_args(policy, tool, call, even_with_approval)
    if not real_gate_runs(policy, tool, call, even_with_approval):
        raise RuntimeError(f"the solver's counterexample {call} does not run on the real gate, so the model is wrong")
    return Result(False, call)


def model_says_runs(policy: dict, tool: str, args: dict, even_with_approval: bool = False) -> bool:
    """Evaluate the formula on one exact call. Used to test the model against the real gate."""
    z3 = _import_z3()
    entry = policy.get(tool)
    names = _named_args(entry)
    for arg, value in args.items():
        if arg in names and not isinstance(value, (int, float)) and not isinstance(value, str):
            raise ValueError("only numbers, booleans and strings are modelled")
    enc = _Encoder(z3, names)
    solver = z3.Solver()
    solver.add(*enc.base, _can_run(enc, entry, even_with_approval))
    for arg in names:
        value = args.get(arg, OTHER)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            solver.add(enc.number[arg], enc.value[arg] == z3.RealVal(str(value)))
        else:
            tokens = enc.tokens[arg]
            solver.add(z3.Not(enc.number[arg]), enc.choice[arg] == (tokens.index(value) if value in tokens else tokens.index(OTHER)))
    return solver.check() == z3.sat
