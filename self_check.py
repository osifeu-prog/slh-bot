import os
import json
import subprocess

print("=== SLH SELF MODEL ===")

files = [
    "bot_stable.py",
    "refresh_token_handler.py",
    "state/db.json",
    "docs/SELF_MODEL.md"
]

for f in files:
    print(f, "✅" if os.path.exists(f) else "❌")

print("\n=== GIT ===")
try:
    print(subprocess.check_output(
        ["git","log","-1","--oneline"],
        text=True
    ))
except Exception as e:
    print(e)

print("=== END ===")
