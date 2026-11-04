"""The decision: may this tool call run now? Every path not proven safe holds."""
from dataclasses import dataclass

from . import checks


@dataclass
class Decision:
    allow: bool
    by: str
    reason: str = ""


class Gate:
    def __init__(self, policy: dict, approvals=None, reviewer=None, intent: str | None = None,
                 allow: frozenset = frozenset()):
        self.policy, self.approvals, self.reviewer = policy, approvals, reviewer
        self.intent, self.allow = intent, allow

    def is_commit(self, tool: str) -> bool:
        # Fail closed: a tool the policy does not name counts as irreversible.
        return self.policy.get(tool, "commit") == "commit"

    def decide(self, tool: str, args: dict, inventory: set[str], trace: list[dict]) -> Decision:
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
        try:
            proceed, reason = self.reviewer(self.intent, tool, args, trace)
        except Exception as exc:  # noqa: BLE001 - any review failure must hold
            return Decision(False, "reviewer", f"review unavailable: {type(exc).__name__}")
        return Decision(proceed, "reviewer", reason)
