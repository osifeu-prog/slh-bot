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

TARGETS="$(
  python3 - "$REGISTRY" "$ALIAS" <<'PY'
import importlib.util
import sys

registry_path, alias = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("slh_token_registry", registry_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

try:
    bot = module.get_bot(alias)
except KeyError:
    print(f"ERROR: unknown bot alias: {alias}", file=sys.stderr)
    raise SystemExit(4)

print(bot["username"])
for target in bot["targets"]:
    print(
        "\t".join(
            [
                target["project_id"],
                target["environment_id"],
                target["service_id"],
                target["variable"],
                target["project"],
                target["service"],
            ]
        )
    )
PY
)

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
if [[ -z "${NEW_TOKEN}" ]]; then
  echo "ERROR: empty token; nothing changed."
  exit 6
fi

export NEW_TOKEN EXPECTED_USERNAME
trap 'unset NEW_TOKEN EXPECTED_USERNAME' EXIT
python3 <<'PY'
import json
import os
import sys
import urllib.request

token = os.environ.get("NEW_TOKEN", "")
expected = os.environ.get("EXPECTED_USERNAME", "").lstrip("@")

try:
    with urllib.request.urlopen(
        "https://api.telegram.org/bot" + token + "/getMe",
        timeout=10,
    ) as response:
        data = json.load(response)
except Exception as exc:
    print("ERROR: Telegram validation failed; nothing changed.")
    print(type(exc).__name__)
    sys.exit(7)

if not data.get("ok"):
    print("ERROR: Telegram rejected token; nothing changed.")
    sys.exit(7)

actual = str((data.get("result") or {}).get("username") or "").lstrip("@")
if actual != expected:
    print("ERROR: token belongs to a different bot; nothing changed.")
    print(f"Expected: @{expected}")
    print(f"Received: @{actual or 'unknown'}")
    sys.exit(8)

print(f"Telegram validation: OK (@{actual})")
PY
while IFS=$'\t' read -r PROJECT_ID ENVIRONMENT_ID SERVICE_ID VARIABLE PROJECT SERVICE; do
  [[ -z "$PROJECT_ID" ]] && continue

  echo "Updating $PROJECT/$SERVICE -> $VARIABLE"
  printf '%s' "$NEW_TOKEN" | railway variable set "$VARIABLE" --stdin \
    --project "$PROJECT_ID" \
    --service "$SERVICE_ID" \
    --environment "$ENVIRONMENT_ID" \
    --skip-deploys

  echo "Redeploying $PROJECT/$SERVICE"
  railway redeploy \
    --project "$PROJECT_ID" \
    --service "$SERVICE_ID" \
    --environment "$ENVIRONMENT_ID" \
    --yes
done <<< "$TARGET_ROWS"

echo "Telegram token rotation completed for @$EXPECTED_USERNAME."
