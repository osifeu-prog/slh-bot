from pathlib import Path
import ast

ROOT = Path.cwd()

SKIP = {
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "archive",
}

MUTATORS = {
    "add_balance",
    "spend_credits",
    "grant",
    "atomic_update",
    "save_db",
}

print("=" * 120)
print("SLH MONEY MUTATION CALL-SITE AUDIT")
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

        if not isinstance(node, ast.Call):
            continue

        try:
            call = ast.unparse(node)
        except Exception:
            continue

        matched = None

        if isinstance(node.func, ast.Name):
            if node.func.id in MUTATORS:
                matched = node.func.id

        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in MUTATORS:
                matched = node.func.attr

        if not matched:
            continue

        try:
            source_line = ast.get_source_segment(source, node) or call
        except Exception:
            source_line = call

        print()
        print("-" * 120)
        print(f"FILE:     {path}")
        print(f"LINE:     {node.lineno}")
        print(f"MUTATOR:  {matched}")
        print(f"CALL:     {call[:500]}")
        print(f"SOURCE:   {source_line.strip()[:500]}")

print()
print("=" * 120)
print("CALL-SITE AUDIT COMPLETE — READ ONLY")
print("=" * 120)
