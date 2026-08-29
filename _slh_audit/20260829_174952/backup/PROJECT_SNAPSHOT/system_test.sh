#!/data/data/com.termux/files/usr/bin/bash

# ============================================================
# SLH SYSTEM TEST SUITE
# Non-destructive automated diagnostics
# ============================================================

set +e

ROOT="$(pwd)"
REPORT_DIR="$ROOT/reports"
TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
REPORT="$REPORT_DIR/system_test_$TIMESTAMP.log"

mkdir -p "$REPORT_DIR"

PASS=0
FAIL=0
WARN=0

exec > >(tee "$REPORT") 2>&1

echo "============================================================"
echo "              SLH SYSTEM TEST SUITE"
echo "============================================================"
echo "Date: $(date)"
echo "Root: $ROOT"
echo "Report: $REPORT"
echo "============================================================"
echo

pass() {
    echo "✅ PASS: $1"
    PASS=$((PASS+1))
}

fail() {
    echo "❌ FAIL: $1"
    FAIL=$((FAIL+1))
}

warn() {
    echo "⚠️ WARN: $1"
    WARN=$((WARN+1))
}

section() {
    echo
    echo "============================================================"
    echo "$1"
    echo "============================================================"
}

# ------------------------------------------------------------
# 1. BASIC ENVIRONMENT
# ------------------------------------------------------------

section "1. BASIC ENVIRONMENT"

if command -v python3 >/dev/null 2>&1; then
    pass "Python available: $(python3 --version)"
else
    fail "Python3 missing"
fi

if [ -f "bot_stable.py" ]; then
    pass "bot_stable.py exists"
else
    fail "bot_stable.py missing"
fi

if [ -f "requirements.txt" ]; then
    pass "requirements.txt exists"
else
    warn "requirements.txt missing"
fi

# ------------------------------------------------------------
# 2. ACTIVE PROCESS
# ------------------------------------------------------------

section "2. ACTIVE PROCESS"

PIDS=$(pgrep -f "python.*bot_stable.py" | grep -v "$$" || true)

if [ -n "$PIDS" ]; then
    pass "Bot process active"
    echo "$PIDS"
else
    fail "No active bot_stable.py process"
fi

COUNT=$(echo "$PIDS" | grep -c "python" || true)

if [ "$COUNT" -gt 1 ]; then
    fail "Multiple bot processes detected: $COUNT"
else
    pass "Single-instance process check"
fi

# ------------------------------------------------------------
# 3. PYTHON SYNTAX
# ------------------------------------------------------------

section "3. PYTHON SYNTAX"

SYNTAX_FAIL=0

while IFS= read -r file; do
    python3 -m py_compile "$file" >/dev/null 2>&1

    if [ $? -ne 0 ]; then
        echo "❌ Syntax error: $file"
        SYNTAX_FAIL=1
    fi
done < <(find . -name "*.py" \
    -not -path "./.git/*" \
    -not -path "./__pycache__/*" \
    -not -path "*/__pycache__/*")

if [ "$SYNTAX_FAIL" -eq 0 ]; then
    pass "All Python files compile"
else
    fail "Python syntax errors detected"
fi

# ------------------------------------------------------------
# 4. CORE FILES
# ------------------------------------------------------------

section "4. CORE FILES"

CORE_FILES=(
    "bot_stable.py"
    "state/db.json"
    "state/users.json"
    "state/agents.json"
    "handlers/advanced_ask_handler.py"
    "handlers/askdebug_handler.py"
    "handlers/llm_handler.py"
)

for file in "${CORE_FILES[@]}"; do
    if [ -f "$file" ]; then
        pass "Exists: $file"
    else
        fail "Missing: $file"
    fi
done

# ------------------------------------------------------------
# 5. JSON VALIDATION
# ------------------------------------------------------------

section "5. JSON VALIDATION"

JSON_FAIL=0

while IFS= read -r file; do
    python3 - "$file" <<'PY'
import json
import sys

path = sys.argv[1]

try:
    with open(path, encoding="utf-8") as f:
        json.load(f)
    print("✅ JSON OK:", path)
except Exception as e:
    print("❌ JSON ERROR:", path, repr(e))
    sys.exit(1)
PY

    if [ $? -ne 0 ]; then
        JSON_FAIL=1
    fi
done < <(find state -type f -name "*.json" 2>/dev/null)

if [ "$JSON_FAIL" -eq 0 ]; then
    pass "All state JSON files valid"
else
    fail "Invalid JSON detected"
fi

# ------------------------------------------------------------
# 6. DATABASE / STATE CONTENT
# ------------------------------------------------------------

section "6. DATABASE / STATE CONTENT"

python3 <<'PY'
import json
import os

files = [
    "state/db.json",
    "state/users.json",
    "state/agents.json",
    "state/tasks.json",
    "state/security/roles.json",
]

for path in files:
    print()
    print("---", path, "---")

    if not os.path.exists(path):
        print("MISSING")
        continue

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        print("SIZE:", os.path.getsize(path))
        print("TYPE:", type(data).__name__)

        if isinstance(data, dict):
            print("KEYS:", list(data.keys()))

            for key in ("users", "agents", "tasks", "votes", "memory"):
                if key in data:
                    value = data[key]
                    try:
                        print(f"{key}: {len(value)}")
                    except Exception:
                        print(f"{key}: {type(value).__name__}")

        elif isinstance(data, list):
            print("COUNT:", len(data))

    except Exception as e:
        print("ERROR:", repr(e))
PY

