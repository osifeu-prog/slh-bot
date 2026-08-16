#!/bin/bash
echo "=== SLH FREEZE CHECK v1.0 ==="
cd ~/slh_clean

# 1. OWNER
OID=$(grep OWNER_ID core/identity.py | grep -o '[0-9]\+')
echo "[OWNER] core/identity.py = $OID"

# 2. ASK
grep -q "register_ask_handler" handlers/loader.py && echo "[ASK] Handler registered" || echo "[ASK] NOT REGISTERED"

# 3. AGENTS JSON
python3 -c "import json; json.load(open('state/agents.json', encoding='utf-8')); print('[AGENTS] UTF8 OK')" 2>/dev/null || echo "[AGENTS] UTF8 BROKEN"

# 4. GIT
git log -1 --oneline

echo "=== END ==="
echo "אם הכל ירוק: git commit -am 'Freeze v1.0'"
