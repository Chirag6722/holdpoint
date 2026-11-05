"""Write benchmark task lists for each split. Usage: make_taskfiles.py [SPLIT_JSON] [OUT_DIR]"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def write(pairs, path):
    lines = ["tasks:"]
    for pair in pairs:
        category, task_id = pair.split("/")
        for side in ("act", "abstain"):
            lines += [f'  - category: "{category}"', f'    task_id: "{task_id}"', f'    task_type: "{side}"']
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main():
    split = json.loads(Path(sys.argv[1] if len(sys.argv) > 1 else HERE / "split.json").read_text(encoding="utf-8"))
    out = Path(sys.argv[2] if len(sys.argv) > 2 else HERE)
    write(split["dev"], out / "tasks_dev.yaml")
    write(split["held_out"], out / "tasks_held_out.yaml")
    print("dev", len(split["dev"]), "held_out", len(split["held_out"]))


if __name__ == "__main__":
    main()
