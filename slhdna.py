from pathlib import Path
import json
import hashlib
import shutil
import subprocess
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
DNA_ROOT = ROOT / "_slh_map" / "dna"
SCANS_ROOT = ROOT / "_slh_map" / "scans"
CURRENT_SCAN = ROOT / "_slh_map" / "system_map.json"
CURRENT_SUMMARY = ROOT / "_slh_map" / "summary.json"

for p in [DNA_ROOT, SCANS_ROOT]:
    p.mkdir(parents=True, exist_ok=True)

FILES = {
    "DNA.json": DNA_ROOT / "DNA.json",
    "CURRENT.json": DNA_ROOT / "CURRENT.json",
    "AUTHORITY.json": DNA_ROOT / "AUTHORITY.json",
    "DECISIONS.json": DNA_ROOT / "DECISIONS.json",
    "FINDINGS.json": DNA_ROOT / "FINDINGS.json",
    "RISKS.json": DNA_ROOT / "RISKS.json",
    "TODO.json": DNA_ROOT / "TODO.json",
    "HISTORY.jsonl": DNA_ROOT / "HISTORY.jsonl",
}

NOW = datetime.now(timezone.utc).isoformat()


def load_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    tmp.replace(path)


def append_history(event, data=None):
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "data": data or {},
    }
    with FILES["HISTORY.jsonl"].open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def ensure_file(name, default):
    if not FILES[name].exists():
        save_json(FILES[name], default)


def initialize():
    dna = {
        "schema": "slh-dna/v1",
        "created_at": NOW,
        "updated_at": NOW,
        "project": "main",
        "root": str(ROOT),
        "principles": [
            "DNA is the persistent project source of truth.",
            "Scans are immutable snapshots.",
            "Signals are not automatically treated as authority.",
            "Existing code is not deleted by mapping.",
            "PowerShell and Telegram must consume the same DNA state.",
        ],
        "current_scan": None,
        "canonical_entrypoints": [],
        "canonical_commands": [],
        "state_authorities": [],
    }

    ensure_file("DNA.json", dna)
    ensure_file("CURRENT.json", {
        "schema": "slh-dna/current/v1",
        "updated_at": NOW,
        "scan": None,
        "health": {},
        "hotspots": [],
        "parse_errors": [],
        "next_actions": [],
    })
    ensure_file("AUTHORITY.json", {
        "schema": "slh-dna/authority/v1",
        "entrypoints": [],
        "commands": [],
        "state": [],
        "services": [],
        "status": "classification_required",
    })
    ensure_file("DECISIONS.json", {
        "schema": "slh-dna/decisions/v1",
        "decisions": [],
    })
    ensure_file("FINDINGS.json", {
        "schema": "slh-dna/findings/v1",
        "findings": [],
    })
    ensure_file("RISKS.json", {
        "schema": "slh-dna/risks/v1",
        "risks": [],
    })
    ensure_file("TODO.json", {
        "schema": "slh-dna/todo/v1",
        "items": [],
    })

    append_history("DNA_INITIALIZED", {
        "schema": "slh-dna/v1"
    })


