"""Write the policy from each environment class's generic tool labels.

Reads no task file. Run from the benchmark checkout: export_policy.py OUT.yaml
"""
import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, os.getcwd())

from abstention_factory.runtime.registry import get_environment_class


def main(out):
    policy = {}
    for d in sorted(Path("data/environments").iterdir()):
        if (d / "environment.py").exists():
            for tool, kind in get_environment_class(d.name).tool_kinds.items():
                policy[f"{d.name}.{tool}"] = kind
    Path(out).write_text(yaml.safe_dump(policy, sort_keys=True), encoding="utf-8", newline="\n")
    print("tools", len(policy), "commit", sum(k == "commit" for k in policy.values()))


if __name__ == "__main__":
    main(sys.argv[1])
