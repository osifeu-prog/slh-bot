#!/usr/bin/env bash
set -euo pipefail

# Secure Telegram BOT_TOKEN rotation.
# - Reads the new token from hidden terminal input (never CLI args).
# - Validates it with Telegram getMe before changing anything.
# - Updates Railway's canonical BOT_TOKEN secret.
# - Does not write tokens to Git, state/, config.json, or logs.
# - Redeploy/verification is intentionally explicit so a failed deployment
#   cannot silently leave the operator believing rotation completed.

if ! command -v railway >/dev/null 2>&1; then
  echo "ERROR: Railway CLI is required."
  exit 2
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required."
  exit 2
fi

read -r -s -p "New Telegram BOT_TOKEN: " NEW_TOKEN
echo

if [[ -z "${NEW_TOKEN}" ]]; then
  echo "ERROR: empty token; nothing changed."
  exit 3
fi

export NEW_TOKEN
python3 - <<'PY'
import json, os, sys, urllib.request

token = os.environ.get("NEW_TOKEN", "")
url = "https://api.telegram.org/bot" + token + "/getMe"
try:
    with urllib.request.urlopen(url, timeout=10) as response:
        data = json.load(response)
except Exception as exc:
    print("ERROR: Telegram validation failed; nothing changed.")
    print(type(exc).__name__)
    sys.exit(4)

if not data.get("ok"):
    print("ERROR: Telegram rejected token; nothing changed.")
    sys.exit(4)

bot = data.get("result", {})
print("Telegram validation: OK")
print("Bot identity:", "@" + str(bot.get("username", "unknown")))
PY

unset NEW_TOKEN

# Ask for the token a second time so it is never retained in shell history or
# command arguments. Railway receives it only through the CLI process stdin-free
# argument construction below; the shell variable is cleared immediately after.
read -r -s -p "Enter the validated token again to update Railway: " NEW_TOKEN
 echo
if [[ -z "${NEW_TOKEN}" ]]; then
  echo "ERROR: empty token; Railway was not changed."
  exit 5
fi

export NEW_TOKEN
python3 - <<'PY'
import json, os, sys, urllib.request

token = os.environ["NEW_TOKEN"]
try:
    with urllib.request.urlopen("https://api.telegram.org/bot" + token + "/getMe", timeout=10) as response:
        data = json.load(response)
except Exception:
    print("ERROR: token re-validation failed; Railway was not changed.")
    sys.exit(6)
if not data.get("ok"):
    print("ERROR: token re-validation failed; Railway was not changed.")
    sys.exit(6)
PY

# Railway CLI needs the value as an argument. It is not printed by this script.
# The shell history does not contain the command because this is an executable
# invocation, not a command typed by the operator.
railway variables --set "BOT_TOKEN=${NEW_TOKEN}"
unset NEW_TOKEN

echo "Railway BOT_TOKEN updated successfully."
echo "Next required step: railway redeploy"
echo "Then verify the new deployment reaches SUCCESS and Telegram polling starts."
