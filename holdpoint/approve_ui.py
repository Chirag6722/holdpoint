"""A local approval screen, for a person to approve or reject held calls.

Only answers on this machine, and only with the secret link it prints, so a web page in another
tab cannot approve a payment by posting to localhost. No dependencies. Run: holdpoint serve
"""
import hmac
import html
import json
import secrets
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlencode, urlparse

from .approval import UNAPPROVABLE

STYLE = """
:root{--paper:#dfe9e4;--sheet:#eef4f0;--ink:#12332d;--tag:#f4c20d;--line:#7b968d;--fail:#a4262c}
body{margin:0;background:var(--paper);color:var(--ink);font:400 1.05rem/1.5 system-ui,sans-serif}
main{max-width:760px;margin:0 auto;padding:32px 16px}
h1{font:400 2.4rem/1.1 Georgia,serif;margin:0 0 .4rem}
.hold{background:var(--sheet);border-top:6px solid var(--tag);padding:18px;margin-top:18px}
.tool{font:600 1.15rem Consolas,monospace;overflow-wrap:anywhere}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font:400 .95rem Consolas,monospace;margin:.6rem 0}
.why{color:#3f5b53}
form{display:inline}
button{font:600 1rem system-ui;padding:.5rem 1.1rem;border-radius:999px;border:2px solid var(--ink);cursor:pointer;margin:.5rem .5rem 0 0}
.approve{background:var(--ink);color:#fff}.reject{background:none;color:var(--fail);border-color:var(--fail)}
.done{font-weight:600;color:#0b6e4f;margin:.5rem 0}
.msg{background:var(--sheet);border-left:6px solid var(--fail);padding:10px 14px;margin-top:14px}
:focus-visible{outline:3px solid var(--ink);outline-offset:2px}
"""


def render(holds: list[dict], token: str, message: str = "", approved: frozenset | set = frozenset()) -> str:
    e = lambda text: html.escape(str(text), quote=True)
    cards = ""
    for hold in sorted(holds, key=lambda h: h["at"]):
        when = time.strftime("%H:%M:%S", time.localtime(hold["at"]))
        fields = "".join(f"<input type='hidden' name='{k}' value='{e(v)}'>"
                         for k, v in (("token", token), ("hold", hold["hold_id"])))
        approve = ("<p class='done'>This call cannot be approved. It needs a change to the policy or the tools.</p>"
                   if hold.get("by") in UNAPPROVABLE else
                   "<p class='done'>Approved. It runs once if the agent asks again. Reject cancels this.</p>"
                   if hold["hold_id"] in approved else
                   f"<form method='post' action='/approve'>{fields}<button class='approve'>Approve this exact call once</button></form>")
        cards += (f"<section class='hold'><div class='tool'>{e(hold['tool'])}</div>"
                  f"<pre>{e(json.dumps(hold['args'], indent=1, sort_keys=True))}</pre>"
                  f"<p class='why'>Held at {when}. {e(hold['reason'])}</p>{approve}"
                  f"<form method='post' action='/reject'>{fields}<button class='reject'>Reject</button></form></section>")
    note = f"<p class='msg' role='status'>{e(message)}</p>" if message else ""
    body = cards or "<p>Nothing is waiting for approval.</p>"
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<meta http-equiv='refresh' content='5; url=/?token={e(quote(token))}'><meta name='referrer' content='no-referrer'><title>Holdpoint approvals</title><style>{STYLE}</style></head>"
            f"<body><main><h1>Waiting for you</h1><p>Approving runs that exact call once, within {APPROVAL_TTL_SECONDS // 60} minutes.</p>{note}{body}</main></body></html>")


APPROVAL_TTL_SECONDS = 300


def make_server(approvals, port: int = 0):
    token = secrets.token_urlsafe(24)

    class Handler(BaseHTTPRequestHandler):
        def _trusted(self, supplied: str) -> bool:
            # The host check stops another site reaching this server through a rebinding DNS name.
            host = self.headers.get("Host", "").rsplit(":", 1)[0]
            return host in ("127.0.0.1", "localhost") and hmac.compare_digest(supplied.encode(), token.encode())

        def _send(self, code: int, text: str) -> None:
            data = text.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            query = parse_qs(urlparse(self.path).query)
            if urlparse(self.path).path != "/" or not self._trusted(query.get("token", [""])[0]):
                return self._send(403, "Forbidden. Use the link the command printed.")
            return self._send(200, render(approvals.list_holds(), token, query.get("msg", [""])[0], approvals.approved_ids()))

        def do_POST(self):
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return self._send(400, "Bad request.")
            if not 0 <= length <= 4096:
                return self._send(400, "Bad request.")
            form = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
            if not self._trusted(form.get("token", [""])[0]):
                return self._send(403, "Forbidden.")
            hold = form.get("hold", [""])[0]
            message = ""
            try:
                if self.path == "/approve":
                    approvals.approve(hold, APPROVAL_TTL_SECONDS)
                elif self.path == "/reject":
                    approvals.deny(hold)
                else:
                    return self._send(404, "Not found.")
            except (ValueError, OSError) as exc:
                message = str(exc)
            # Redirect, so a refresh of this page can never send the approval again.
            self.send_response(303)
            self.send_header("Location", f"/?{urlencode({'token': token, 'msg': message})}")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    return server, f"http://127.0.0.1:{server.server_address[1]}/?token={token}"
