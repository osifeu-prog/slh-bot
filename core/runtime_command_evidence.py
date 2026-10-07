"""Read-only evidence adapter for live Telegram command registration.

The source of truth here is the TeleBot instance's in-memory
message_handlers list. This module never dispatches, mutates handlers,
or persists a snapshot.
"""

from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Any


_RUNTIME_BOTS: dict[str, object] = {}
_LOCK = RLock()


def register_runtime_bot(name: str, bot: object) -> None:
    """Register the already-running TeleBot object for read-only inspection."""
    key = str(name or "").strip()
    if not key:
        raise ValueError("BOT_NAME_REQUIRED")
    with _LOCK:
        _RUNTIME_BOTS[key] = bot


def _normalize_command(value: Any) -> str | None:
    command = str(value or "").strip().lstrip("/").lower()
    return command or None


def _callback_identity(callback: object) -> dict[str, str | None]:
    return {
        "module": getattr(callback, "__module__", None),
        "function": getattr(callback, "__name__", None),
        "qualname": getattr(callback, "__qualname__", None),
    }


def snapshot_bot(bot_name: str, bot: object) -> dict[str, Any]:
    """Return JSON-safe evidence from one live TeleBot instance."""
    raw_handlers = getattr(bot, "message_handlers", [])
    handlers = raw_handlers if isinstance(raw_handlers, list) else list(raw_handlers or [])

    commands: dict[str, list[dict[str, Any]]] = {}
    command_handler_count = 0

    for registration_index, handler in enumerate(handlers):
        if not isinstance(handler, dict):
            continue

        filters = handler.get("filters") or {}
        raw_commands = filters.get("commands")
        if isinstance(raw_commands, str):
            raw_commands = [raw_commands]
        if not isinstance(raw_commands, (list, tuple, set)):
            continue

        callback = handler.get("function")
        if callback is None:
            continue

        identity = _callback_identity(callback)
        normalized = []
        for raw_command in raw_commands:
            command = _normalize_command(raw_command)
            if command:
                normalized.append(command)

        for command in normalized:
            command_handler_count += 1
            commands.setdefault(command, []).append(
                {
                    "registration_index": registration_index,
                    **identity,
                }
            )

    collisions = {
        f"/{command}": registrations
        for command, registrations in commands.items()
        if len(registrations) > 1
    }

    return {
        "bot": bot_name,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source": "TeleBot.message_handlers",
        "total_message_handlers": len(handlers),
        "command_registrations": command_handler_count,
        "unique_commands": len(commands),
        "collision_count": len(collisions),
        "commands": {f"/{command}": registrations for command, registrations in sorted(commands.items())},
        "collisions": dict(sorted(collisions.items())),
    }


def snapshot_runtime(bot_name: str | None = None) -> dict[str, Any]:
    """Return evidence for one registered bot or all registered bots."""
    with _LOCK:
        items = dict(_RUNTIME_BOTS)

    if bot_name:
        bot = items.get(str(bot_name))
        if bot is None:
            raise KeyError("BOT_NOT_REGISTERED")
        return snapshot_bot(str(bot_name), bot)

    return {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source": "TeleBot.message_handlers",
        "bots": {
            name: snapshot_bot(name, bot)
            for name, bot in sorted(items.items())
        },
    }
