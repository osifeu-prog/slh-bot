import state_manager
from pathlib import Path
import json
import hashlib
from datetime import datetime, timezone

ROOT = Path(".")
OUT = ROOT / "state" / "takeover" / "manifest.json"


def load_json(path, default):
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def file_info(path):
    return {
        "exists": path.exists(),
        "path": str(path),
        "size_bytes": path.stat().st_size if path.exists() else 0,
    }


def sha256_file(path):
    if not path.exists():
        return None

    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)

    return h.hexdigest()


db_path = ROOT / "state" / "db.json"
board_path = ROOT / "state" / "missions" / "board.json"
rewards_path = ROOT / "state" / "rewards_ledger.json"
memory_path = ROOT / "state" / "system_memory.json"
audit_path = ROOT / "state" / "audit.jsonl"

task_service_path = ROOT / "services" / "task_service.py"
task_handler_path = ROOT / "handlers" / "task_handler.py"
ownership_path = ROOT / "handlers" / "ownership_transfer_handler.py"
registry_path = ROOT / "core" / "agent_registry.py"
audit_module_path = ROOT / "core" / "audit.py"


db = load_json(db_path, {})
agents = state_manager.get_agents() if isinstance(db, dict) else {}

board = load_json(board_path, {"missions": []})
missions = board.get("missions", []) if isinstance(board, dict) else []

rewards = load_json(rewards_path, [])
if not isinstance(rewards, list):
    rewards = []

system_memory = load_json(memory_path, {})


agent_items = []

for agent_id, agent in agents.items():
    if not isinstance(agent, dict):
        continue

    inbox = agent.get("inbox", [])
    permissions = agent.get("permissions", [])

    agent_items.append({
        "id": str(agent_id),
        "name": agent.get("name"),
        "role": agent.get("role"),
        "state": agent.get("state"),
        "inbox_count": len(inbox) if isinstance(inbox, list) else 0,
        "permissions_count": (
            len(permissions)
            if isinstance(permissions, list)
            else 0
        ),
    })


agent_states = {}

for agent in agent_items:
    state = agent.get("state") or "unknown"
    agent_states[state] = agent_states.get(state, 0) + 1


open_missions = []
assigned_missions = []
completed_missions = []

agent_ids = set(str(k) for k in agents.keys())

agent_names = set(
    str(agent.get("name", "")).lower()
    for agent in agents.values()
    if isinstance(agent, dict)
)

invalid_agent_references = []

for mission in missions:

    if not isinstance(mission, dict):
        continue

    status = mission.get("status")
    target = mission.get("assigned_to")

    if status == "open":
        open_missions.append(mission)

    elif status == "assigned":
        assigned_missions.append(mission)

    elif status == "done":
        completed_missions.append(mission)

    if target:

        target_str = str(target)

        if (
            target_str not in agent_ids
            and target_str.lower() not in agent_names
        ):
            invalid_agent_references.append({
                "mission_id": mission.get("id"),
                "assigned_to": target,
            })


mission_ids = [
    mission.get("id")
    for mission in missions
    if isinstance(mission, dict)
]

duplicate_mission_ids = sorted({
    mid
    for mid in mission_ids
    if mission_ids.count(mid) > 1
})


mission_id_set = set(str(mid) for mid in mission_ids)

orphan_rewards = []

for reward in rewards:

    if not isinstance(reward, dict):
        continue

    mission_id = str(reward.get("mission_id"))

    if mission_id not in mission_id_set:
        orphan_rewards.append(reward)


task_service_exists = task_service_path.exists()
task_handler_exists = task_handler_path.exists()

tasks_db = db.get("tasks", {}) if isinstance(db, dict) else {}

if isinstance(tasks_db, dict):
    task_count = len(tasks_db)
elif isinstance(tasks_db, list):
    task_count = len(tasks_db)
else:
    task_count = 0


issues = []

if invalid_agent_references:
    issues.append("invalid_agent_references")

if duplicate_mission_ids:
    issues.append("duplicate_mission_ids")

if orphan_rewards:
    issues.append("orphan_rewards")

if not registry_path.exists():
    issues.append("agent_registry_missing")

if not task_service_exists:
    issues.append("task_service_missing")

if not memory_path.exists():
    issues.append("system_memory_missing")


takeover_status = (
    "PARTIAL"
    if issues
    else "READY_FOR_LAYER"
)


