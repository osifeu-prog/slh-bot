from pathlib import Path
import ast

ROOT = Path.cwd()

FILES = [
    ROOT / "handlers" / "staking_handler.py",
    ROOT / "ton_handler.py",
    ROOT / "slh.py",
    ROOT / "core" / "migration.py",
]

TARGET_LINES = {
    "staking_handler.py": {14, 34},
    "ton_handler.py": {95, 98, 101, 102, 103, 106, 116},
    "slh.py": {20},
    "migration.py": {32},
}

print("=" * 120)
print("SLH MONEY BYPASS CONTEXT AUDIT")
print("=" * 120)

for path in FILES:

    if not path.exists():
        print(f"\n[MISSING] {path}")
        continue

    source = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    try:
        tree = ast.parse(source)
    except Exception as e:
        print(f"\n[PARSE ERROR] {path}: {e}")
        continue

    print()
    print("=" * 120)
    print(f"FILE: {path}")
    print("=" * 120)

    for node in ast.walk(tree):

        if not isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue

        start = node.lineno
        end = getattr(node, "end_lineno", start)

        relevant = False

        for line in TARGET_LINES.get(path.name, set()):
            if start <= line <= end:
                relevant = True
                break

        if not relevant:
            continue

        print()
        print("-" * 120)
        print(
            f"FUNCTION: {node.name} "
            f"(lines {start}-{end})"
        )
        print("-" * 120)

        try:
            print(ast.get_source_segment(source, node))
        except Exception:
            print("<unable to extract function>")

print()
print("=" * 120)
print("MONEY BYPASS CONTEXT AUDIT COMPLETE — READ ONLY")
print("=" * 120)
