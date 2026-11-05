"""Print the reviewer's remaining mistakes on a development round. Usage: read_mistakes.py RUNS_DIR"""
import json
import sys
from pathlib import Path

runs = Path(sys.argv[1])
for side, want_allow, title in (("act", False, "HOLDS ON SHOULD-ACT"), ("abstain", True, "PROCEEDS ON SHOULD-STOP")):
    print(f"\n==== {title}")
    for path in sorted(runs.glob(f"*.{side}.*/audit.jsonl")):
        task = path.parent.name.rsplit(".", 2)[0]
        for line in path.read_text(encoding="utf-8").splitlines():
            e = json.loads(line)["event"]
            if e["by"] in ("reviewer", "checks") and e["allow"] == want_allow:
                print(f"\n[{task}] {e['tool']} by={e['by']}\n  args: {json.dumps(e['args'])[:260]}\n  reason: {e['reason']}")
                intent = next(path.parent.glob("intent.txt"), None)
                if intent:
                    print(f"  request: {intent.read_text(encoding='utf-8')[:520]}")
