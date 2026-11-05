"""Run the benchmark's own inference, baseline or gated, without editing its source.

Run from the benchmark checkout, with the same flags as src.scripts.run_inference:
  python run_gated.py baseline|gated --runtime-config CONFIG --task-config TASKS --workers 4
Each condition's runtime config needs its own results_root.

With HOLDPOINT_AGENT_BACKEND=anthropic, the OpenAI SDK harness talks to Claude through
Anthropic's OpenAI-compatible endpoint. Results then differ in harness from the
published Claude rows, so they compare only with baselines run the same way.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getcwd())
sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness_patch
from gated_args import wrap

from src.runtime import common, googleadk, openaisdk
from src.scripts import run_inference

RUNS = os.environ.get("HOLDPOINT_RUNS_DIR", "runs/gated")
original = common.build_runtime_server_args


def gated_args(bundle):
    return wrap(original(bundle), bundle.task_yaml["instruction"], RUNS)


def use_anthropic_backend():
    from agents import set_default_openai_api, set_default_openai_client, set_tracing_disabled
    from openai import AsyncOpenAI

    client = AsyncOpenAI(base_url="https://api.anthropic.com/v1/", api_key=os.environ["ANTHROPIC_API_KEY"])
    set_default_openai_client(client, use_for_tracing=False)
    set_default_openai_api("chat_completions")
    set_tracing_disabled(True)


if __name__ == "__main__":
    condition = sys.argv.pop(1)
    if condition not in ("baseline", "gated"):
        sys.exit("first argument must be baseline or gated")
    harness_patch.apply()
    if os.environ.get("HOLDPOINT_AGENT_BACKEND") == "anthropic":
        use_anthropic_backend()
    if condition == "gated":
        # Both harnesses bound the function at import, so each reference is replaced.
        common.build_runtime_server_args = gated_args
        googleadk.build_runtime_server_args = gated_args
        openaisdk.build_runtime_server_args = gated_args
    run_inference.main()
