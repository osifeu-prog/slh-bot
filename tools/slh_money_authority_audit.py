from pathlib import Path
import ast

ROOT = Path.cwd()

SKIP = {
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "archive",
    "AUDIT_SNAPSHOT_20260815_211655",
    "SLH_ADAPTER_BACKUP_20260804_182035",
    "SLH_FIX_BACKUP_20260804_181820",
    "SLH_STATE_BACKUP_20260812_marketfix_bot_stable.py",
    "SLH_DASHBOARD_RECOVERY_BACKUP_20260811_180605",
}

TARGET_CALLS = {
    "add_balance",
    "spend_credits",
    "grant",
    "atomic_update",
    "save_db",
    "load_db",
}

MONEY_KEYS = {
    "credits",
    "balance",
    "staked",
    "token_balance",
}

print("=" * 120)
print("SLH MONEY AUTHORITY / CALL GRAPH AUDIT")
print("=" * 120)

for path in sorted(ROOT.rglob("*.py")):

    if any(part in SKIP for part in path.parts):
        continue

    try:
        source = path.read_text(
            encoding="utf-8",
            errors="replace",
        )
        tree = ast.parse(source)
    except Exception:
        continue

    for node in ast.walk(tree):

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function_name = node.name

        elif isinstance(node, ast.Call):
            function_name = None

            func = node.func

            if isinstance(func, ast.Name):
                function_name = func.id

            elif isinstance(func, ast.Attribute):
                function_name = func.attr

            if function_name in TARGET_CALLS:
                print()
                print("-" * 120)
                print(f"FILE: {path}")
                print(f"LINE: {node.lineno}")
                print(f"CALL: {function_name}")
                print(
                    ast.get_source_segment(source, node)
                    or "<unavailable>"
                )

        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):

            targets = []

            if isinstance(node, ast.Assign):
                targets = node.targets
            else:
                targets = [node.target]

            for target in targets:
                try:
                    text = ast.unparse(target)
                except Exception:
                    continue

                low = text.lower()

                if any(key in low for key in MONEY_KEYS):
                    print()
                    print("-" * 120)
                    print(f"FILE: {path}")
                    print(f"LINE: {node.lineno}")
                    print(f"KIND: {type(node).__name__}")
                    print(f"TARGET: {text}")
                    print(
                        ast.get_source_segment(source, node)
                        or "<unavailable>"
                    )

print()
print("=" * 120)
print("AUTHORITY / CALL GRAPH AUDIT COMPLETE — READ ONLY")
print("=" * 120)
