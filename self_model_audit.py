import os
import json

ALLOW = [
    "bot_stable.py",
    "handlers",
    "services",
    "core",
    "state/db.json",
    "state/system_memory.json",
    "state/memory.jsonl",
    "journal.json",
    "docs",
    "SOURCE_OF_TRUTH.md",
    "KERNEL_RULES.md",
    "AGENT_RULES.md"
]

BLOCK = [
    "backups",
    ".git",
    "__pycache__",
    "pre_restore",
    "pre_fix",
    "archive_unused"
]

print("=== SLH SELF MODEL SOURCES ===")

for x in ALLOW:
    print("ALLOW:", x)

print()
print("=== BLOCKED FROM LEARNING ===")

for x in BLOCK:
    print("BLOCK:", x)

print()
print("=== SECRET SCAN ===")

for root,dirs,files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in BLOCK]
    for f in files:
        if any(k in f.lower() for k in ["token","secret","key","password"]):
            print("CHECK:",os.path.join(root,f))

