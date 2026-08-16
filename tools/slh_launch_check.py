from pathlib import Path
import subprocess
import json
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

print("=== SLH OS LAUNCH CHECK ===")

errors = []

print("\n[1] COMPILE")
r = subprocess.run(
    [sys.executable, "-m", "compileall", "-q", "."],
    capture_output=True,
    text=True
)

print("OK" if r.returncode == 0 else "FAIL")

if r.returncode != 0:
    errors.append("compile")


print("\n[2] IMPORTS")

try:
    import handlers.loader
    import core.kernel
    import core.agent_registry
    print("OK")
except Exception as e:
    print("FAIL:", e)
    errors.append("imports")


print("\n[3] HANDLERS")

print("count:", len(list(Path("handlers").glob("*.py"))))


print("\n[4] AGENTS")

try:
    import core.agent_registry as r
    agents = r.STORE.get_all()
    print("count:", len(agents))
except Exception as e:
    print("FAIL:", e)
    errors.append("agents")


print("\n[5] AI HEALTH")

health = Path("state/ai_health.json")

if health.exists():
    print(json.dumps(
        json.loads(health.read_text(encoding="utf-8")),
        indent=2
    ))
else:
    print("missing")


print("\n[6] GIT")

subprocess.run(["git", "status", "--short"])

print(subprocess.check_output(
    ["git", "log", "-1", "--oneline"],
    text=True
).strip())


print("\n====================")

if errors:
    print("STATUS: NOT READY")
    print(errors)
    sys.exit(1)

print("STATUS: LAUNCH READY")
