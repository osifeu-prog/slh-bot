#!/usr/bin/env python3

import json
import hashlib
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DB = ROOT / "state" / "db.json"
SNAPSHOT = ROOT / "state" / "agents.json"
MANIFEST = ROOT / "state" / "takeover" / "manifest.json"

BACKUP_ROOT = ROOT / "state" / "snapshots" / "agent_state_autopilot"

def now():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def sha256(path):
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()

def load_json(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ INVALID JSON: {path}")
        print(repr(e))
        return None

def save_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    tmp.replace(path)

def db_agents(data):
    if not isinstance(data, dict):
        return {}
    agents = data.get("agents", {})
    return agents if isinstance(agents, dict) else {}

def snapshot_agents(data):
    if not isinstance(data, dict):
        return {}
    return data if isinstance(data, dict) else {}

def manifest_agents(data):
    if not isinstance(data, dict):
        return {}

    section = data.get("agents", {})

    if not isinstance(section, dict):
        return {}

    items = section.get("items", [])

    if not isinstance(items, list):
        return {}

    result = {}

    for agent in items:
        if isinstance(agent, dict) and "id" in agent:
            result[str(agent["id"])] = agent

    return result

def make_backup():
    target = BACKUP_ROOT / now()
    target.mkdir(parents=True, exist_ok=True)

    for path in (DB, SNAPSHOT, MANIFEST):
        if path.exists():
            shutil.copy2(
                path,
                target / path.name
            )

    print("✅ BACKUP CREATED:")
    print(target)

    return target

def build_snapshot(db_map):
    result = {}

    for agent_id, agent in db_map.items():

        if not isinstance(agent, dict):
            continue

        result[str(agent_id)] = {
            "id": str(agent_id),
            "name": agent.get("name"),
            "role": agent.get("role", "agent"),
            "state": agent.get("state", "idle"),
            "inbox": agent.get("inbox", []),
            "permissions": agent.get("permissions", [])
        }

    return result

def main():

    print("=" * 80)
    print("SLH AGENT STATE AUTOPILOT")
    print("=" * 80)

    if not DB.exists():
        print("❌ DB NOT FOUND")
        return 1

    db = load_json(DB)
    snapshot = load_json(SNAPSHOT)
    manifest = load_json(MANIFEST)

    if db is None:
        return 1

    db_map = db_agents(db)
    snapshot_map = snapshot_agents(snapshot)
    manifest_map = manifest_agents(manifest)

    db_ids = set(map(str, db_map.keys()))
    snapshot_ids = set(map(str, snapshot_map.keys()))
    manifest_ids = set(map(str, manifest_map.keys()))

    print()
    print("LIVE SOURCE:")
    print("state/db.json")

    print()
    print("COUNTS")
    print("DB       :", len(db_ids))
    print("SNAPSHOT :", len(snapshot_ids))
    print("MANIFEST :", len(manifest_ids))

    print()
    print("DRIFT DETECTION")

    drift = []

    for agent_id in sorted(
        db_ids | snapshot_ids | manifest_ids,
        key=lambda x: (len(x), x)
    ):

        db_agent = db_map.get(agent_id, {})
        snapshot_agent = snapshot_map.get(agent_id, {})
        manifest_agent = manifest_map.get(agent_id, {})

        db_state = db_agent.get("state")
        snapshot_state = snapshot_agent.get("state")
        manifest_state = manifest_agent.get("state")

        if db_state != snapshot_state:
            drift.append(
                (
                    agent_id,
                    "DB vs SNAPSHOT",
                    db_state,
                    snapshot_state
                )
            )

        if (
            manifest_agent
            and db_state != manifest_state
        ):
            drift.append(
                (
                    agent_id,
                    "DB vs MANIFEST",
                    db_state,
                    manifest_state
                )
            )

    if drift:

        print()
        print("⚠️ DRIFT FOUND:")

        for item in drift:
            print(
                f"Agent {item[0]} | "
                f"{item[1]} | "
                f"DB={item[2]} | "
                f"OTHER={item[3]}"
            )

    else:
        print("✅ NO STATE DRIFT")

    print()
    print("AUTOMATIC ACTION")
    print("----------------")

    print("1. Backup current state")
    backup = make_backup()

    print()
    print("2. Rebuild state/agents.json from state/db.json")

    new_snapshot = build_snapshot(db_map)

    save_json(
        SNAPSHOT,
        new_snapshot
    )

    print("✅ SNAPSHOT REBUILT")

    print()
    print("3. Verify rebuilt snapshot")

    verified_snapshot = load_json(SNAPSHOT)
    verified_map = snapshot_agents(verified_snapshot)

    if set(map(str, verified_map.keys())) != db_ids:
        print("❌ SNAPSHOT VERIFICATION FAILED")
        print("Restoring backup...")

        shutil.copy2(
            backup / "agents.json",
            SNAPSHOT
        )

        return 1

    for agent_id in db_ids:

        db_state = db_map[agent_id].get("state")
        snapshot_state = verified_map[agent_id].get("state")

        if db_state != snapshot_state:

            print(
                f"❌ STATE VERIFICATION FAILED "
                f"FOR AGENT {agent_id}"
            )

            shutil.copy2(
                backup / "agents.json",
                SNAPSHOT
            )

            return 1

    print("✅ SNAPSHOT VERIFIED")

    print()
    print("4. Manifest status")

    if manifest:

        manifest_map = manifest_agents(manifest)

        manifest_drift = []

        for agent_id in db_ids & set(manifest_map):

            db_state = db_map[agent_id].get("state")
            manifest_state = manifest_map[agent_id].get("state")

            if db_state != manifest_state:

                manifest_drift.append(
                    (
                        agent_id,
                        db_state,
                        manifest_state
                    )
                )

        if manifest_drift:

            print(
                "⚠️ MANIFEST DRIFT REMAINS"
            )

            for agent_id, db_state, manifest_state in manifest_drift:

                print(
                    f"Agent {agent_id}: "
                    f"DB={db_state} "
                    f"MANIFEST={manifest_state}"
                )

            print()
            print(
                "ℹ️ MANIFEST WAS NOT MODIFIED."
            )
            print(
                "It remains a historical/takeover record."
            )

        else:

            print(
                "✅ MANIFEST MATCHES DB"
            )

    print()
    print("=" * 80)
    print("AUTOPILOT COMPLETE")
    print("=" * 80)

    print("DB SHA256      :", sha256(DB))
    print("SNAPSHOT SHA256:", sha256(SNAPSHOT))

    print()
    print("BACKUP:")
    print(backup)

    print()
    print("RESULT:")
    print("✅ DB preserved")
    print("✅ Snapshot rebuilt from DB")
    print("✅ Snapshot verified")
    print("✅ Backup created")
    print("ℹ️ Manifest not automatically rewritten")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
