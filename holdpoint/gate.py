"""The decision: may this tool call run now? Every path not proven safe holds."""
from collections import Counter
from dataclasses import dataclass

from . import checks
from .approval import call_hash

SAFE_LABELS = ("lookup", "verify")
# Each review is a fresh chance of a wrong "proceed", so retries must not buy more of them.
MAX_REVIEW_HOLDS_PER_TOOL = 3


@dataclass
class Decision:
    allow: bool
    by: str
    reason: str = ""
    usage: dict | None = None


class Gate:
    def __init__(self, policy: dict, approvals=None, reviewer=None, intent: str | None = None,
                 allow: frozenset = frozenset()):
        self.policy, self.approvals, self.reviewer = policy, approvals, reviewer
        self.intent, self.allow = intent, allow
        self.review_held: set[str] = set()
        self.review_holds = Counter()

    def is_commit(self, tool: str) -> bool:
        # Fail closed: an unnamed tool, or any label but an exact safe one, counts as irreversible.
        return self.policy.get(tool) not in SAFE_LABELS

    def decide(self, tool: str, args: dict, inventory: dict, trace: list[dict]) -> Decision:
        if tool in self.allow:
            return Decision(True, "allowlist")
        if not self.is_commit(tool):
            return Decision(True, "policy")
        if self.approvals is not None:
            hold_id = self.approvals.consume(tool, args)
            if hold_id:
                return Decision(True, "human", f"approval {hold_id}")
        if not self.intent:
            return Decision(False, "gate", "the user's request was not provided to the gate")
        reason = checks.unresolved_failure(tool, trace) or checks.missing_required_tool(self.intent, inventory)
        if reason:
            return Decision(False, "checks", reason)
        if self.reviewer is None:
            return Decision(False, "gate", "needs human approval")
        digest = call_hash(tool, args)
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
        return Decision(proceed, "reviewer", reason, getattr(self.reviewer, "last_usage", None))
