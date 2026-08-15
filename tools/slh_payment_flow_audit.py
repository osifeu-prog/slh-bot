from pathlib import Path
import ast

ROOT = Path.cwd()

FILES = [
    "handlers/payment_handler.py",
    "core/reward_engine.py",
    "core/profile_manager.py",
    "core/state_manager.py",
    "state/db.json",
]

print("=" * 100)
print("SLH PAYMENT TRANSACTION FLOW AUDIT")
print("=" * 100)

for filename in FILES:
    path = ROOT / filename

    print("\n" + "-" * 100)
    print(filename)
    print("-" * 100)

    if not path.exists():
        print("MISSING")
        continue

    source = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    if filename.endswith(".py"):
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
            low = body.lower()

            if not any(x in low for x in (
                "successful_payment",
                "charge_id",
                "telegram_payment_charge_id",
                "reward_engine.grant",
                "save_db",
                "transactions",
                "add_balance",
                "get_balance",
            )):
                continue

            print(f"\nFUNCTION: {node.name}")
            print(f"LINE: {node.lineno}")

            for i, line in enumerate(
                body.splitlines(),
                start=node.lineno,
            ):
                l = line.lower()

                if any(x in l for x in (
                    "successful_payment",
                    "charge_id",
                    "telegram_payment_charge_id",
                    "grant(",
                    "add_balance(",
                    "save_db(",
                    "transactions",
                    "already",
                    "duplicate",
                    "except",
                    "error",
                    "rollback",
                )):
                    print(f"{i}: {line.strip()}")

    else:
        print(source[:12000])

print("\n" + "=" * 100)
print("PAYMENT FLOW AUDIT COMPLETE — READ ONLY")
print("=" * 100)
