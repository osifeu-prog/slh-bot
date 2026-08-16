from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent

EXCLUDED_DIRS = {
    "venv",
    ".venv",
    "__pycache__",
    ".git",
    "tests",
    "_archive",
    "archive",
    "node_modules",
    "_slh_map",
}

def excluded_file(name):
    n = name.lower()
    return (
        "backup" in n
        or "recovery" in n
        or "copy" in n
        or n.endswith(".bak")
        or n.endswith(".old")
    )

files = []

for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [
        d for d in dirnames
        if d not in EXCLUDED_DIRS
        and not d.startswith("_BACKUP_")
    ]

    for filename in filenames:
        if not filename.endswith(".py"):
            continue

        if excluded_file(filename):
            continue

        path = Path(dirpath) / filename

        try:
            rel = path.relative_to(ROOT)
        except ValueError:
            continue

        if "_slh_map" in rel.parts:
            continue

        files.append(str(rel).replace("\\", "/"))

print()
print("========================================")
print("       SLH CLEAN PYTHON INVENTORY")
print("========================================")
print(f"Python files after exclusions: {len(files)}")
print()

print("BACKUP/RECOVERY-LIKE FILES STILL INCLUDED:")
bad = [
    f for f in files
    if any(x in Path(f).name.lower() for x in
           ["backup", "recovery", "copy", "archive", ".bak", ".old"])
]

if bad:
    for f in bad:
        print("  [BAD]", f)
else:
    print("  NONE")

print()
print("========================================")
