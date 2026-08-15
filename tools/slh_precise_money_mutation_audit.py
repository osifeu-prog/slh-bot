from pathlib import Path
import ast

ROOT = Path.cwd()

SKIP = {
    ".git",
    "__pycache__",
    "venv",
    ".venv",
}

MONEY_WORDS = (
    "credit",
    "credits",
    "balance",
    "wallet",
    "staked",
    "token_balance",
)

print("=" * 110)
print("SLH PRECISE MONEY MUTATION AUDIT")
print("=" * 110)

for path in ROOT.rglob("*.py"):

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

    hits = []

    for node in ast.walk(tree):

        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):

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

                low = text.lower()

                if any(word in low for word in MONEY_WORDS):

                    kind = type(node).__name__

                    try:
                        full = ast.get_source_segment(source, node) or text
                    except Exception:
                        full = text

                    hits.append(
                        (
                            node.lineno,
                            kind,
                            text,
                            full.strip(),
                        )
                    )

        elif isinstance(node, ast.Call):

            try:
                call = ast.unparse(node)
            except Exception:
                continue

            low = call.lower()

            if any(x in low for x in (
                ".update(",
                ".setdefault(",
                "add_balance(",
                "spend_credits(",
                "grant(",
                "save_db(",
            )):
                hits.append(
                    (
                        node.lineno,
                        "CALL",
                        call[:220],
                        call[:220],
                    )
                )

    if not hits:
        continue

    print()
    print("-" * 110)
    print("FILE:", path)
    print("-" * 110)

    for line, kind, target, full in sorted(
        hits,
        key=lambda x: x[0],
    ):
        print(f"{line}: {kind}")
        print(f"    TARGET/CALL: {target}")
        print(f"    SOURCE:      {full}")

print()
print("=" * 110)
print("PRECISE MONEY MUTATION AUDIT COMPLETE — READ ONLY")
print("=" * 110)