def import_current_scan():
    if not CURRENT_SCAN.exists():
        print("ERROR: _slh_map/system_map.json not found.")
        return False

    system_map = load_json(CURRENT_SCAN, {})
    summary = load_json(CURRENT_SUMMARY, {})

    if not system_map.get("nodes"):
        print("ERROR: system map contains no nodes.")
        return False

    timestamp = system_map.get("generated_at", NOW)
    safe_timestamp = (
        timestamp.replace(":", "")
        .replace("+00", "Z")
        .replace(".", "_")
    )

    snapshot_dir = SCANS_ROOT / safe_timestamp
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(CURRENT_SCAN, snapshot_dir / "system_map.json")

    if CURRENT_SUMMARY.exists():
        shutil.copy2(CURRENT_SUMMARY, snapshot_dir / "summary.json")

    nodes = system_map.get("nodes", [])
    errors = [
        n for n in nodes
        if n.get("parse_error")
    ]

    hotspots = sorted(
        [
            {
                "path": n.get("path"),
                "module": n.get("module"),
                "calls": len(n.get("calls", [])),
                "imports": len(n.get("imports", [])),
                "entrypoint_signals": n.get("entrypoint_signals", []),
            }
            for n in nodes
        ],
        key=lambda x: (
            x["calls"],
            x["imports"],
        ),
        reverse=True,
    )[:30]

    current = load_json(FILES["CURRENT.json"], {})

    current.update({
        "updated_at": NOW,
        "scan": {
            "generated_at": timestamp,
            "snapshot": str(snapshot_dir.relative_to(ROOT)).replace("\\", "/"),
            "files": summary.get("files", len(nodes)),
            "edges": summary.get("edges", len(system_map.get("edges", []))),
        },
        "health": {
            "parse_errors": len(errors),
            "entrypoint_candidates": summary.get("entrypoint_candidates", 0),
            "command_candidates": summary.get("command_candidates", 0),
            "state_read_candidates": summary.get("state_read_candidates", 0),
            "state_write_candidates": summary.get("state_write_candidates", 0),
        },
        "hotspots": hotspots,
        "parse_errors": [
            {
                "path": n.get("path"),
                "error": n.get("parse_error"),
            }
            for n in errors
        ],
        "next_actions": [],
    })

    next_actions = []

    if errors:
        next_actions.append({
            "priority": "P0",
            "action": f"Resolve {len(errors)} Python parse errors.",
            "reason": "Broken parsing reduces map confidence."
        })

    if summary.get("entrypoint_candidates", 0) > 50:
        next_actions.append({
            "priority": "P1",
            "action": "Classify entrypoint candidates into canonical/legacy/unknown.",
            "reason": "Entrypoint signal count is high."
        })

    if summary.get("state_write_candidates", 0) < 5:
        next_actions.append({
            "priority": "P1",
            "action": "Audit state write authority.",
            "reason": "AST heuristic detected very few state writes."
        })

    next_actions.append({
        "priority": "P1",
        "action": "Classify runtime authority for bot_stable.py, bot_gateway.py and SLH_MAIN.py.",
        "reason": "Multiple runtime entrypoint signals exist."
    })

    current["next_actions"] = next_actions

    save_json(FILES["CURRENT.json"], current)

    dna = load_json(FILES["DNA.json"], {})
    dna["updated_at"] = NOW
    dna["current_scan"] = current["scan"]
    save_json(FILES["DNA.json"], dna)

    append_history("SCAN_IMPORTED", {
        "snapshot": str(snapshot_dir.relative_to(ROOT)).replace("\\", "/"),
        "files": len(nodes),
        "edges": len(system_map.get("edges", [])),
        "parse_errors": len(errors),
    })

    return True


def status():
    dna = load_json(FILES["DNA.json"], {})
    current = load_json(FILES["CURRENT.json"], {})
    h = current.get("health", {})

    print()
    print("========================================")
    print("             SLH DNA STATUS")
    print("========================================")
    print(f"Project        : {dna.get('project', 'unknown')}")
    print(f"Schema         : {dna.get('schema', 'unknown')}")
    print(f"Last scan      : {current.get('scan', {}).get('generated_at', 'NONE')}")
    print(f"Python files   : {current.get('scan', {}).get('files', 0)}")
    print(f"Import edges   : {current.get('scan', {}).get('edges', 0)}")
    print(f"Parse errors   : {h.get('parse_errors', 0)}")
    print(f"Entrypoints    : {h.get('entrypoint_candidates', 0)}")
    print(f"Commands       : {h.get('command_candidates', 0)}")
    print(f"State reads    : {h.get('state_read_candidates', 0)}")
    print(f"State writes   : {h.get('state_write_candidates', 0)}")
    print()
    print("NEXT:")
    for item in current.get("next_actions", []):
        print(f"[{item.get('priority')}] {item.get('action')}")
    print("========================================")
    print()


def hotspots():
    current = load_json(FILES["CURRENT.json"], {})

    print()
    print("========================================")
    print("             SLH DNA HOTSPOTS")
    print("========================================")

    for i, n in enumerate(current.get("hotspots", [])[:25], 1):
        print(
            f"{i:02d}. "
            f"{n.get('calls', 0):4d} calls | "
            f"{n.get('imports', 0):2d} imports | "
            f"{n.get('path')}"
        )

    print("========================================")
    print()


