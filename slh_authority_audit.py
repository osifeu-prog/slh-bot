from pathlib import Path
import ast
import json
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
TARGETS = {
    "SLH_MAIN.py",
    "SLH_KERNEL.py",
    "SLH_GATEWAY.py",
    "bot_stable.py",
    "bot_core.py",
    "bot_gateway.py",
    "webapp.py",
    "slh.py",
}

OUT = ROOT / "_slh_map" / "dna" / "AUTHORITY_AUDIT.json"

def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None

def safe_read(path):
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return raw.decode("utf-8", errors="replace")

results = []

for path in sorted(ROOT.rglob("*.py")):
    if path.name not in TARGETS:
        continue

    try:
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        source = safe_read(path)
        tree = ast.parse(source, filename=rel)

        imports = []
        calls = []
        functions = []
        handlers = []
        state_reads = []
        state_writes = []

        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                imports.extend(a.name for a in n.names)

            elif isinstance(n, ast.ImportFrom):
                base = n.module or ""
                imports.extend(
                    f"{base}.{a.name}".strip(".")
                    for a in n.names
                )

            elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(n.name)

            elif isinstance(n, ast.Call):
                name = dotted(n.func)
                if not name:
                    continue

                calls.append(name)

                low = name.lower()

                if any(x in low for x in (
                    "register_command",
                    "add_handler",
                    "register_handler",
                    "router",
                    "command",
                    "dispatcher",
                )):
                    handlers.append(name)

                if any(x in low for x in (
                    "state.get",
                    "state.read",
                    "load_state",
                    "get_state",
                    "read_state",
                    "fetch_state",
                )):
                    state_reads.append(name)

                if any(x in low for x in (
                    "state.set",
                    "state.write",
                    "save_state",
                    "set_state",
                    "write_state",
                    "update_state",
                )):
                    state_writes.append(name)

        results.append({
            "path": rel,
            "status": "PARSED",
            "functions": sorted(set(functions)),
            "imports": sorted(set(imports)),
            "handler_signals": sorted(set(handlers)),
            "state_reads": sorted(set(state_reads)),
            "state_writes": sorted(set(state_writes)),
            "call_count": len(calls),
            "main_guard": (
                'if __name__ == "__main__":' in source
                or "if __name__ == '__main__':" in source
            ),
            "signals": {
                "filename_entrypoint": path.name in TARGETS,
                "has_main": "main" in functions,
                "has_run": "run" in functions,
                "has_start": "start" in functions,
                "has_dispatch": "dispatch" in functions,
                "has_handlers": bool(handlers),
                "has_state_writes": bool(state_writes),
            },
        })

    except Exception as e:
        results.append({
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "status": "ERROR",
            "error": str(e),
        })

audit = {
    "schema": "slh-dna/authority-audit/v1",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "principle": "Signals are evidence, not authority.",
    "targets": results,
}

OUT.write_text(
    json.dumps(audit, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

print()
print("========================================")
print("       SLH DNA AUTHORITY AUDIT")
print("========================================")
print(f"Targets : {len(results)}")
print(f"Output  : {OUT}")
print()

for item in results:
    print(f"[{item['status']}] {item['path']}")

    if item["status"] == "PARSED":
        s = item["signals"]
        print(f"  main_guard    : {s['has_main']}")
        print(f"  main          : {s['has_main']}")
        print(f"  run           : {s['has_run']}")
        print(f"  start         : {s['has_start']}")
        print(f"  dispatch      : {s['has_dispatch']}")
        print(f"  handlers      : {s['has_handlers']}")
        print(f"  state writes  : {s['has_state_writes']}")
        print(f"  calls         : {item['call_count']}")
        print(f"  imports       : {len(item['imports'])}")

print()
print("IMPORTANT:")
print("This audit does NOT declare a canonical runtime.")
print("It only collects evidence.")
print("========================================")
