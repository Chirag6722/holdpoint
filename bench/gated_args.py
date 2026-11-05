"""Build the harness's server arguments with the gate in front.

The reviewer's only input from the task is the user's instruction text. Nothing
answer-bearing in task.yaml or metadata.yaml is passed on.
"""
import os
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXPORT_TOOL = "__runtime_export_snapshot"


def wrap(original_args: list[str], instruction: str, runs_dir: str) -> list[str]:
    # The folder name lets the report attribute holds per task. The gate never reads it.
    ident = ".".join(original_args[i + 1] for i, a in enumerate(original_args)
                     if a in ("--category", "--task-id", "--task-type"))
    state = Path(runs_dir).resolve() / f"{ident}.{uuid.uuid4().hex}"
    state.mkdir(parents=True)
    intent = state / "intent.txt"
    intent.write_text(instruction, encoding="utf-8")
    env_file = str(Path(os.environ.get("HOLDPOINT_ENV_FILE", ".env")).resolve())
    return [str(HERE / "gated_server.py"), env_file, "--policy", str(HERE / "policy.yaml"), "--state-dir", str(state),
            "--intent-file", str(intent), "--allow", EXPORT_TOOL, "--", sys.executable, *original_args]
