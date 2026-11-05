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
    ("commit tools not gated", "gate.py", 'return self.policy.get(tool, "commit") == "commit"', "return False"),
    ("unknown tools treated as safe", "gate.py", 'self.policy.get(tool, "commit")', 'self.policy.get(tool, "lookup")'),
    ("missing request allowed", "gate.py", "if not self.intent:", "if False:"),
    ("automatic checks skipped", "gate.py", "if reason:\n            return Decision(False, \"checks\", reason)",
     "if False:\n            pass"),
    ("no reviewer means allow", "gate.py", 'return Decision(False, "gate", "needs human approval")',
     'return Decision(True, "gate")'),
    ("reviewer failure allows", "gate.py", 'return Decision(False, "reviewer", f"review unavailable: {type(exc).__name__}")',
     'return Decision(True, "reviewer")'),
    ("reviewer hold ignored", "gate.py", 'return Decision(proceed, "reviewer", reason, ', 'return Decision(True, "reviewer", reason, '),
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
    ("audit chain not verified", "audit.py", 'ok = rec["prev"] == prev and rec["hash"] == _digest(prev, rec["event"])', "ok = True"),
    ("allowlist ignored", "gate.py", "if tool in self.allow:", "if False:"),
    ("several verdicts accepted", "reviewer.py", "if len(calls) != 1:", "if not calls:"),
    ("secrets passed to tool server", "proxy.py",'if not k.startswith("HOLDPOINT_")', "if True"),
    ("failures left out of trace", "proxy.py",'self.trace.append({"tool": tool, "ok": False, "text": str(exc)})', "pass"),
]


def run_tests(cwd):
    env = {**os.environ, "PYTHONPATH": str(cwd), "PYTHONUTF8": "1"}
    return subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "tests"],
                          cwd=cwd, env=env, capture_output=True, text=True, check=False)


def main():
    # A failing suite would make every mutant look caught, so the clean code must pass first.
    clean = run_tests(ROOT)
    if clean.returncode:
        print(clean.stdout[-1500:])
        sys.exit("the unmodified code fails its tests, so a mutation score would mean nothing")
    results = []
    for name, file, old, new in MUTANTS:
        with tempfile.TemporaryDirectory() as d:
            work = Path(d)
            shutil.copytree(ROOT / "holdpoint", work / "holdpoint")
            shutil.copytree(ROOT / "tests", work / "tests")
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
