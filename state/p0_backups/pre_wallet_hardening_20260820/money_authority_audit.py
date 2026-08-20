from pathlib import Path
import re

ROOT = Path(".")

print("=" * 100)
print("SLH GLOBAL MONEY AUTHORITY AUDIT")
print("=" * 100)

TARGETS = {
    "credits": [
        r'wallet\s*\[\s*["\']credits["\']\s*\]\s*=',
        r'\.wallet\s*\.\s*credits\s*=',
        r'["\']credits["\']\s*\+?=',
    ],
    "staked": [
        r'wallet\s*\[\s*["\']staked["\']\s*\]\s*=',
        r'\.wallet\s*\.\s*staked\s*=',
        r'["\']staked["\']\s*\+?=',
    ],
    "economy_calls": [
        r'economy_service\.',
        r'economy_bridge\.',
        r'add_credits\s*\(',
        r'move_balance\s*\(',
        r'stake\s*\(',
        r'unstake\s*\(',
        r'reward\s*\(',
    ],
}

EXCLUDE = {
    ".git",
    "__pycache__",
}

AUTHORITY_FILES = {
    Path("core/economy_service.py"),
    Path("core/economy_bridge.py"),
}

for kind, patterns in TARGETS.items():

    print(f"\n{'=' * 30} {kind.upper()} {'=' * 30}")

    hits = []

    for p in ROOT.rglob("*.py"):

        if any(part in EXCLUDE for part in p.parts):
            continue

        if "state" in p.parts and "p0_backups" in p.parts:
            continue

        try:
            lines = p.read_text(
                encoding="utf-8",
                errors="ignore"
            ).splitlines()
        except Exception:
            continue

        for lineno, line in enumerate(lines, 1):

            if any(re.search(pattern, line) for pattern in patterns):

                hits.append((p, lineno, line.strip()))

    for p, lineno, line in hits:
        marker = "AUTHORITY" if p in AUTHORITY_FILES else "OUTSIDE-AUTHORITY"
        print(f"[{marker}] {p}:{lineno}: {line}")

    print(f"\nTOTAL: {len(hits)}")

print("\n" + "=" * 100)
print("END MONEY AUTHORITY AUDIT")
print("=" * 100)
