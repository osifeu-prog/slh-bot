#!/data/data/com.termux/files/usr/bin/bash

OUT="pre_change_audit_$(date +%Y%m%d_%H%M%S).log"

echo "===== SLH PRE CHANGE AUDIT =====" | tee "$OUT"
echo "DATE: $(date)" | tee -a "$OUT"
echo "DIR: $(pwd)" | tee -a "$OUT"

echo -e "\n===== FILES =====" | tee -a "$OUT"
ls -lah | tee -a "$OUT"

echo -e "\n===== PYTHON VERSION =====" | tee -a "$OUT"
python3 --version | tee -a "$OUT"

echo -e "\n===== PY COMPILE CHECK =====" | tee -a "$OUT"
python3 -m py_compile *.py 2>&1 | tee -a "$OUT"

echo -e "\n===== DOCKERFILE =====" | tee -a "$OUT"
cat Dockerfile | tee -a "$OUT"

echo -e "\n===== BOT ENTRY =====" | tee -a "$OUT"
grep -nE "polling|infinity|bot_stable|TOKEN|slh_lock|railway" bot_stable.py 2>/dev/null | tee -a "$OUT"

echo -e "\n===== LOCK =====" | tee -a "$OUT"
cat slh_lock.py 2>/dev/null | tee -a "$OUT"

echo -e "\n===== HEALTH FILE =====" | tee -a "$OUT"
cat railway_health.py 2>/dev/null | tee -a "$OUT"

echo -e "\n===== REPORT HANDLER =====" | tee -a "$OUT"
sed -n '1,80p' report_handler.py 2>/dev/null | tee -a "$OUT"

echo -e "\n===== GIT STATUS =====" | tee -a "$OUT"
git status | tee -a "$OUT"

echo -e "\n===== LAST COMMITS =====" | tee -a "$OUT"
git log --oneline -5 | tee -a "$OUT"

echo -e "\n===== RAILWAY ENV CHECK =====" | tee -a "$OUT"
echo "PORT=$PORT" | tee -a "$OUT"

echo -e "\n===== RUNNING LOCAL PYTHON =====" | tee -a "$OUT"
ps -ef | grep -E "python|bot|SLH" | grep -v grep | tee -a "$OUT"

echo -e "\n===== END AUDIT =====" | tee -a "$OUT"

echo ""
echo "✅ AUDIT SAVED:"
echo "$OUT"
