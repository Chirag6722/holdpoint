#!/usr/bin/env bash
# Save the API key inside Ubuntu without showing it. Usage: bash set_key.sh [OUT_FILE]
out="${1:-$HOME/agentabstain-spike/.env}"
read -rsp "Paste your key, then press Enter (nothing will show): " K
echo
# API keys use only these characters, so this removes anything a paste or pipe added.
K="$(printf '%s' "$K" | LC_ALL=C tr -cd 'A-Za-z0-9_-')"
if [ -z "$K" ]; then
  echo "Nothing entered, so nothing was saved."
  exit 1
fi
umask 077
printf 'ANTHROPIC_API_KEY=%s\nHOLDPOINT_REVIEWER_KEY=%s\n' "$K" "$K" > "$out"
chmod 600 "$out"
echo "Saved. Key length: ${#K} characters."
