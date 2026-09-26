"""Canonical Telegram Bot registry backed by the SLH DB.

Bots are metadata/runtime records only. Secrets such as BOT_TOKEN must live
in Railway environment variables and are never persisted here.
"""

from datetime import datetime, timezone
from uuid import uuid4

import state_manager


_BOTS_KEY = "bots"
_ALLOWED_STATUSES = {"draft", "declared", "online", "offline", "degraded", "deploying", "retired", "error"}
_ALLOWED_LIFECYCLES = {"ACTIVE", "MIGRATION", "RETIRED"}
_ALLOWED_HEALTH = {"UNKNOWN", "HEALTHY", "DEGRADED", "DOWN"}
_ALLOWED_TELEMETRY = {"UNVERIFIED", "VERIFIED", "STALE"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _clean_username(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    return raw if raw.startswith("@") else "@" + raw


def _normalize(record):
    if not isinstance(record, dict):
        return None
    result = dict(record)
    result.setdefault("telegram_username", "")
    result.setdefault("role", "unclassified")
    result.setdefault("source", "unknown")
    result.setdefault("lifecycle", "ACTIVE")
    result.setdefault("health", "UNKNOWN")
    result.setdefault("telemetry_status", "UNVERIFIED")
    result.setdefault("last_heartbeat_at", None)
    result.setdefault("last_heartbeat_status", None)
    result.setdefault("last_heartbeat_details", {})
    return result


def _find_key(bots, identifier):
    raw = str(identifier or "").strip()
    if raw in bots:
        return raw
    lowered = raw.lower()
    for bot_id, record in bots.items():
        candidates = {
            str(record.get("id", "")).lower(),
            str(record.get("name", "")).lower(),
            str(record.get("bot_key", "")).lower(),
            str(record.get("telegram_username", "")).lower(),
        }
        if lowered in candidates:
            return bot_id
    return None


def create_bot(
    name,
    owner_id,
    bot_key=None,
    template="generic",
    telegram_username=None,
    role="unclassified",
    source="bot_factory",
    lifecycle="ACTIVE",
):
    name = str(name).strip()
    if not name:
        raise ValueError("Bot name cannot be empty")
    owner_id = str(owner_id).strip()
    if not owner_id:
        raise ValueError("Bot owner_id cannot be empty")
    template = str(template).strip() or "generic"
    lifecycle = str(lifecycle).strip().upper() or "ACTIVE"
    if lifecycle not in _ALLOWED_LIFECYCLES:
        raise ValueError("INVALID_LIFECYCLE")

    def mutate(db):
        bots = db.setdefault(_BOTS_KEY, {})
        username = _clean_username(telegram_username)
        for record in bots.values():
            same_owner = str(record.get("owner_id", "")) == owner_id
            same_name = str(record.get("name", "")).lower() == name.lower()
            same_username = username and str(record.get("telegram_username", "")).lower() == username.lower()
            if same_owner and (same_name or same_username):
                raise ValueError(f"Bot '{name}' already exists for this owner")

        bot_id = "BOT_" + uuid4().hex[:12]
        now = _now()
        record = {
            "id": bot_id,
            "name": name,
            "bot_key": str(bot_key).strip() if bot_key else bot_id,
            "telegram_username": username,
            "template": template,
            "role": str(role or "unclassified"),
            "source": str(source or "unknown"),
            "owner_id": owner_id,
            "railway_project_id": None,
            "railway_service_id": None,
            "railway_environment_id": None,
            "status": "draft",
            "lifecycle": lifecycle,
            "health": "UNKNOWN",
            "telemetry_status": "UNVERIFIED",
            "last_heartbeat_at": None,
            "last_heartbeat_status": None,
            "last_heartbeat_details": {},
            "created_at": now,
            "updated_at": now,
        }
        bots[bot_id] = record
        return dict(record)

    return state_manager.atomic_update(mutate)


def register_declared_bot(username, owner_id, name=None, role="unclassified", source="botfather_declared"):
    username = _clean_username(username)
    if not username:
        raise ValueError("Bot username cannot be empty")
    display_name = str(name or username.lstrip("@")).strip()

    def mutate(db):
        bots = db.setdefault(_BOTS_KEY, {})
        existing_key = _find_key(bots, username)
        now = _now()
        if existing_key:
            record = bots[existing_key]
            record["telegram_username"] = username
            if display_name:
                record["name"] = display_name
            record["role"] = str(role or record.get("role") or "unclassified")
            record["source"] = str(source or record.get("source") or "unknown")
            if str(record.get("lifecycle", "")).upper() not in _ALLOWED_LIFECYCLES:
                record["lifecycle"] = "ACTIVE"
            if str(record.get("status", "")).lower() == "draft":
                record["status"] = "declared"
            record["telemetry_status"] = str(record.get("telemetry_status") or "UNVERIFIED")
            record["updated_at"] = now
            return dict(record)

        bot_id = "BOT_" + uuid4().hex[:12]
        record = {
            "id": bot_id,
            "name": display_name,
            "bot_key": username.lstrip("@"),
            "telegram_username": username,
            "template": "generic",
            "role": str(role or "unclassified"),
            "source": str(source or "botfather_declared"),
            "owner_id": str(owner_id),
            "railway_project_id": None,
            "railway_service_id": None,
            "railway_environment_id": None,
            "status": "declared",
            "lifecycle": "ACTIVE",
            "health": "UNKNOWN",
            "telemetry_status": "UNVERIFIED",
            "last_heartbeat_at": None,
            "last_heartbeat_status": None,
            "last_heartbeat_details": {},
            "created_at": now,
            "updated_at": now,
        }
        bots[bot_id] = record
        return dict(record)

    return state_manager.atomic_update(mutate)


def ensure_runtime_bot(name, owner_id, telegram_username=None, role="control_plane"):
    username = _clean_username(telegram_username)

    def mutate(db):
        bots = db.setdefault(_BOTS_KEY, {})
        key = _find_key(bots, username) if username else _find_key(bots, name)
        now = _now()
        if key:
            record = bots[key]
            record.update({
                "name": str(name).strip() or record.get("name"),
                "telegram_username": username or record.get("telegram_username", ""),
                "role": role,
                "source": "runtime",
                "status": "online",
                "lifecycle": "ACTIVE",
                "updated_at": now,
            })
            return dict(record)

        bot_id = "BOT_" + uuid4().hex[:12]
        record = {
            "id": bot_id,
            "name": str(name).strip(),
            "bot_key": username.lstrip("@") if username else bot_id,
            "telegram_username": username,
            "template": "generic",
            "role": role,
            "source": "runtime",
            "owner_id": str(owner_id),
            "railway_project_id": None,
            "railway_service_id": None,
            "railway_environment_id": None,
            "status": "online",
            "lifecycle": "ACTIVE",
            "health": "UNKNOWN",
            "telemetry_status": "UNVERIFIED",
            "last_heartbeat_at": None,
            "last_heartbeat_status": None,
            "last_heartbeat_details": {},
            "created_at": now,
            "updated_at": now,
        }
        bots[bot_id] = record
        return dict(record)

    return state_manager.atomic_update(mutate)


def record_heartbeat(identifier, status="ok", details=None):
    status = str(status or "ok").strip().lower()
    health = "HEALTHY" if status in {"ok", "healthy", "online"} else "DEGRADED"
    if status in {"down", "offline", "error", "failed"}:
        health = "DOWN"

    def mutate(db):
        bots = db.setdefault(_BOTS_KEY, {})
        key = _find_key(bots, identifier)
        if not key:
            raise KeyError(f"Bot '{identifier}' not found")
        record = bots[key]
        record["health"] = health
        record["telemetry_status"] = "VERIFIED"
        record["last_heartbeat_at"] = _now()
        record["last_heartbeat_status"] = status
        record["last_heartbeat_details"] = dict(details or {})
        record["status"] = "online" if health == "HEALTHY" else ("offline" if health == "DOWN" else "degraded")
        record["updated_at"] = _now()
        return dict(record)

    return state_manager.atomic_update(mutate)


def get_bot(identifier):
    db = state_manager.load_db()
    key = _find_key(db.get(_BOTS_KEY, {}) if isinstance(db.get(_BOTS_KEY, {}), dict) else {}, identifier)
    if not key:
        return None
    return _normalize(db[_BOTS_KEY][key])


def list_bots(owner_id=None):
    db = state_manager.load_db()
    bots = db.get(_BOTS_KEY, {})
    bots = bots if isinstance(bots, dict) else {}
    records = []
    owner = str(owner_id) if owner_id is not None else None
    for record in bots.values():
        if owner is not None and str(record.get("owner_id")) != owner:
            continue
        records.append(_normalize(record))
    return sorted(records, key=lambda x: str(x.get("created_at", "")))


def update_bot(identifier, **changes):
    allowed = {
        "name",
        "bot_key",
        "telegram_username",
        "template",
        "role",
        "source",
        "railway_project_id",
        "railway_service_id",
        "railway_environment_id",
        "status",
        "lifecycle",
        "health",
        "telemetry_status",
        "last_heartbeat_at",
        "last_heartbeat_status",
        "last_heartbeat_details",
    }
    unknown = set(changes) - allowed
    if unknown:
        raise ValueError("Unsupported bot fields: " + ", ".join(sorted(unknown)))

    def mutate(db):
        bots = db.setdefault(_BOTS_KEY, {})
        key = _find_key(bots, identifier)
        if not key:
            raise KeyError(f"Bot '{identifier}' not found")

        record = bots[key]
        if "telegram_username" in changes and changes["telegram_username"] is not None:
            changes["telegram_username"] = _clean_username(changes["telegram_username"])
        if "lifecycle" in changes and changes["lifecycle"] is not None:
            lifecycle = str(changes["lifecycle"]).upper()
            if lifecycle not in _ALLOWED_LIFECYCLES:
                raise ValueError("INVALID_LIFECYCLE")
            changes["lifecycle"] = lifecycle
        if "status" in changes and changes["status"] is not None:
            status = str(changes["status"]).lower()
            if status not in _ALLOWED_STATUSES:
                raise ValueError("INVALID_BOT_STATUS")
            changes["status"] = status
        if "health" in changes and changes["health"] is not None:
            health = str(changes["health"]).upper()
            if health not in _ALLOWED_HEALTH:
                raise ValueError("INVALID_HEALTH")
            changes["health"] = health
        if "telemetry_status" in changes and changes["telemetry_status"] is not None:
            telemetry = str(changes["telemetry_status"]).upper()
            if telemetry not in _ALLOWED_TELEMETRY:
                raise ValueError("INVALID_TELEMETRY_STATUS")
            changes["telemetry_status"] = telemetry

        record.update({k: v for k, v in changes.items() if v is not None})
        record["updated_at"] = _now()
        return dict(record)

    return state_manager.atomic_update(mutate)


def delete_bot(identifier):
    def mutate(db):
        bots = db.setdefault(_BOTS_KEY, {})
        key = _find_key(bots, identifier)
        if not key:
            raise KeyError(f"Bot '{identifier}' not found")
        del bots[key]
        return key

    return state_manager.atomic_update(mutate)
