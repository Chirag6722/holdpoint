#!/usr/bin/env bash
# Save the API key inside Ubuntu without showing it. The key arrives on standard input:
#   Get-Clipboard | wsl -d Ubuntu-22.04 --cd "<this folder>" -- bash set_key.sh
out="${1:-$HOME/agentabstain-spike/.env}"
IFS= read -r K
# API keys use only these characters, so this removes anything a paste or pipe added.
K="$(printf '%s' "$K" | LC_ALL=C tr -cd 'A-Za-z0-9_-')"
case "$K" in
  sk-ant-*) ;;
  *) echo "That is not a Claude API key (it should start with sk-ant-). Nothing was saved."; exit 1 ;;
esac
if [ "${#K}" -lt 40 ]; then
  echo "That is too short to be a whole key. Nothing was saved."
  exit 1
fi
umask 077
printf 'ANTHROPIC_API_KEY=%s\nHOLDPOINT_REVIEWER_KEY=%s\n' "$K" "$K" > "$out"
chmod 600 "$out"
echo "Saved. Key length: ${#K} characters."
