"""The browser page's link to the real gate. Runs under Pyodide on the page, and under Python in the tests."""
import json
import tempfile

import yaml

from holdpoint import rules
from holdpoint.approval import Approvals
from holdpoint.gate import Gate

KEY = b"browser-playground-only"


class Session:
    """One fresh gate. There is no reviewer in the browser, so a plain commit always waits for a person."""

    def __init__(self, policy_text: str):
        policy = yaml.safe_load(policy_text)
        if not isinstance(policy, dict):
            raise ValueError("The policy must be a list of tools and their labels.")  # noqa: TRY004 - shown to a person
        rules.validate(policy)
        self.approvals = Approvals(tempfile.mkdtemp(), KEY)
        self.gate = Gate(policy, self.approvals, None, "The user's request.")

    def call(self, tool: str, args_json: str) -> str:
        try:
            args = json.loads(args_json)
        except ValueError:
            raise ValueError("The arguments are not valid JSON.") from None
        if not isinstance(args, dict):
            raise ValueError("The arguments must be a JSON object.")  # noqa: TRY004 - shown to a person
        decision = self.gate.decide(tool, args, {}, [])
        outcome = "RAN" if decision.allow else "REFUSED" if decision.by == "floor" else "HELD"
        hold_id = self.approvals.record_hold(tool, args, decision.reason) if outcome == "HELD" else None
        return json.dumps({"outcome": outcome, "by": decision.by, "reason": decision.reason, "hold": hold_id})

    def approve(self, hold_id: str) -> None:
        self.approvals.approve(hold_id, 3600)
