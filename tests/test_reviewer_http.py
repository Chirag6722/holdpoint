"""The reviewer clients, against a local HTTP stub. Needs no keys or network."""
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from holdpoint.reviewer import AnthropicReviewer, HttpReviewer, reviewer_from_env


def serve(reply):
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            seen["path"] = self.path
            seen["headers"] = dict(self.headers)
            seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            data = json.dumps(reply).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{server.server_address[1]}", seen


def tool_use(decision, reason="r"):
    return {"type": "tool_use", "name": "verdict", "input": {"decision": decision, "reason": reason}}


def test_anthropic_reviewer_forces_the_verdict_and_sends_prompt_separately():
    url, seen = serve({"content": [tool_use("hold", "unclear")]})
    verdict = AnthropicReviewer(url, "k", "m")("Pay Ann", "send_payment", {"to": "Ann"}, [])
    assert verdict == (False, "unclear")
    assert seen["path"] == "/v1/messages"
    assert seen["headers"]["x-api-key"] == "k"
    assert seen["body"]["tool_choice"] == {"type": "tool", "name": "verdict"}
    assert "irreversible action" in seen["body"]["system"]
    assert [m["role"] for m in seen["body"]["messages"]] == ["user"]


def test_anthropic_reviewer_proceed():
    url, _ = serve({"content": [tool_use("proceed")]})
    assert AnthropicReviewer(url, "k", "m")("i", "t", {}, [])[0] is True


@pytest.mark.parametrize("content", [
    [],
    [{"type": "text", "text": '{"decision": "proceed", "reason": "r"}'}],
    [tool_use("yes")],
    [tool_use("proceed"), tool_use("proceed")],
    [{"type": "tool_use", "name": "other", "input": {"decision": "proceed", "reason": "r"}}],
])
def test_anthropic_reviewer_rejects_anything_but_one_valid_verdict(content):
    url, _ = serve({"content": content})
    with pytest.raises(ValueError):
        AnthropicReviewer(url, "k", "m")("i", "t", {}, [])


def test_openai_compatible_reviewer():
    url, seen = serve({"choices": [{"message": {"content": '{"decision": "proceed", "reason": "r"}'}}]})
    assert HttpReviewer(url, "k", "m")("i", "t", {}, []) == (True, "r")
    assert seen["path"] == "/chat/completions"
    assert seen["headers"]["Authorization"] == "Bearer k"


def test_reviewer_selection_from_environment(monkeypatch):
    for name in ("HOLDPOINT_REVIEWER_KEY", "HOLDPOINT_REVIEWER_MODEL", "HOLDPOINT_REVIEWER_PROVIDER"):
        monkeypatch.delenv(name, raising=False)
    assert reviewer_from_env() is None
    monkeypatch.setenv("HOLDPOINT_REVIEWER_KEY", "k")
    monkeypatch.setenv("HOLDPOINT_REVIEWER_MODEL", "m")
    assert isinstance(reviewer_from_env(), HttpReviewer)
    monkeypatch.setenv("HOLDPOINT_REVIEWER_PROVIDER", "anthropic")
    assert isinstance(reviewer_from_env(), AnthropicReviewer)
