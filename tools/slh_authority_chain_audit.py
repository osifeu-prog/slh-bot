from pathlib import Path
import ast

ROOT = Path.cwd()

TARGETS = [
    "handlers/payment_handler.py",
    "handlers/staking_handler.py",
    "core/reward_engine.py",
    "core/profile_manager.py",
    "core/economy_bridge.py",
    "security/permissions.py",
    "core/identity.py",
    "admin_utils.py",
]

print("=" * 90)
print("SLH AUTHORITY CHAIN AUDIT")
print("=" * 90)

for filename in TARGETS:
    path = ROOT / filename

    print("\n" + "-" * 90)
    print(filename)
    print("-" * 90)

    if not path.exists():
        print("MISSING")
        continue

    source = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    try:
        tree = ast.parse(source)
    except Exception as e:
        print("AST_FAIL:", type(e).__name__, str(e))
        continue

    for node in ast.walk(tree):

        if not isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue

        body = ast.get_source_segment(source, node) or ""

        calls = []
        writes = []
        auth = []

        for child in ast.walk(node):

            if isinstance(child, ast.Call):
                try:
                    call = ast.unparse(child)
                except Exception:
                    continue

                low = call.lower()

                if any(x in low for x in (
                    "grant(",
                    "add_balance(",
                    "spend(",
                    "spend_credits(",
                    "save_db(",
                    "setdefault(",
                    "send_invoice(",
                )):
                    calls.append(call[:220])

            elif isinstance(child, (ast.Assign, ast.AugAssign)):
                try:
                    target = (
                        ast.unparse(
                            child.targets[0]
                            if isinstance(child, ast.Assign)
                            else child.target
                        )
                    )
                except Exception:
                    continue

                low = target.lower()

                if any(x in low for x in (
                    "credit",
                    "staked",
                    "wallet",
                    "balance",
                )):
                    writes.append(target[:180])

        for line in body.splitlines():

            low = line.lower()

            if any(x in low for x in (
                "is_admin",
                "permission",
                "authorize",
                "authorized",
                "owner",
                "admin",
                "role",
                "identity",
                "from_user",
                "user_id",
            )):
                auth.append(line.strip())

        if calls or writes or auth:

            print(f"\nFUNCTION: {node.name}")
            print(f"LINE: {node.lineno}")

            if auth:
                print("AUTHORITY:")
                for x in auth[:30]:
                    print("  ", x)

            if writes:
                print("MONEY_WRITES:")
                for x in writes[:30]:
                    print("  ", x)

            if calls:
                print("MONEY_CALLS:")
                for x in calls[:30]:
                    print("  ", x)

print("\n" + "=" * 90)
print("AUTHORITY CHAIN AUDIT COMPLETE — READ ONLY")
print("=" * 90)
