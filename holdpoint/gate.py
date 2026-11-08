"""The decision: may this tool call run now? Every path not proven safe holds."""
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from . import checks, rules
from .approval import call_hash

SAFE_LABELS = ("lookup", "verify")
PERSON_LABEL = "person"
# Each review is a fresh chance of a wrong "proceed", so retries must not buy more of them.
MAX_REVIEW_HOLDS_PER_TOOL = 3
MAX_TOOL_FAILURES = 3


@dataclass
class Decision:
    allow: bool
    by: str
    reason: str = ""
    usage: dict | None = None


class Gate:
    def __init__(self, policy: dict, approvals=None, reviewer=None, intent: str | None = None,
                 allow: frozenset = frozenset(), review_state=None):
        self.policy, self.approvals, self.reviewer = policy, approvals, reviewer
        self.intent, self.allow = intent, allow
        self.review_state = Path(review_state) if review_state else None
        self.review_held: set[str] = set()
        self.review_holds = Counter()
        self.totals = Counter()
        self.executed: set[str] = set()
        self._load_review_state()

    def _request_id(self) -> str:
        return hashlib.sha256((self.intent or "").encode("utf-8")).hexdigest()

    def _load_review_state(self) -> None:
        # Tied to the request, so restarting the proxy cannot buy more reviews, but a new request starts fresh.
        if self.review_state and self.review_state.exists():
            saved = json.loads(self.review_state.read_text(encoding="utf-8"))
            if saved["request"] == self._request_id():
                self.review_held, self.review_holds = set(saved["held"]), Counter(saved["holds"])
                self.totals = Counter(saved["totals"])
                self.executed = set(saved["executed"])

    def _save_review_state(self) -> None:
        if self.review_state:
            self.review_state.write_text(json.dumps({"request": self._request_id(), "held": sorted(self.review_held),
                                                     "holds": self.review_holds, "totals": self.totals,
                                                     "executed": sorted(self.executed)}), encoding="utf-8")

    def is_commit(self, tool: str) -> bool:
        # Fail closed: an unnamed tool, or any label but an exact safe one, counts as irreversible.
        return rules.label_of(self.policy.get(tool)) not in SAFE_LABELS

    def _allowed(self, tool: str, args: dict, by: str, reason: str = "", usage=None) -> Decision:
        if self.is_commit(tool):
            # Counted when allowed, so a timeout that may have charged still blocks a silent retry.
            self.executed.add(call_hash(tool, args))
        amount = rules.amount_of(self.policy.get(tool), args)
        if amount:
            self.totals[rules.budget_of(self.policy.get(tool), tool)] += amount
        self._save_review_state()
        return Decision(True, by, reason, usage)

    def decide(self, tool: str, args: dict, inventory: dict, trace: list[dict]) -> Decision:
        entry = self.policy.get(tool)
        ruling = rules.check(entry, args, self.totals[rules.budget_of(entry, tool)])
        if ruling and ruling[0] == "deny":
            return Decision(False, "floor", f"{ruling[1]}. No approval can clear this.")
        if tool in self.allow:
            # Skips everything but the floor, which nothing may skip.
            return Decision(True, "allowlist")
        if not ruling and not self.is_commit(tool):
            return self._allowed(tool, args, "policy")
        if self.approvals is not None:
            hold_id = self.approvals.consume(tool, args)
            if hold_id:
                return self._allowed(tool, args, "human", f"approval {hold_id}")
        if ruling:
            return Decision(False, "rules", f"{ruling[1]}, so it needs human approval")
        digest = call_hash(tool, args)
        if digest in self.executed:
            return Decision(False, "gate", "this exact call already ran this session, so running it again needs human approval")
        last = next((e for e in reversed(trace) if e["tool"] == tool), None)
        if self.is_commit(tool) and last is not None and not last["ok"]:
            # A server can fail after the change was made, for example a timeout after a payment went through.
            # A retry with any small difference would pass the duplicate check, so every retry waits.
            return Decision(False, "gate", "the last call to this tool failed, and it may still have gone through, "
                                           "so the next one needs human approval")
        if sum(e["tool"] == tool and not e["ok"] for e in trace) >= MAX_TOOL_FAILURES:
            return Decision(False, "gate", f"this tool has failed {MAX_TOOL_FAILURES} times this session, so it needs human approval")
        if rules.label_of(self.policy.get(tool)) == rules.AUTO_LABEL:
            return self._allowed(tool, args, "auto", "inside every hard rule")
        if not self.intent:
            return Decision(False, "gate", "the user's request was not provided to the gate")
        reason = checks.unresolved_failure(tool, trace) or checks.missing_required_tool(self.intent, inventory)
        if reason:
            return Decision(False, "checks", reason)
        # A reviewer can be fooled by forged tool output, so these tools never reach one.
        if self.reviewer is None or rules.label_of(self.policy.get(tool)) == PERSON_LABEL:
            return Decision(False, "gate", "needs human approval")
        if digest in self.review_held:
            return Decision(False, "gate", "review already held this exact call, so it needs human approval")
        if self.review_holds[tool] >= MAX_REVIEW_HOLDS_PER_TOOL:
            return Decision(False, "gate", "review has held this tool repeatedly, so it needs human approval")
        try:
            proceed, reason = self.reviewer(self.intent, tool, args, trace, inventory.get(tool))
        except Exception as exc:  # noqa: BLE001 - any review failure must hold
            return Decision(False, "reviewer", f"review unavailable: {type(exc).__name__}")
        if not proceed:
            self.review_held.add(digest)
            self.review_holds[tool] += 1
            self._save_review_state()
            return Decision(False, "reviewer", reason, getattr(self.reviewer, "last_usage", None))
        return self._allowed(tool, args, "reviewer", reason, getattr(self.reviewer, "last_usage", None))
