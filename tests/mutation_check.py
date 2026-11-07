"""Break each protection in a temporary copy and confirm the tests notice.

Run: python tests/mutation_check.py [OUT.json]. A surviving mutant is a protection no test covers.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MUTANTS = [
    ("commit tools not gated", "gate.py", "return rules.label_of(self.policy.get(tool)) not in SAFE_LABELS", "return False"),
    ("unknown tools treated as safe", "gate.py", "rules.label_of(self.policy.get(tool)) not in SAFE_LABELS",
     'rules.label_of(self.policy.get(tool, "lookup")) not in SAFE_LABELS'),
    ("mistyped labels pass", "gate.py", "rules.label_of(self.policy.get(tool)) not in SAFE_LABELS",
     'rules.label_of(self.policy.get(tool, "commit")) == "commit"'),
    ("deny rule ignored", "gate.py", 'if ruling and ruling[0] == "deny":', "if False:"),
    ("person rule ignored", "gate.py", 'if ruling:\n            return Decision(False, "rules"', 'if False:\n            return Decision(False, "rules"'),
    ("rules skipped on safe labels", "gate.py", "if not ruling and not self.is_commit(tool):", "if not self.is_commit(tool):"),
    ("mapping without label is safe", "rules.py", 'entry.get("label", "commit")', 'entry.get("label", "lookup")'),
    ("bad rules start anyway", "proxy.py", "    validate_rules(policy)\n", ""),
    ("missing amount counts as small", "rules.py", 'return not _within(value, rule["over"])', 'return _is_number(value) and value > rule["over"]'),
    ("true counts as a number", "rules.py", "and not isinstance(value, bool)", ""),
    ("list check off", "rules.py", 'return value not in rule["not_in"]', "return False"),
    ("pattern ignores other arguments", "rules.py", 'json.dumps(args, default=str) if rule["arg"] == "*" else ', ""),
    ("session total off", "rules.py", 'if not _is_number(value) or not _within(spent + abs(value), total["over"]):', "if False:"),
    ("large negative passes the total", "rules.py", "_within(spent + abs(value), total", "_within(spent + value, total"),
    ("negative amount lowers the total", "rules.py", 'return abs(value) if _within(value, float("inf")) else 0', 'return value if _within(value, float("inf")) else 0'),
    ("session total not counted", "gate.py", "self.totals[tool] += amount", "pass"),
    ("session total lost on restart", "gate.py", 'self.totals = Counter(saved["totals"])', "pass"),
    ("milder rule wins", "rules.py", "return max(hits,", "return min(hits,"),
    ("floor refusal waits for a person", "proxy.py", '("pins", "labels", "floor")', '("pins", "labels")'),
    ("held call reviewed again", "gate.py", "if digest in self.review_held:", "if False:"),
    ("no limit on repeated holds", "gate.py", "if self.review_holds[tool] >= MAX_REVIEW_HOLDS_PER_TOOL:", "if False:"),
    ("review outage sticks", "gate.py", 'return Decision(False, "reviewer", f"review unavailable: {type(exc).__name__}")',
     'self.review_held.add(digest)\n            return Decision(False, "reviewer", "review unavailable")'),
    ("audit log not signed", "audit.py",
     "return hmac.new(log_key, data, hashlib.sha256).hexdigest() if log_key else hashlib.sha256(data).hexdigest()",
     "return hashlib.sha256(data).hexdigest()"),
    ("signed head not checked", "audit.py", "if log_key and n and not _head_matches(path, log_key, n, prev):", "if False:"),
    ("empty log with a head accepted", "audit.py", "if not n and _head_path(path).exists():", "if False:"),
    ("saved hash ignored", "audit.py", "if expect and not seen:", "if False:"),
    ("edited hold approved", "approval.py",
     'if not hmac.compare_digest(str(record.get("mac")), self._hold_mac(hold_id, record["tool"], record["args"])):', "if False:"),
    ("hold id not checked", "approval.py",
     ('if not HOLD_ID.fullmatch(hold_id):\n            raise ValueError("not a hold id")\n        path = self.pending / f"{hold_id}.json"\n'
      '        if not path.exists():\n            raise ValueError("no pending hold with that id; it may already be used")\n        record'),
     ('path = self.pending / f"{hold_id}.json"\n'
      '        if not path.exists():\n            raise ValueError("no pending hold with that id; it may already be used")\n        record')),
    ("used hold stays pending", "approval.py", 'os.replace(hold, hold.with_suffix(".used"))', "pass"),
    ("person label goes to the reviewer", "gate.py", "if self.reviewer is None or rules.label_of(self.policy.get(tool)) == PERSON_LABEL:",
     "if self.reviewer is None:"),
    ("retry limits lost on restart", "gate.py", 'if saved["request"] == self._request_id():', "if False:"),
    ("retry limits survive a new request", "gate.py", 'if saved["request"] == self._request_id():', "if True:"),
    ("server's danger admission ignored", "proxy.py", "and admits_it_changes_things(match):", "and False:"),
    ("read-only false ignored", "proxy.py", 'or hint(annotations, "read_only_hint", "readOnlyHint") is False', ""),
    ("only one hint spelling read", "proxy.py", "snake if hasattr(annotations, snake) else camel", "camel"),
    ("redaction skipped", "proxy.py", "logged_args = redact(args, self.redact_args)", "logged_args = args"),
    ("nothing waits for a person", "proxy.py", "while time.monotonic() < deadline:", "while False:"),
    ("waiting call runs without approval", "proxy.py", "if self.approvals.consume(tool, args):\n                return True",
     "if True:\n                return True"),
    ("approval clears a changed tool", "proxy.py", 'if decision.by in ("pins", "labels", "floor") or not await', "if not await"),
    ("auto runs with no rules", "rules.py", 'if label_of(entry) == AUTO_LABEL and not (', "if False and not ("),
    ("auto ignores its person rule", "gate.py", 'if ruling:\n            return Decision(False, "rules"', 'if ruling and rules.label_of(self.policy.get(tool)) != rules.AUTO_LABEL:\n            return Decision(False, "rules"'),
    ("same call runs twice", "gate.py", "if digest in self.executed:", "if False:"),
    ("executed calls forgotten on restart", "gate.py", 'self.executed = set(saved["executed"])', "pass"),
    ("repeated reads blocked", "gate.py", "        if self.is_commit(tool):\n            # Counted", "        if True:\n            # Counted"),
    ("circuit breaker off", "gate.py", 'if sum(e["tool"] == tool and not e["ok"] for e in trace) >= MAX_TOOL_FAILURES:', "if False:"),
    ("breaker counts every tool", "gate.py", 'e["tool"] == tool and not e["ok"]', 'not e["ok"]'),
    ("rejected hold can be approved", "approval.py", 'os.replace(path, path.with_suffix(".denied"))', "pass"),
    ("rejected id not checked", "approval.py", 'if not HOLD_ID.fullmatch(hold_id):\n            raise ValueError("not a hold id")\n        path = self.pending / f"{hold_id}.json"\n        if not path.exists():\n            raise ValueError("no pending hold with that id; it may already be used")\n        # Cancel', 'path = self.pending / f"{hold_id}.json"\n        if not path.exists():\n            raise ValueError("no pending hold with that id; it may already be used")\n        # Cancel'),
    ("waiting ignores a rejection", "proxy.py", "if self.approvals.was_denied(hold_id):\n                return False", "if False:\n                return False"),
    ("success outcome not logged", "proxy.py", 'self.audit.append(tool=tool, by="outcome", allow=True, ok=ok)', "pass"),
    ("failure outcome not logged", "proxy.py", 'self.audit.append(tool=tool, by="outcome", allow=True, ok=False)', "pass"),
    ("screen needs no secret", "approve_ui.py", "and hmac.compare_digest(supplied.encode(), token.encode())", ""),
    ("screen answers any host", "approve_ui.py", 'return host in ("127.0.0.1", "localhost") and', "return"),
    ("proof proves everything", "prove.py", "if answer == z3.unsat:", "if True:"),
    ("model ignores its limits", "prove.py",
     'holds.append(enc.within(arg, z3.RealVal(str(rule["over"]))) if "over" in rule else enc.listed(arg, rule["not_in"]))', "pass"),
    ("model lists no allowed values", "prove.py", 'else enc.listed(arg, rule["not_in"]))', "else z3.BoolVal(True))"),
    ("model ignores large negatives", "prove.py", "value <= limit, -value <= limit)", "value <= limit)"),
    ("model ignores the session total", "prove.py", 'holds.append(enc.size_within(total["arg"], z3.RealVal(str(total["over"]))))', "pass"),
    ("model lets a person label run", "prove.py", "if not even_with_approval and rules.label_of(entry) == PERSON_LABEL:", "if False:"),
    ("plain person label runs in the model", "prove.py", "even_with_approval or rules.label_of(entry) != PERSON_LABEL", "True"),
    ("approval skips person rules wrongly", "prove.py", 'or (even_with_approval and rule["then"] != "deny")', ""),
    ("approval ignores deny total", "prove.py", 'if total and (not even_with_approval or total["then"] == "deny"):', "if total and not even_with_approval:"),
    ("booleans treated as numbers", "prove.py", "for i in numeric if isinstance(i, bool)]", "for i in numeric if False]"),
    ("claim direction flipped", "prove.py", '{">": value > limit,', '{">": value < limit,'),
    ("list claim flipped", "prove.py", 'return listed if op == "in" else z3.Not(listed)', 'return z3.Not(listed) if op == "in" else listed'),
    ("prove exit code always ok", "cli.py", "sys.exit(0 if result.proved else 1)", "sys.exit(0)"),
    ("reject leaves the approval live", "approval.py", '(self.tokens / f"{hold_id}.json").unlink(missing_ok=True)', "pass"),
    ("screen hides that it is approved", "approve_ui.py", 'if hold["hold_id"] in approved else', "if False else"),
    ("screen does not redirect", "approve_ui.py", "self.send_response(303)", "self.send_response(200)"),
    ("screen does not escape", "approve_ui.py", "html.escape(str(text), quote=True)", "str(text)"),
    ("screen hides the reject", "approve_ui.py", "approvals.deny(hold)", "pass"),
    ("changed tool definitions run", "proxy.py", "tool in self.pins.changed(tools)", "False"),
    ("description left out of fingerprint", "proxy.py", '{"description": tool.description, "parameters"', '{"parameters"'),
    ("drafted policy trusts server hints", "cli.py", 'f"{json.dumps(t.name)}: commit{note}"',
     'f"{json.dumps(t.name)}: {\'lookup\' if read_only else \'commit\'}{note}"'),
    ("missing request allowed", "gate.py", "if not self.intent:", "if False:"),
    ("automatic checks skipped", "gate.py", "if reason:\n            return Decision(False, \"checks\", reason)",
     "if False:\n            pass"),
    ("no reviewer means allow", "gate.py", 'return Decision(False, "gate", "needs human approval")',
     'return Decision(True, "gate")'),
    ("reviewer failure allows", "gate.py", 'return Decision(False, "reviewer", f"review unavailable: {type(exc).__name__}")',
     'return Decision(True, "reviewer")'),
    ("reviewer hold ignored", "gate.py", 'return Decision(False, "reviewer", reason, ', 'return Decision(True, "reviewer", reason, '),
    ("signature not checked", "approval.py", "good = hmac.compare_digest(t[\"mac\"], self._mac(t[\"hold_id\"], t[\"digest\"], t[\"expires\"]))",
     "good = True"),
    ("expiry not checked", "approval.py", 'fresh = float(t["expires"]) > now', "fresh = True"),
    ("arguments not bound", "approval.py", 'match = t["digest"] == digest', "match = True"),
    ("token reusable", "approval.py", "os.replace(path, path.with_suffix(\".used\"))", "pass"),
    ("no key still approves", "approval.py", "if self.key is None:\n            raise ValueError(\"no signing key configured\")",
     "if self.key is None:\n            self.key = b'x'"),
    ("recovered failures still hold", "checks.py", "last[entry[\"tool\"]] = entry[\"ok\"]",
     "last[entry[\"tool\"]] = last.get(entry[\"tool\"], True) and entry[\"ok\"]"),
    ("failed tools ignored", "checks.py", "not ok and t != tool", "False"),
    ("missing tool check off", "checks.py", "missing = sorted(named - available)", "missing = []"),
    ("loose verdict parsing", "reviewer.py", 'verdict.get("decision") not in ("proceed", "hold")', "False"),
    ("tool output not quoted", "reviewer.py", 'f"TOOL_RESULTS:\\n{json.dumps(results)}"', 'f"TOOL_RESULTS:\\n{results}"'),
    ("long output keeps head only", "reviewer.py", 'return f"{text[:half]}...[{len(text) - MAX_ENTRY_CHARS} chars cut]...{text[-half:]}"',
     "return text[:MAX_ENTRY_CHARS]"),
    ("audit chain not verified", "audit.py", 'ok = rec["prev"] == prev and rec["hash"] == _digest(prev, rec["event"], log_key)', "ok = True"),
    ("allowlist ignored", "gate.py", "if tool in self.allow:", "if False:"),
    ("several verdicts accepted", "reviewer.py", "if len(calls) != 1:", "if not calls:"),
    ("secrets passed to tool server", "proxy.py",'if not k.startswith("HOLDPOINT_")', "if True"),
    ("failures left out of trace", "proxy.py",'self.trace.append({"tool": tool, "ok": False, "text": str(exc)})', "pass"),
]


def run_tests(cwd):
    env = {**os.environ, "PYTHONPATH": str(cwd), "PYTHONUTF8": "1"}
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "tests"],
                          cwd=cwd, env=env, capture_output=True, text=True, check=False)


def copy_project(work):
    for folder in ("holdpoint", "tests", "examples", "evidence"):
        shutil.copytree(ROOT / folder, work / folder)


def main():
    # A failing suite would make every mutant look caught, so the clean code must pass first.
    clean = run_tests(ROOT)
    if clean.returncode:
        print(clean.stdout[-1500:])
        sys.exit("the unmodified code fails its tests, so a mutation score would mean nothing")
    # A copy could fail for a reason unrelated to the mutation, which would make every mutant look caught.
    with tempfile.TemporaryDirectory() as d:
        copy_project(Path(d))
        control = run_tests(Path(d))
        if control.returncode:
            print(control.stdout[-1500:])
            sys.exit("an unmodified copy fails its tests, so a mutation score would mean nothing")
    results = []
    for name, file, old, new in MUTANTS:
        with tempfile.TemporaryDirectory() as d:
            work = Path(d)
            copy_project(work)
            path = work / "holdpoint" / file
            src = path.read_text(encoding="utf-8").replace("\r\n", "\n")
            if src.count(old) != 1:
                results.append({"mutant": name, "status": "NOT APPLIED"})
                print(results[-1], flush=True)
                continue
            path.write_text(src.replace(old, new), encoding="utf-8")
            r = run_tests(work)
            results.append({"mutant": name, "status": "caught" if r.returncode else "SURVIVED"})
            print(results[-1], flush=True)
    caught = sum(x["status"] == "caught" for x in results)
    print(f"caught {caught} of {len(results)}")
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(json.dumps(results, indent=1), encoding="utf-8")
    sys.exit(0 if caught == len(results) else 1)


if __name__ == "__main__":
    main()