manifest = {
    "manifest_version": "1.0",

    "system": {
        "name": "SLH OS",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generation_mode": "read_only_derived_snapshot",
        "takeover_status": takeover_status,
    },

    "agents": {
        "total": len(agent_items),
        "states": agent_states,
        "items": agent_items,
    },

    "missions": {
        "total": len(missions),
        "open": len(open_missions),
        "assigned": len(assigned_missions),
        "done": len(completed_missions),
        "duplicate_ids": duplicate_mission_ids,
        "invalid_agent_references": len(
            invalid_agent_references
        ),
        "open_items": [
            {
                "id": mission.get("id"),
                "description": mission.get("desc"),
                "assigned_to": mission.get("assigned_to"),
                "reward": mission.get("reward"),
            }
            for mission in open_missions
        ],
    },

    "rewards": {
        "ledger_exists": rewards_path.exists(),
        "entries": len(rewards),
        "orphan_entries": len(orphan_rewards),
    },

    "tasks": {
        "service_exists": task_service_exists,
        "handler_exists": task_handler_exists,
        "database_count": task_count,
        "architecture_status": (
            "parallel_with_missions"
            if task_service_exists
            else "not_available"
        ),
    },

    "knowledge": {
        "system_memory": {
            "exists": memory_path.exists(),
            "status": (
                "active"
                if memory_path.exists()
                else "missing"
            ),
        },
        "audit_module": {
            "exists": audit_module_path.exists(),
            "status": (
                "active"
                if audit_module_path.exists()
                else "missing"
            ),
        },
        "audit_log": {
            "exists": audit_path.exists(),
            "status": (
                "active"
                if audit_path.exists()
                else "not_initialized"
            ),
        },
        "knowledge_base": {
            "status": "not_implemented",
        },
    },

    "ownership": {
        "system_identity_module": file_info(
            ROOT / "core" / "identity.py"
        ),
        "formal_takeover_layer": False,
        "formal_knowledge_transfer": False,
        "mission_responsibility": True,
        "device_ownership": True,
    },

    "verification": {
        "agent_registry": {
            "status": (
                "verified"
                if registry_path.exists()
                else "missing"
            ),
            "source": str(registry_path),
        },
        "mission_board": {
            "status": (
                "verified"
                if board_path.exists()
                else "missing"
            ),
            "source": str(board_path),
        },
        "mission_integrity": {
            "status": (
                "verified"
                if (
                    not invalid_agent_references
                    and not duplicate_mission_ids
                )
                else "issues_found"
            ),
            "invalid_agent_references": len(
                invalid_agent_references
            ),
            "duplicate_ids": len(
                duplicate_mission_ids
            ),
        },
        "rewards": {
            "status": (
                "verified"
                if not orphan_rewards
                else "issues_found"
            ),
            "orphan_entries": len(orphan_rewards),
        },
        "system_memory": {
            "status": (
                "verified"
                if memory_path.exists()
                else "missing"
            ),
        },
    },

    "system_memory_summary": {
        "memory_version": system_memory.get(
            "memory_version"
        ),
        "milestone": system_memory.get(
            "milestone"
        ),
        "next_phase": system_memory.get(
            "next_phase"
        ),
        "goal": system_memory.get(
            "goal"
        ),
    },

    "source_files": {
        "db": file_info(db_path),
        "missions": file_info(board_path),
        "rewards": file_info(rewards_path),
        "system_memory": file_info(memory_path),
        "audit": file_info(audit_path),
        "agent_registry": file_info(registry_path),
        "task_service": file_info(task_service_path),
        "task_handler": file_info(task_handler_path),
        "ownership_handler": file_info(ownership_path),
        "audit_module": file_info(audit_module_path),
    },

    "integrity": {
        "source_sha256": {
            "db": sha256_file(db_path),
            "missions": sha256_file(board_path),
            "system_memory": sha256_file(memory_path),
            "agent_registry": sha256_file(registry_path),
        },
        "issues": issues,
    },
}


OUT.parent.mkdir(parents=True, exist_ok=True)

OUT.write_text(
    json.dumps(
        manifest,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)


print("=" * 80)
print("        SLH TAKEOVER MANIFEST GENERATED")
print("=" * 80)
print("FILE:", OUT)
print("STATUS:", takeover_status)
print("AGENTS:", len(agent_items))
print("MISSIONS:", len(missions))
print("OPEN MISSIONS:", len(open_missions))
print("ASSIGNED MISSIONS:", len(assigned_missions))
print("DONE MISSIONS:", len(completed_missions))
print("TASKS:", task_count)
print("REWARDS:", len(rewards))
print("ISSUES:", len(issues))

if issues:
    print()
    print("ISSUES:")
    for issue in issues:
        print(" -", issue)

print()
print("MANIFEST CREATED")
