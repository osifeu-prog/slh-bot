#!/bin/bash
# SLH Doctor – Full diagnostic block (no conditionals, all steps)
set -euo pipefail

echo "===== SLH DOCTOR START ====="
date
pwd

echo "[1] Git status"
git status --short
echo "HEAD: $(git rev-parse --short HEAD)"

echo "[2] Python syntax (all files)"
python3 -m compileall -q . 2>&1 && echo "PASS: Syntax OK"  echo "FAIL: Syntax errors"

echo "[3] JSON integrity"
python3 - <<'PY'
import json, sys
files = ["state/db.json", "state/agents.json", "state/users.json"]
failed = 0
for f in files:
    try:
        with open(f, "r", encoding="utf-8") as fp:
            json.load(fp)
        print("PASS:", f)
    except Exception as e:
        print("FAIL:", f, str(e))
        failed += 1
sys.exit(failed)
PY

echo "[4] Critical imports"
python3 - <<'PY'
import importlib, sys
mods = [
    "handlers.loader",
    "handlers.llm_handler",
    "handlers.advanced_ask_handler",
    "core.identity",
    "core.system_collector",
    "handlers.logo_handler",
    "handlers.esp_handler"
]
failed = 0
for m in mods:
    try:
        importlib.import_module(m)
        print("PASS:", m)
    except Exception as e:
        print("FAIL:", m, str(e))
        failed += 1
sys.exit(failed)
PY

echo "[5] API keys present"
python3 - <<'PY'
import os
keys = ["GROQ_API_KEY", "GEMINI_API_KEY", "BOT_TOKEN"]
for k in keys:
    val = os.getenv(k)
    print("PASS:", k, "present" if val else "MISSING")
PY

echo "[6] Bot process"
pgrep -af bot_stable.py  echo "FAIL: bot not running"

echo "[7] Last 30 lines of bot.log"
tail -30 bot.log 2>/dev/null || echo "No bot.log"

echo "[8] Git diff summary"
git diff --stat

echo "[9] Environment (masked)"
env | grep -E 'BOT|GROQ|TOKEN|RAILWAY' | sed 's/=.*$/=***/'

echo "===== SLH DOCTOR DONE ====="
