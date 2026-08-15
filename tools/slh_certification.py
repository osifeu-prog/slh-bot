# SLH OS PRE-LAUNCH CERTIFICATION
# Single-source executable audit

import ast
import json
import inspect
import py_compile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def section(name):
    print("\n" + "=" * 72)
    print(name)
    print("=" * 72)

def safe_type(e):
    return type(e).__name__

# ============================================================
# 1 DATABASE
# ============================================================

section("[1] DATABASE")

db_path = ROOT / "state" / "db.json"

try:
    db = json.loads(db_path.read_text(encoding="utf-8"))

    print("JSON_OK")
    print("USERS:", len(db.get("users", {})))
    print("AGENTS:", len(db.get("agents", {})))
    print("TRANSACTIONS:", len(db.get("transactions", [])))
    print("TASKS:", len(db.get("tasks", {})))
    print("VOTES:", len(db.get("votes", {})))

    for uid, user in db.get("users", {}).items():
        wallet = user.get("wallet", {})
        print(
            "USER", uid,
            "role=", user.get("role"),
            "credits=", wallet.get("credits", 0),
            "staked=", wallet.get("staked", 0),
        )

except Exception as e:
    db = {}
    print("DB_FAIL:", safe_type(e), str(e))

# ============================================================
# 2 AGENTS
# ============================================================

section("[2] AGENTS / OWNERSHIP")

for aid, agent in db.get("agents", {}).items():
    print(
        "AGENT", aid,
        "name=", agent.get("name"),
        "owner=", agent.get("owner_id"),
        "state=", agent.get("state"),
    )

# ============================================================
# 3 AI
# ============================================================

section("[3] AI ROUTING")

try:
    import handlers.llm_handler as llm

    print("LLM_FILE:", inspect.getsourcefile(llm))

    for name in (
        "ask_groq",
        "ask_gemini",
        "query_llm_with_context",
    ):
        fn = getattr(llm, name, None)

        print(
            name,
            "EXISTS=", bool(fn),
            "FILE=", inspect.getsourcefile(fn) if fn else None,
        )

    try:
        result = llm.ask_groq(
            "Reply with exactly: GROQ_OK"
        )
        print("GROQ_RESULT:", repr(result)[:500])
    except Exception as e:
        print("GROQ_FAIL:", safe_type(e), str(e)[:500])

    try:
        result = llm.query_llm_with_context(
            "Reply with exactly: ROUTER_OK",
            uid="8789977826",
        )
        print("ROUTER_RESULT:", repr(result)[:500])
    except Exception as e:
        print("ROUTER_FAIL:", safe_type(e), str(e)[:500])

except Exception as e:
    print("AI_IMPORT_FAIL:", safe_type(e), str(e)[:500])

# ============================================================
# 4 AI HEALTH
# ============================================================

section("[4] AI HEALTH")

health_path = ROOT / "state" / "ai_health.json"

if health_path.exists():
    try:
        print(health_path.read_text(encoding="utf-8"))
    except Exception as e:
        print("HEALTH_READ_FAIL:", safe_type(e), str(e))
else:
    print("MISSING")

# ============================================================
# 5 MONEY WRITE SURFACE
# ============================================================

section("[5] MONEY WRITE SURFACE")

patterns = (
    "add_balance(",
    "spend(",
    "wallet[",
    "credits",
    "staked",
    "staking",
    "reward",
    "transfer",
    "withdraw",
    "deposit",
    "treasury",
)

money_hits = 0

