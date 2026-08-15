from pathlib import Path
import ast

ROOT = Path.cwd()

print("=" * 100)
print("SLH DIRECT WALLET WRITE AUDIT")
print("=" * 100)

for path in ROOT.rglob("*.py"):

    if any(x in path.parts for x in (
        ".git",
        "__pycache__",
        "venv",
        ".venv",
    )):
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
            targets = node.targets

            for target in targets:
                try:
                    text = ast.unparse(target)
                except Exception:
                    continue

                low = text.lower()

                if any(x in low for x in (
                    "wallet",
                    "credits",
                    "staked",
                    "balance",
                )):
                    hits.append(
                        (node.lineno, "ASSIGN", text)
                    )

        elif isinstance(node, ast.AugAssign):

            try:
                text = ast.unparse(node.target)
            except Exception:
                continue

            low = text.lower()

            if any(x in low for x in (
                "wallet",
                "credits",
                "staked",
                "balance",
            )):
                hits.append(
                    (node.lineno, "AUGASSIGN", text)
                )

    if hits:
        print("\nFILE:", path)

        for line, kind, target in hits:
            print(f"  {line}: {kind}: {target}")

print("\n" + "=" * 100)
print("DIRECT WALLET WRITE AUDIT COMPLETE — READ ONLY")
print("=" * 100)
