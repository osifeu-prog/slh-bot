from pathlib import Path
import ast

ROOT = Path.cwd()

SKIP = {
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "archive",
    "AUDIT_SNAPSHOT",
    "SLH_ADAPTER_BACKUP_20260804_182035",
    "SLH_FIX_BACKUP_20260804_181820",
    "SLH_STATE_BACKUP_20260812_marketfix_bot_stable.py",
}

KEYS = {
    "credits",
    "balance",
    "wallet",
    "staked",
}

print("=" * 120)
print("SLH MONEY WRITE AUDIT — AST")
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

        if not isinstance(
            node,
            (ast.Assign, ast.AnnAssign, ast.AugAssign)
        ):
            continue

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

            if not any(k in low for k in KEYS):
                continue

            try:
                source_segment = (
                    ast.get_source_segment(source, node)
                    or text
                )
            except Exception:
                source_segment = text

            print()
            print("-" * 120)
            print(f"FILE:   {path}")
            print(f"LINE:   {node.lineno}")
            print(f"KIND:   {type(node).__name__}")
            print(f"TARGET: {text}")
            print("SOURCE:")
            print(source_segment.strip())

print()
print("=" * 120)
print("AUDIT COMPLETE — READ ONLY")
print("=" * 120)
