from pathlib import Path
import py_compile

FILES = [
    "handlers/loader.py",
    "state/custom_handlers/token_handler.py",
    "bot_stable.py",
]

print("=== SLH Integrity Check ===")

for f in FILES:
    p = Path(f)

    if not p.exists():
        print("❌ Missing:", f)
        continue

    try:
        py_compile.compile(str(p), doraise=True)
        print("✅", f)
    except Exception as e:
        print("❌", f, e)

print("=== DONE ===")
