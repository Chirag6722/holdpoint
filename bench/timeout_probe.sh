#!/usr/bin/env bash
cd "$HOME/agentabstain-spike" || exit 1
S=.venv-era/lib/python3.11/site-packages
sed -n 1,24p harness_era.log | cut -c1-150
grep -n "client_session_timeout_seconds" $S/agents/mcp/server.py | head -8
grep -n "timeout" $S/google/adk/tools/mcp_tool/mcp_session_manager.py | head -20
cat agent/googleadk/toolset.py | head -60
.venv-era/bin/python - <<'EOF'
import time, subprocess, sys
t=time.time(); subprocess.run([sys.executable,"-c","import fastmcp"],check=True); print("import fastmcp seconds", round(time.time()-t,1))
t=time.time(); subprocess.run([sys.executable,"-c","import fastmcp"],check=True); print("again seconds", round(time.time()-t,1))
EOF
