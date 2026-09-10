import state_manager
"""
SLH Agent Runtime Factory

Stage 21B:
Canonical DB agent record -> runtime agent instance.

The factory intentionally uses an explicit allow-list.
It does NOT dynamically import arbitrary names from state/db.json.
"""

from agents.echo import EchoAgent
from agents.system_guard import SystemGuardAgent
from agents.mission_executor import MissionExecutorAgent


AGENT_CLASS_MAP = {
    "EchoAgent": EchoAgent,
    "SystemGuardAgent": SystemGuardAgent,
    "MissionExecutorAgent": MissionExecutorAgent,
}


def register_agent_class(name, cls):
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Agent class name must be a non-empty string")
    if not callable(cls):
        raise TypeError("Agent class must be callable")
    AGENT_CLASS_MAP[name.strip()] = cls


def get_agent_class(class_name):
    if not class_name:
        return None
    return AGENT_CLASS_MAP.get(str(class_name))


def create_runtime_agent(class_name, **kwargs):
    cls = get_agent_class(class_name)
    if cls is None:
        raise KeyError(f"Runtime Agent class not registered: {class_name}")
    return cls(**kwargs)


def list_runtime_classes():
    return sorted(AGENT_CLASS_MAP.keys())


def create_agent_from_record(agent_record, **kwargs):
    if not isinstance(agent_record, dict):
        raise TypeError("Agent record must be a dictionary")
    runtime_class = agent_record.get("runtime_class")
    if not runtime_class:
        raise ValueError("Agent record has no runtime_class")
    return create_runtime_agent(runtime_class, **kwargs)


def load_agents_into_kernel(kernel, db=None):
    """
    Load canonical DB agents with explicitly registered runtime classes.
    If a DB object is supplied, use that exact object; otherwise read the
    canonical state through state_manager.
    """
    if db is None:
        db = state_manager.load_db()

    agents = db.get("agents", {}) if isinstance(db, dict) else {}

    report = {"loaded": [], "skipped": [], "errors": []}

    for agent_id, record in agents.items():
        if not isinstance(record, dict):
            report["errors"].append({"id": str(agent_id), "error": "invalid agent record"})
            continue

        runtime_class = record.get("runtime_class")
        if not runtime_class:
            report["skipped"].append({
                "id": str(agent_id),
                "name": record.get("name"),
                "reason": "missing runtime_class",
            })
            continue

        try:
            runtime_agent = create_validated_agent_from_record(record)
            kernel_name = str(record.get("name") or agent_id)
            kernel.register(kernel_name, runtime_agent)
            report["loaded"].append({
                "id": str(agent_id),
                "name": kernel_name,
                "runtime_class": runtime_class,
            })
        except Exception as exc:
            report["errors"].append({
                "id": str(agent_id),
                "name": record.get("name"),
                "runtime_class": runtime_class,
                "error": str(exc),
            })

    return report


RUNTIME_MANIFESTS = {
    "MissionExecutorAgent": {
        "name": "MissionExecutorAgent", "version": "1.0",
        "capabilities": ["mission_execution"], "read_only": True,
        "db_access": False, "external_io": False,
    },
    "EchoAgent": {
        "name": "EchoAgent", "version": "1.0",
        "capabilities": ["echo"], "read_only": True,
        "db_access": False, "external_io": False,
    },
    "SystemGuardAgent": {
        "name": "SystemGuardAgent", "version": "1.0",
        "capabilities": ["runtime_health", "event_validation"],
        "read_only": True, "db_access": False, "external_io": False,
    },
}


def get_runtime_manifest(class_name):
    if not class_name:
        return None
    class_name = str(class_name)
    if class_name not in AGENT_CLASS_MAP:
        return None
    manifest = RUNTIME_MANIFESTS.get(class_name)
    return dict(manifest) if manifest is not None else None


def get_agent_manifest(agent_record):
    if not isinstance(agent_record, dict):
        raise TypeError("Agent record must be a dictionary")
    runtime_class = agent_record.get("runtime_class")
    if not runtime_class:
        raise ValueError("Agent record has no runtime_class")
    manifest = get_runtime_manifest(runtime_class)
    if manifest is None:
        raise KeyError(f"No runtime manifest for: {runtime_class}")
    return manifest


def validate_agent_manifest(agent_record):
    if not isinstance(agent_record, dict):
        raise TypeError("Agent record must be a dictionary")
    runtime_class = agent_record.get("runtime_class")
    if not runtime_class:
        return {"ok": False, "reason": "missing runtime_class"}
    if runtime_class not in AGENT_CLASS_MAP:
        return {"ok": False, "reason": "runtime_class_not_registered", "runtime_class": runtime_class}
    manifest = RUNTIME_MANIFESTS.get(runtime_class)
    if manifest is None:
        return {"ok": False, "reason": "runtime_manifest_missing", "runtime_class": runtime_class}
    return {"ok": True, "runtime_class": runtime_class, "manifest": dict(manifest)}


def create_validated_agent_from_record(agent_record, **kwargs):
    validation = validate_agent_manifest(agent_record)
    if not validation["ok"]:
        raise PermissionError("Agent runtime validation failed: " + validation["reason"])
    return create_agent_from_record(agent_record, **kwargs)