if [ -f "state/db.json" ]; then
    pass "Primary state DB readable"
else
    fail "Primary state DB missing"
fi

# ------------------------------------------------------------
# 7. DATABASE SOURCE CONSISTENCY
# ------------------------------------------------------------

section "7. DATABASE SOURCE CONSISTENCY"

echo "Searching DB readers..."

grep -RniE \
    "state/db\.json|users\.json|agents\.json|tasks\.json|json\.load|load_state|load_db" \
    handlers core services 2>/dev/null | head -n 200

echo
echo "Potential DB sources listed above."

# ------------------------------------------------------------
# 8. ASK PATH ANALYSIS
# ------------------------------------------------------------

section "8. ASK PATH ANALYSIS"

echo "--- advanced_ask_handler.py ---"
nl -ba handlers/advanced_ask_handler.py 2>/dev/null | sed -n '1,220p'

echo
echo "--- llm_handler.py ---"
nl -ba handlers/llm_handler.py 2>/dev/null | sed -n '1,400p'

echo
echo "--- Possible string concatenation ---"

grep -RniE \
    "\+[[:space:]]*[A-Za-z_][A-Za-z0-9_]*|[A-Za-z_][A-Za-z0-9_]*[[:space:]]*\+=" \
    handlers core services 2>/dev/null | head -n 300

# ------------------------------------------------------------
# 9. IMPORT TEST
# ------------------------------------------------------------

section "9. IMPORT TEST"

python3 <<'PY'
import importlib

modules = [
    "handlers.advanced_ask_handler",
    "handlers.askdebug_handler",
    "handlers.llm_handler",
]

failed = False

for module in modules:
    try:
        importlib.import_module(module)
        print("✅ IMPORT OK:", module)
    except Exception as e:
        print("❌ IMPORT FAILED:", module)
        print(repr(e))
        failed = True

if failed:
    raise SystemExit(1)
PY

if [ $? -eq 0 ]; then
    pass "Critical handler imports"
else
    fail "Critical handler import failure"
fi

# ------------------------------------------------------------
# 10. ASK FUNCTION DIRECT TEST
# ------------------------------------------------------------

section "10. ASK FUNCTION DIRECT TEST"

python3 <<'PY'
import traceback

try:
    from handlers.llm_handler import query_llm_with_context

    print("Function found: query_llm_with_context")

    test_cases = [
        ("", "8789977826"),
        ("test", "8789977826"),
        ("system status", "8789977826"),
    ]

    for query, uid in test_cases:
        print()
        print("TEST:", repr(query), repr(uid))

        try:
            result = query_llm_with_context(query, uid)

            print("RESULT TYPE:", type(result).__name__)
            print("RESULT:", repr(result)[:1000])

            if result is None:
                print("⚠️ RETURNED NONE")

        except Exception as e:
            print("❌ EXCEPTION:", repr(e))
            traceback.print_exc()

except Exception as e:
    print("❌ Could not load query_llm_with_context")
    traceback.print_exc()
PY

# ------------------------------------------------------------
# 11. ASK ERROR CAPTURE SEARCH
# ------------------------------------------------------------

section "11. ERROR HANDLING AUDIT"

grep -RniE \
    "except Exception|except:|traceback|logger\.exception|print_exc" \
    handlers core services 2>/dev/null | head -n 300

echo
echo "Checking generic exception swallowing..."

SWALLOWED=$(grep -RniE "^[[:space:]]*except:[[:space:]]*$" \
    handlers core services 2>/dev/null | wc -l)

if [ "$SWALLOWED" -eq 0 ]; then
    pass "No bare except blocks detected"
else
    warn "Bare except blocks detected: $SWALLOWED"
fi

# ------------------------------------------------------------
# 12. STATUS DATA PATH AUDIT
# ------------------------------------------------------------

section "12. STATUS DATA PATH AUDIT"

echo "Searching status implementation..."

grep -RniE \
    "status|Users:|Agents:|Tasks:|len\(.*users|len\(.*agents|len\(.*tasks" \
    handlers core services 2>/dev/null | head -n 300

# ------------------------------------------------------------
# 13. ENVIRONMENT
# ------------------------------------------------------------

section "13. ENVIRONMENT"

echo "Python:"
python3 --version

echo
echo "Working directory:"
pwd

echo
echo "Important environment variables:"
env | grep -E "^(BOT_TOKEN|GROQ_API_KEY|GEMINI_API_KEY|OPENAI_API_KEY|RAILWAY|DATABASE)" \
    | sed 's/=.*$/=<SET>/'

echo
echo "Disk:"
df -h .

# ------------------------------------------------------------
# 14. GIT STATUS
# ------------------------------------------------------------

section "14. GIT STATUS"

if [ -d ".git" ]; then
    git status --short
    echo
    echo "Current commit:"
    git log -1 --oneline

    if [ -z "$(git status --short)" ]; then
        pass "Git working tree clean"
    else
        warn "Git working tree has changes"
    fi
else
    warn "Git repository not detected"
fi

# ------------------------------------------------------------
# 15. FINAL SUMMARY
# ------------------------------------------------------------

section "FINAL SUMMARY"

echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "WARN: $WARN"
echo
echo "REPORT:"
echo "$REPORT"

echo
echo "============================================================"

if [ "$FAIL" -eq 0 ]; then
    echo "🟢 SYSTEM TEST RESULT: NO CRITICAL STRUCTURAL FAILURES"
else
    echo "🔴 SYSTEM TEST RESULT: FAILURES DETECTED"
fi

echo "============================================================"

exit "$FAIL"
