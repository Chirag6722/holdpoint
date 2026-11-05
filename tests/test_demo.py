"""The README's demo must keep working: it runs the real proxy as a separate process."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_demo_runs_with_no_keys():
    env = {k: v for k, v in os.environ.items() if not k.startswith("HOLDPOINT_")}
    env.update(PYTHONUTF8="1", PYTHONPATH=str(ROOT))
    run = subprocess.run([sys.executable, str(ROOT / "examples" / "demo.py")], env=env, capture_output=True,
                         text=True, timeout=180, check=False)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "All outcomes were as expected." in run.stdout
    assert "intact" in run.stdout
