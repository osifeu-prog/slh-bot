echo "=== SLH ENV REPORT ==="

echo ""
echo "[1] CURRENT DIR"
pwd

echo ""
echo "[2] FILES"
ls -la

echo ""
echo "[3] CONFIG"
cat config.json 2>/dev/null || echo "NO CONFIG"

echo ""
echo "[4] DB STRUCTURE"
python3 - << 'PY'
import json, os

if os.path.exists("db.json"):
    try:
        db = json.load(open("db.json"))
        print("DB keys:", list(db.keys()))
    except Exception as e:
        print("DB ERROR:", e)
else:
    print("NO DB")
PY

echo ""
echo "[5] PYTHON IMPORT CHECK"
python3 - << 'PY'
mods = ["telebot", "json", "os"]
for m in mods:
    try:
        __import__(m)
        print(m, "OK")
    except Exception as e:
        print(m, "FAIL", e)
PY

echo ""
echo "=== END REPORT ==="
