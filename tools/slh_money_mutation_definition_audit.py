from pathlib import Path
import ast

ROOT = Path.cwd()

TARGETS = {
    "add_balance",
    "spend_credits",
    "grant",
    "atomic_update",
}

FILES = [
    ROOT / "core" / "profile_manager.py",
    ROOT / "core" / "reward_engine.py",
    ROOT / "core" / "economy_bridge.py",
    ROOT / "handlers" / "payment_handler.py",
    ROOT / "handlers" / "market_handler.py",
    ROOT / "handlers" / "staking_handler.py",
    ROOT / "handlers" / "exec_request_handler.py",
    ROOT / "ton_handler.py",
    ROOT / "state_manager.py",
]

print("=" * 120)
print("SLH MONEY MUTATION DEFINITION AUDIT")
print("=" * 120)

for path in FILES:
    if not path.exists():
        print(f"\n[MISSING] {path}")
        continue

    source = path.read_text(encoding="utf-8", errors="replace")

    try:
        tree = ast.parse(source)
    except Exception as e:
        print(f"\n[PARSE ERROR] {path}: {e}")
        continue

    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        name = node.name

        if name not in TARGETS:
            continue

        print()
        print("-" * 120)
        print(f"FILE:     {path}")
        print(f"FUNCTION: {name}")
        print(f"LINE:     {node.lineno}")
        print("-" * 120)

        try:
            print(ast.get_source_segment(source, node))
        except Exception:
            print(f"<unable to extract source for {name}>")

print()
print("=" * 120)
print("MONEY MUTATION DEFINITION AUDIT COMPLETE — READ ONLY")
print("=" * 120)
