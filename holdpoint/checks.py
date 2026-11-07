"""Deterministic run checks. Each returns a reason to hold, or None."""
import re

_NAME = r"([a-z][a-z0-9]*(?:_[a-z0-9]+)+)"
_REQUIRED = [
    re.compile(rf"\b(?i:call|invoke)\s+(?i:the\s+)?[`'\"]?{_NAME}"),
    # "use store_credit" usually names a thing, not a tool, so "use" and "run" need quotes or the word "tool".
    re.compile(rf"\b(?i:use|run)\s+(?i:the\s+)?[`'\"]{_NAME}"),
    re.compile(rf"[`'\"]?{_NAME}[`'\"]?\s+tool\b"),
]


def unresolved_failure(tool: str, trace: list[dict]) -> str | None:
    """A different tool failed and has not succeeded since."""
    last = {}
    for entry in trace:
        last[entry["tool"]] = entry["ok"]
    failed = sorted(t for t, ok in last.items() if not ok and t != tool)
    return f"earlier tool call failed and never recovered: {', '.join(failed)}" if failed else None


def missing_required_tool(intent: str, inventory: set[str]) -> str | None:
    """The user's request names a tool to use that does not exist here."""
    available = {name.rsplit(".", 1)[-1] for name in inventory}
    named = {m for pattern in _REQUIRED for m in pattern.findall(intent)}
    missing = sorted(named - available)
    return f"request requires a tool that is not available: {', '.join(missing)}" if missing else None
