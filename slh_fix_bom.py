from pathlib import Path
from datetime import datetime
import os

ROOT = Path(__file__).resolve().parent
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP = ROOT / "_slh_map" / "encoding_backups" / STAMP
BACKUP.mkdir(parents=True, exist_ok=True)

EXCLUDED_DIRS = {
    "venv",
    ".venv",
    "__pycache__",
    ".git",
    "_archive",
    "archive",
    "tests",
    "node_modules",
}

checked = 0
fixed = []
skipped = []

for dirpath, dirnames, filenames in os.walk(ROOT):
    current = Path(dirpath)

    # Prune excluded directories BEFORE entering them.
    dirnames[:] = [
        d for d in dirnames
        if d not in EXCLUDED_DIRS
        and not d.startswith("_BACKUP_")
    ]

    for filename in filenames:
        if not filename.endswith(".py"):
            continue

        path = current / filename

        # Never scan the backup tree itself.
        try:
            rel = path.relative_to(ROOT)
        except ValueError:
            continue

        if "_slh_map" in rel.parts:
            continue

        checked += 1

        try:
            raw = path.read_bytes()
        except (OSError, PermissionError) as e:
            skipped.append({
                "path": str(rel),
                "error": str(e),
            })
            continue

        if not raw.startswith(b"\xef\xbb\xbf"):
            continue

        backup = BACKUP / rel
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(raw)

        path.write_bytes(raw[3:])

        fixed.append(str(rel).replace("\\", "/"))

print()
print("========================================")
print("          SLH BOM REPAIR")
print("========================================")
print(f"Checked : {checked}")
print(f"Fixed   : {len(fixed)}")
print(f"Skipped : {len(skipped)}")
print(f"Backup  : {BACKUP}")
print()

if fixed:
    print("FIXED FILES:")
    for item in fixed:
        print(f"  [FIXED] {item}")
else:
    print("No UTF-8 BOM files found.")

if skipped:
    print()
    print("SKIPPED:")
    for item in skipped:
        print(f"  [SKIP] {item['path']}")
        print(f"         {item['error']}")

print()
print("========================================")