def errors():
    current = load_json(FILES["CURRENT.json"], {})
    items = current.get("parse_errors", [])

    print()
    print("========================================")
    print("             SLH DNA ERRORS")
    print("========================================")

    if not items:
        print("No parse errors recorded.")
    else:
        for item in items:
            print(f"\nFILE: {item.get('path')}")
            print(f"ERR : {item.get('error')}")

    print("========================================")
    print()


def authority():
    data = load_json(FILES["AUTHORITY.json"], {})

    print()
    print("========================================")
    print("           SLH DNA AUTHORITY")
    print("========================================")
    print(f"Status: {data.get('status')}")
    print()
    print("Canonical entrypoints:")
    for x in data.get("entrypoints", []):
        print(f"  - {x}")
    print()
    print("Canonical commands:")
    for x in data.get("commands", []):
        print(f"  - {x}")
    print()
    print("State authorities:")
    for x in data.get("state", []):
        print(f"  - {x}")
    print("========================================")
    print()


def continuation():
    current = load_json(FILES["CURRENT.json"], {})
    dna = load_json(FILES["DNA.json"], {})
    todo = load_json(FILES["TODO.json"], {})

    print()
    print("========================================")
    print("          SLH DNA CONTINUATION")
    print("========================================")
    print(f"Project : {dna.get('project')}")
    print(f"Scan    : {current.get('scan', {}).get('generated_at', 'NONE')}")
    print()

    print("KNOWN:")
    print(f"  Files       : {current.get('scan', {}).get('files', 0)}")
    print(f"  Edges       : {current.get('scan', {}).get('edges', 0)}")
    print(f"  Parse errs  : {current.get('health', {}).get('parse_errors', 0)}")

    print()
    print("NEXT ACTIONS:")
    for item in current.get("next_actions", []):
        print(f"  [{item.get('priority')}] {item.get('action')}")

    print()
    print("TODO:")
    for item in todo.get("items", [])[:20]:
        print(f"  [{item.get('status', 'open')}] {item.get('title')}")

    print("========================================")
    print()


def snapshot():
    import_current_scan()

    current = load_json(FILES["CURRENT.json"], {})
    snap = {
        "schema": "slh-dna/snapshot/v1",
        "created_at": NOW,
        "project": "main",
        "current": current,
        "dna": load_json(FILES["DNA.json"], {}),
        "authority": load_json(FILES["AUTHORITY.json"], {}),
        "decisions": load_json(FILES["DECISIONS.json"], {}),
        "findings": load_json(FILES["FINDINGS.json"], {}),
        "risks": load_json(FILES["RISKS.json"], {}),
        "todo": load_json(FILES["TODO.json"], {}),
    }

    out = DNA_ROOT / "LAST_SNAPSHOT.json"
    save_json(out, snap)

    append_history("SNAPSHOT_CREATED", {
        "path": str(out.relative_to(ROOT)).replace("\\", "/")
    })

    print(f"SNAPSHOT: {out}")


def export_bundle():
    snapshot()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = SCANS_ROOT / f"DNA_EXPORT_{stamp}"
    out.mkdir(parents=True, exist_ok=True)

    for name, path in FILES.items():
        if path.exists():
            shutil.copy2(path, out / name)

    if CURRENT_SCAN.exists():
        shutil.copy2(CURRENT_SCAN, out / "system_map.json")

    if CURRENT_SUMMARY.exists():
        shutil.copy2(CURRENT_SUMMARY, out / "summary.json")

    print(f"EXPORT: {out}")


def main():
    import sys

    command = sys.argv[1].lower() if len(sys.argv) > 1 else "status"

    initialize()

    if command == "init":
        print("SLH DNA initialized.")
    elif command == "scan":
        script = ROOT / "slh_dna_scan.py"
        if not script.exists():
            print("ERROR: slh_dna_scan.py not found.")
            return 1
        subprocess.run(["python", str(script)], check=False)
        import_current_scan()
    elif command == "status":
        status()
    elif command == "hotspots":
        hotspots()
    elif command == "errors":
        errors()
    elif command == "authority":
        authority()
    elif command == "continue":
        continuation()
    elif command == "snapshot":
        snapshot()
    elif command == "export":
        export_bundle()
    else:
        print(
            "Usage: slhdna "
            "{init|scan|status|hotspots|errors|authority|continue|snapshot|export}"
        )
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
