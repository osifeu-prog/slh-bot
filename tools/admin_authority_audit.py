from pathlib import Path

ROOT = Path(".")

PATTERNS = [
    "SUPER_ADMIN",
    "SUPERADMIN",
    "super_admin",
    "is_super_admin",
    "admin_id",
    "ADMIN_ID",
    "OWNER_ID",
    "OWNER_UID",
    "OWNER_TELEGRAM_ID",
    "is_admin",
]

SKIP = {
    ".git",
    "__pycache__",
}

print("=" * 100)
print("SLH GLOBAL ADMIN AUTHORITY AUDIT")
print("=" * 100)

for p in sorted(ROOT.rglob("*.py")):

    if any(part in SKIP for part in p.parts):
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

    hits = []

    for n, line in enumerate(lines, 1):
        if any(x in line for x in PATTERNS):
            hits.append((n, line.strip()))

    if hits:
        print(f"\nFILE: {p}")

        for n, line in hits:
            print(f"{n}: {line}")

print("\n" + "=" * 100)
print("END ADMIN AUTHORITY AUDIT")
print("=" * 100)
