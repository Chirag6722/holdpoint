#!/usr/bin/env bash
cd "$HOME/agentabstain-spike" || exit 1
.venv/bin/python - <<'EOF'
from mcp.types import CallToolResult
print("CallToolResult fields:", list(CallToolResult.model_fields))
r = CallToolResult(content=[], structured_content={"state": {}, "execution_log": []})
print("getattr structuredContent:", getattr(r, "structuredContent", "MISSING"))
print("getattr structured_content:", getattr(r, "structured_content", "MISSING"))
EOF
grep -n "structuredContent\|structured_content\|isError\|is_error" src/runtime/*.py agent/*/*.py | head -20
ls -la --time-style=long-iso .venv/lib/python3.11/site-packages | grep -E " (mcp|fastmcp|openai_agents|google_adk)-" | head
curl -s https://pypi.org/pypi/mcp/json | .venv/bin/python -c "
import json,sys
d=json.load(sys.stdin)['releases']
print('mcp releases before 2026-08:',[ (v,f[0]['upload_time'][:10]) for v,f in d.items() if f and f[0]['upload_time'][:7] in ('2026-05','2026-06','2026-07')][-6:])"
curl -s https://pypi.org/pypi/fastmcp/json | .venv/bin/python -c "
import json,sys
d=json.load(sys.stdin)['releases']
print('fastmcp releases:',[ (v,f[0]['upload_time'][:10]) for v,f in d.items() if f and f[0]['upload_time'][:7] in ('2026-06','2026-07')][-6:])"
EOF_MARK=1
