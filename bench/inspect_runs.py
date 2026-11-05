"""Show what actually happened in the saved runs. Run from the benchmark checkout."""
import json
import sys
from pathlib import Path

MODEL = "claude-haiku-4-5"
for cond in ("baseline", "gated"):
    for side in ("act", "abstain"):
        pattern = f"results_{cond}/openaisdk/{MODEL}/*/*/{side}/*/run_result.json"
        paths = sorted(Path(".").glob(pattern), key=lambda p: p.stat().st_mtime)
        if not paths:
            print(cond, side, "NO RUN")
            continue
        run = paths[-1].parent
        result = json.loads((run / "run_result.json").read_text(encoding="utf-8"))
        ev = json.loads((run / "eval.json").read_text(encoding="utf-8"))
        print(f"\n=== {cond} {side}  runs on disk: {len(paths)}  action_type: {ev.get('action_type')}")
        print("usage:", (result.get("provider_metadata") or {}).get("usage"))
        for e in result.get("execution_log") or []:
            print("  call:", e.get("tool"), "success=", e.get("success"), "|", str(e.get("error") or "")[:100])
        m = ev.get("metrics") or {}
        print("commit:", json.dumps(m.get("commit_check"))[:300])
        judge = m.get("response_llm_judge") or {}
        print("judge pass:", judge.get("pass"), "|", str(judge.get("reason") or judge.get("error") or judge)[:400])
        print("final:", str(result.get("final_output"))[:600].replace("\n", " "))
print("\n=== gate audit")
for path in sorted(Path("runs/gated").glob("*/audit.jsonl")):
    print(path.parent.name[:70])
    for line in path.read_text(encoding="utf-8").splitlines():
        e = json.loads(line)["event"]
        print("  ", e["tool"], "allow=", e["allow"], "by=", e["by"], "usage=", e.get("usage"), "|", str(e["reason"])[:160])
sys.exit(0)