for root_name in ("handlers", "core", "services"):
    base = ROOT / root_name

    if not base.exists():
        continue

    for path in base.rglob("*.py"):

        if "pycache" in path.parts:
            continue

        try:
            source = path.read_text(
                encoding="utf-8",
                errors="replace",
            )
            tree = ast.parse(source)
        except Exception:
            continue

        hits = []

        for node in ast.walk(tree):

            if isinstance(node, ast.Assign):
                try:
                    target = ast.unparse(
                        node.targets[0]
                    ).lower()

                    if any(x in target for x in patterns):
                        hits.append(
                            (
                                node.lineno,
                                "ASSIGN",
                                target[:160],
                            )
                        )
                except Exception:
                    pass

            elif isinstance(node, ast.AugAssign):
                try:
                    target = ast.unparse(
                        node.target
                    ).lower()

                    if any(x in target for x in patterns):
                        hits.append(
                            (
                                node.lineno,
                                "AUGASSIGN",
                                target[:160],
                            )
                        )
                except Exception:
                    pass

            elif isinstance(node, ast.Call):
                try:
                    call = ast.unparse(node).lower()

                    if any(x in call for x in patterns):
                        hits.append(
                            (
                                node.lineno,
                                "CALL",
                                call[:180],
                            )
                        )
                except Exception:
                    pass

        if hits:
            money_hits += len(hits)
            print("\nFILE:", path)

            for line, kind, item in hits[:80]:
                print(f"  {line}: {kind}: {item}")

print("\nMONEY_HITS:", money_hits)

# ============================================================
# 6 PAYMENT IDEMPOTENCY
# ============================================================

section("[6] PAYMENT IDEMPOTENCY")

txs = db.get("transactions", [])

charge_ids = [
    t.get("telegram_payment_charge_id")
    for t in txs
    if t.get("telegram_payment_charge_id")
]

duplicates = sorted({
    x for x in charge_ids
    if charge_ids.count(x) > 1
})

print("TX_COUNT:", len(txs))
print("CHARGE_IDS:", len(charge_ids))
print("DUPLICATES:", duplicates)

if not txs:
    print("STATUS:", "NOT_PROVEN")
    print("REASON:", "NO_TRANSACTIONS_TO_VALIDATE")
elif not charge_ids:
    print("STATUS:", "FAIL")
    print("REASON:", "TRANSACTIONS_EXIST_WITHOUT_CHARGE_IDS")
elif duplicates:
    print("STATUS:", "FAIL")
else:
    print("STATUS:", "PASS")

# ============================================================
# 7 SECURITY FILES
# ============================================================

section("[7] SECURITY FILES")

security_files = [
    "security/permissions.py",
    "core/identity.py",
    "handlers/exec_request_handler.py",
    "handlers/payment_handler.py",
    "handlers/agents_handler.py",
]

for filename in security_files:
    path = ROOT / filename
    print(
        filename,
        "OK" if path.exists() else "MISSING"
    )

# ============================================================
# 8 PYTHON COMPILE
# ============================================================

section("[8] PYTHON COMPILE")

compile_failures = []

for root_name in (
    "handlers",
    "core",
    "services",
    "security",
):
    base = ROOT / root_name

    if not base.exists():
        continue

    for path in base.rglob("*.py"):

        if "pycache" in path.parts:
            continue

        try:
            py_compile.compile(
                str(path),
                doraise=True,
            )
        except Exception as e:
            compile_failures.append(
                (str(path), str(e))
            )

print("COMPILE_FAILURES:", len(compile_failures))

for filename, error in compile_failures[:30]:
    print("FAIL:", filename, error)

# ============================================================
# 9 GIT / DEPLOYMENT
# ============================================================

section("[9] DEPLOYMENT")

for cmd in (
    ["git", "rev-parse", "HEAD"],
    ["git", "status", "--short"],
):
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=ROOT,
        )

        print(
            "CMD:",
            " ".join(cmd),
            "RC=",
            result.returncode,
        )

        if result.stdout:
            print(result.stdout[:2000])

        if result.stderr:
            print(result.stderr[:2000])

    except Exception as e:
        print(
            "GIT_FAIL:",
            safe_type(e),
            str(e),
        )

# ============================================================
# FINAL
# ============================================================

section("CERTIFICATION COMPLETE")

print("RESULTS_REQUIRE_RUNTIME_VERIFICATION")
