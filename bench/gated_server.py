"""Entry point the benchmark harness launches in place of its task server.

Usage: gated_server.py ENV_FILE [holdpoint-proxy arguments]

Harnesses start MCP servers with a filtered environment, so the project path is
derived from this file. Only HOLDPOINT_ settings are read from the env file.
"""
import os
import sys
from pathlib import Path

from dotenv import dotenv_values

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from holdpoint.proxy import main

if __name__ == "__main__":
    env_file = sys.argv.pop(1)
    for key, value in dotenv_values(env_file).items():
        if key.startswith("HOLDPOINT_") and value is not None:
            os.environ.setdefault(key, value)
    main()
