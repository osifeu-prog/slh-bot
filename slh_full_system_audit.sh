#!/data/data/com.termux/files/usr/bin/bash

echo "======================================"
echo "      SLH FULL SYSTEM AUDIT"
echo "======================================"
date

echo ""
echo "=== 1. GIT STATUS ==="
git status
git log -3 --oneline

echo ""
echo "=== 2. PYTHON CHECK ==="
python3 - <<'PY'
import sys, os
print("Python:", sys.version)
print("PWD:", os.getcwd())
PY

echo ""
echo "=== 3. COMPILE ALL PY FILES ==="
python3 - <<'PY'
import glob, py_compile
bad=[]
for f in glob.glob("**/*.py", recursive=True):
    try:
        py_compile.compile(f, doraise=True)
    except Exception as e:
        bad.append((f,str(e)))
print("BROKEN FILES:")
for x in bad:
    print(x)
if not bad:
    print("✅ ALL PYTHON FILES OK")
PY

echo ""
echo "=== 4. MAIN BOT FILE ==="
ls -lh bot_stable.py
grep -n "infinity_polling\|polling\|TOKEN\|register" bot_stable.py | head -50

echo ""
echo "=== 5. HANDLER LOAD CHECK ==="
grep -R "loaded" *.py handlers core 2>/dev/null | head -100

echo ""
echo "=== 6. LLM CHECK ==="
grep -R "groq\|gemini\|llm\|provider" *.py handlers core 2>/dev/null | head -100

echo ""
echo "=== 7. TELEGRAM PARSE MODE RISK ==="
grep -R "parse_mode" *.py handlers core 2>/dev/null

echo ""
echo "=== 8. AGENT SYSTEM ==="
grep -R "agent_create\|agentstate\|sendagent\|inbox" *.py handlers core 2>/dev/null

echo ""
echo "=== 9. DATABASE FILES ==="
find . -maxdepth 2 -type f \( -name "*.db" -o -name "*.sqlite*" \) -ls

echo ""
echo "=== 10. STATE FILES ==="
find state runtime -maxdepth 2 -type f 2>/dev/null | head -100

echo ""
echo "=== 11. POSSIBLE ERRORS IN LOGS ==="
grep -R -i -E "error|exception|traceback|failed|conflict" logs *.log 2>/dev/null | tail -100

echo ""
echo "=== 12. REQUIREMENTS ==="
cat requirements.txt

echo ""
echo "=== 13. DOCKER ==="
cat Dockerfile

echo ""
echo "=== 14. RAILWAY LAST LOGS ==="
railway logs --tail 100 2>/dev/null | grep -E "RUNNING|POLLING|ERROR|Exception|Conflict|loaded"

echo ""
echo "======================================"
echo "       AUDIT COMPLETE"
echo "======================================"
