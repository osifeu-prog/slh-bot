"""Canonical Telegram Bot registry backed by the SLH DB.

Bots are metadata/runtime records only. Secrets such as BOT_TOKEN must live
in Railway environment variables and are never persisted here.
"""

from datetime import datetime, timezone
from uuid import uuid4

import state_manager


_BOTS_KEY = "bots"


def _now():
    return datetime.now(timezone.utc).isoformat()


def _normalize(record):
    if not isinstance(record, dict):
        return None
    return dict(record)


def create_bot(name, owner_id, bot_key=None, template="generic"):
    name = str(name).strip()
    if not name:
        raise ValueError("Bot name cannot be empty")
    owner_id = str(owner_id).strip()
    if not owner_id:
        raise ValueError("Bot owner_id cannot be empty")
    template = str(template).strip() or "generic"

    def mutate(db):
        bots = db.setdefault(_BOTS_KEY, {})
        for bot in bots.values():
            if (
                str(bot.get("name", "")).lower() == name.lower()
                and str(bot.get("owner_id", "")) == owner_id
            ):
                raise ValueError(f"Bot '{name}' already exists for this owner")

        bot_id = "BOT_" + uuid4().hex[:12]
        now = _now()
        record = {
            "id": bot_id,
            "name": name,
            "bot_key": str(bot_key).strip() if bot_key else bot_id,
            "template": template,
            "owner_id": owner_id,
            "railway_project_id": None,
            "railway_service_id": None,
            "railway_environment_id": None,
            "status": "draft",
            "created_at": now,
            "updated_at": now,
        }
        bots[bot_id] = record
        return dict(record)

    return state_manager.atomic_update(mutate)


def get_bot(identifier):
    identifier = str(identifier).strip()
    db = state_manager.load_db()
    bots = db.get(_BOTS_KEY, {})
    if identifier in bots:
        return _normalize(bots[identifier])
    lowered = identifier.lower()
    for bot_id, record in bots.items():
        if str(record.get("name", "")).lower() == lowered:
            return _normalize(record)
        if str(record.get("bot_key", "")).lower() == lowered:
            return _normalize(record)
    return None


def list_bots(owner_id=None):
    db = state_manager.load_db()
    bots = db.get(_BOTS_KEY, {})
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
        "template",
        "railway_project_id",
        "railway_service_id",
        "railway_environment_id",
        "status",
    }
    unknown = set(changes) - allowed
    if unknown:
        raise ValueError("Unsupported bot fields: " + ", ".join(sorted(unknown)))

    def mutate(db):
        bots = db.setdefault(_BOTS_KEY, {})
        record = bots.get(str(identifier))
        if record is None:
            lowered = str(identifier).lower()
            for bot_id, candidate in bots.items():
                if (
                    str(candidate.get("name", "")).lower() == lowered
                    or str(candidate.get("bot_key", "")).lower() == lowered
                ):
                    record = candidate
                    identifier_key = bot_id
                    break
            else:
                raise KeyError(f"Bot '{identifier}' not found")
        else:
            identifier_key = str(identifier)

        record.update({k: v for k, v in changes.items() if v is not None})
        record["updated_at"] = _now()
        return dict(bots[identifier_key])

    return state_manager.atomic_update(mutate)


def delete_bot(identifier):
    def mutate(db):
        bots = db.setdefault(_BOTS_KEY, {})
        record = bots.get(str(identifier))
        identifier_key = str(identifier)
        if record is None:
            lowered = str(identifier).lower()
            for bot_id, candidate in bots.items():
                if (
                    str(candidate.get("name", "")).lower() == lowered
                    or str(candidate.get("bot_key", "")).lower() == lowered
                ):
                    identifier_key = bot_id
                    record = candidate
                    break
        if record is None:
            raise KeyError(f"Bot '{identifier}' not found")
        del bots[identifier_key]
        return identifier_key

    return state_manager.atomic_update(mutate)
