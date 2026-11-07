"""The decision: may this tool call run now? Every path not proven safe holds."""
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from . import checks
from .approval import call_hash

SAFE_LABELS = ("lookup", "verify")
PERSON_LABEL = "person"
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
                 allow: frozenset = frozenset(), review_state=None):
        self.policy, self.approvals, self.reviewer = policy, approvals, reviewer
        self.intent, self.allow = intent, allow
        self.review_state = Path(review_state) if review_state else None
        self.review_held: set[str] = set()
        self.review_holds = Counter()
        self._load_review_state()

    def _request_id(self) -> str:
        return hashlib.sha256((self.intent or "").encode("utf-8")).hexdigest()

    def _load_review_state(self) -> None:
        # Tied to the request, so restarting the proxy cannot buy more reviews, but a new request starts fresh.
        if self.review_state and self.review_state.exists():
            saved = json.loads(self.review_state.read_text(encoding="utf-8"))
            if saved["request"] == self._request_id():
                self.review_held, self.review_holds = set(saved["held"]), Counter(saved["holds"])

    def _save_review_state(self) -> None:
        if self.review_state:
            self.review_state.write_text(json.dumps({"request": self._request_id(), "held": sorted(self.review_held),
                                                     "holds": self.review_holds}), encoding="utf-8")

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
        # A reviewer can be fooled by forged tool output, so these tools never reach one.
        if self.reviewer is None or self.policy.get(tool) == PERSON_LABEL:
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
            self._save_review_state()
        return Decision(proceed, "reviewer", reason, getattr(self.reviewer, "last_usage", None))
