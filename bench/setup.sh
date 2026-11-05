#!/usr/bin/env bash
# Install the benchmark exactly as measured. Needs Linux or WSL, git and uv. Uses no API keys.
# Run from the repo root: bash bench/setup.sh
set -eu
E="${HOLDPOINT_REPO:-$PWD}"
D="${AGENTABSTAIN_DIR:-$HOME/agentabstain}"
COMMIT=cfc3faf7ab1cfd4892cde1158d6e43b2f312ddc3
[ -d "$D" ] || git clone -q https://github.com/AntiQuality/agentabstain "$D"
cd "$D"
git checkout -q "$COMMIT"
[ -x .venv-era/bin/python ] || uv venv -q --python 3.11 .venv-era
tr -d '\r' < "$E/bench/requirements.era.lock" > lock.txt
uv pip install -q --python .venv-era/bin/python -r lock.txt
.venv-era/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download('antiquality/agentabstain', repo_type='dataset', local_dir='data')" 2>/dev/null
.venv-era/bin/python - "$E/bench/split.json" <<'EOF'
import hashlib, json, sys
want = json.load(open(sys.argv[1]))["tasks_jsonl_sha256"]
got = hashlib.sha256(open("data/tasks.jsonl", "rb").read()).hexdigest()
print("dataset matches the measured version" if got == want else f"WARNING: dataset differs from the measured version: {got}")
EOF
echo "benchmark ready in $D"
