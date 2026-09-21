#!/usr/bin/env bash
set -euo pipefail

# Secure multi-bot Telegram token rotation.
# The token is read from hidden terminal input only.
# It is validated against the expected bot username before any Railway change.
# No raw token is written to Git, state/, config, or logs.

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REGISTRY="$SCRIPT_DIR/core/telegram_token_registry.py"

if ! command -v railway >/dev/null 2>&1; then
  echo "ERROR: Railway CLI is required."
  exit 2
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required."
  exit 2
fi

ALIAS="${1:-}"
if [[ -z "$ALIAS" ]]; then
  echo "USAGE: $0 <main|air|claude|ton>"
  exit 3
fi

TARGETS="$(python3 -c 'import sys; from importlib.util import spec_from_file_location,module_from_spec; spec=spec_from_file_location("slh_token_registry",sys.argv[1]); m=module_from_spec(spec); spec.loader.exec_module(m); b=m.get_bot(sys.argv[2]); print(b["username"]); [print("\t".join([t["project_id"],t["environment_id"],t["service_id"],t["variable"],t["project"],t["service"]])) for t in b["targets"]]' "$REGISTRY" "$ALIAS")"
EXPECTED_USERNAME="$(printf "%s\n" "$TARGETS" | sed -n '1p')"
TARGET_ROWS="$(printf "%s\n" "$TARGETS" | tail -n +2)"

if [[ -z "$EXPECTED_USERNAME" || -z "$TARGET_ROWS" ]]; then
  echo "ERROR: registry returned no valid targets."
  exit 5
fi

echo "Target bot: @$EXPECTED_USERNAME"
echo "Enter the new token. Input is hidden and is never stored in shell history."
read -r -s -p "New Telegram token: " NEW_TOKEN
echo
if [[ -z "$NEW_TOKEN" ]]; then
  echo "ERROR: empty token; nothing changed."
  exit 6
fi

export NEW_TOKEN EXPECTED_USERNAME
trap 'unset NEW_TOKEN EXPECTED_USERNAME' EXIT

python3 -c 'import json,os,sys,urllib.request; token=os.environ["NEW_TOKEN"]; expected=os.environ["EXPECTED_USERNAME"].lstrip("@"); r=urllib.request.urlopen("https://api.telegram.org/bot"+token+"/getMe",timeout=10); d=json.load(r); actual=str((d.get("result") or {}).get("username") or "").lstrip("@"); (sys.exit(7) if not d.get("ok") else None); (print("ERROR: token belongs to a different bot; nothing changed.") or print("Expected: @"+expected) or print("Received: @"+(actual or "unknown")) or sys.exit(8)) if actual != expected else print("Telegram validation: OK (@"+actual+")")'

while IFS=$'\t' read -r PROJECT_ID ENVIRONMENT_ID SERVICE_ID VARIABLE PROJECT SERVICE; do
  [[ -z "$PROJECT_ID" ]] && continue
  echo "Linking $PROJECT/$SERVICE"
  railway link \
    --project "$PROJECT_ID" \
    --environment "$ENVIRONMENT_ID" \
    --service "$SERVICE_ID" >/dev/null

  echo "Updating $PROJECT/$SERVICE -> $VARIABLE"
  printf "%s" "$NEW_TOKEN" | railway variable set "$VARIABLE" --stdin \
    --service "$SERVICE_ID" \
    --environment "$ENVIRONMENT_ID" \
    --skip-deploys

  echo "Redeploying $PROJECT/$SERVICE"
  railway redeploy \
    --service "$SERVICE_ID" \
    --yes
done <<< "$TARGET_ROWS"

echo "Telegram token rotation completed for @$EXPECTED_USERNAME."
