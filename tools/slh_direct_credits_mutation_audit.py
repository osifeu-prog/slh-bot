from pathlib import Path
import ast

ROOT = Path.cwd()

SKIP = {
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "archive",
    "SLH_ADAPTER_BACKUP_20260804_182035",
    "SLH_DASHBOARD_RECOVERY_BACKUP_20260811_180605",
}

print("=" * 120)
print("SLH DIRECT CREDITS MUTATION AUDIT")
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

        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]

        elif isinstance(node, ast.AugAssign):
            targets = [node.target]

        for target in targets:

            try:
                text = ast.unparse(target)
            except Exception:
                continue

            if "credit" not in text.lower():
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
print("DIRECT CREDITS MUTATION AUDIT COMPLETE — READ ONLY")
print("=" * 120)
