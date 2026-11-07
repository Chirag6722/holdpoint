"""The browser page must run the real code, and its ready-made moves must do what they say."""
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PRESETS = json.loads((ROOT / "site" / "presets.json").read_text(encoding="utf-8"))


def load_playground():
    spec = importlib.util.spec_from_file_location("playground", ROOT / "site" / "playground.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("preset", PRESETS, ids=lambda p: p["id"])
def test_every_ready_made_move_does_what_the_page_says(preset):
    session = load_playground().Session((ROOT / preset["policy_file"]).read_text(encoding="utf-8"))
    for move in preset["moves"]:
        result = json.loads(session.call(move["tool"], json.dumps(move["args"])))
        assert result["outcome"] == move["expected"], (preset["id"], move["label"], result)


def test_person_can_approve_a_held_call_on_the_page():
    session = load_playground().Session("send_payment: commit\n")
    held = json.loads(session.call("send_payment", '{"to": "Ann", "amount": 1}'))
    assert held["outcome"] == "HELD"
    session.approve(held["hold"])
    assert json.loads(session.call("send_payment", '{"to": "Ann", "amount": 1}'))["outcome"] == "RAN"
    assert json.loads(session.call("send_payment", '{"to": "Ann", "amount": 1}'))["outcome"] == "HELD"


def test_changed_call_does_not_use_someone_elses_approval():
    session = load_playground().Session("send_payment: commit\n")
    held = json.loads(session.call("send_payment", '{"to": "Ann", "amount": 1}'))
    session.approve(held["hold"])
    assert json.loads(session.call("send_payment", '{"to": "Mallory", "amount": 1}'))["outcome"] == "HELD"


@pytest.mark.parametrize("text", ["just words", "t: {label: auto}", "t: {rules: [{arg: a, over: x, then: deny}]}"])
def test_a_policy_the_gate_cannot_enforce_is_refused_on_the_page(text):
    with pytest.raises(ValueError):
        load_playground().Session(text)


def test_arguments_must_be_an_object():
    session = load_playground().Session("t: commit\n")
    with pytest.raises(ValueError):
        session.call("t", "[1]")
    with pytest.raises(ValueError):
        session.call("t", "not json")


def test_published_page_embeds_exactly_the_repo_code():
    page_path = ROOT / "docs" / "index.html"
    if not page_path.exists():
        pytest.skip("no built page in this copy")
    page = page_path.read_text(encoding="utf-8")
    raw = re.search(r'<script type="application/json" id="playground-data">(.*?)</script>', page, re.DOTALL).group(1)
    data = json.loads(raw)
    assert "holdpoint/gate.py" in data["files"], "the gate must be embedded"
    for name, text in data["files"].items():
        source = ROOT / "site" / name if name == "playground.py" else ROOT / name
        assert text == source.read_text(encoding="utf-8").replace("\r\n", "\n"), f"{name} is stale: run python site/build.py"


def test_page_imports_nothing_outside_the_embedded_files():
    """Every holdpoint module the gate needs must be on the page, or it fails only in the browser."""
    embedded = {"approval", "checks", "gate", "rules"}
    for name in embedded:
        source = (ROOT / "holdpoint" / f"{name}.py").read_text(encoding="utf-8")
        for match in re.findall(r"^from \.(\w*) import ([\w, ]+)", source, re.MULTILINE):
            module, names = match
            needed = {module} if module else {n.strip() for n in names.split(",")}
            assert needed <= embedded, (name, needed)
