"""Runtime command catalog for the main SLH Telegram bot."""

from __future__ import annotations

import io
import os
from collections import defaultdict
from datetime import datetime


def is_owner(uid) -> bool:
    try:
        from core.authority import is_owner as authority_is_owner
        return bool(authority_is_owner(uid))
    except Exception:
        allowed = {x.strip() for x in (os.getenv("OWNER_ID", ""), os.getenv("ADMIN_ID", "")) if x.strip()}
        return str(uid) in allowed


def collect(bot) -> dict[str, list[str]]:
    table = defaultdict(list)
    for handler in getattr(bot, "message_handlers", []) or []:
        filters = handler.get("filters", {}) if isinstance(handler, dict) else {}
        fn = handler.get("function") if isinstance(handler, dict) else None
        module = getattr(fn, "__module__", "?")
        name = getattr(fn, "__name__", "?")
        for command in filters.get("commands") or []:
            table[str(command).lower()].append(f"{module}.{name}")
    return dict(table)


def render(bot) -> tuple[str, int, int, int]:
    table = collect(bot)
    duplicates = {cmd: owners for cmd, owners in table.items() if len(owners) > 1}
    by_module = defaultdict(list)
    for command, owners in table.items():
        by_module[owners[0].rsplit(".", 1)[0]].append(command)

    lines = [
        "# SLH OS — live Telegram commands",
        f"Generated: {datetime.now():%Y-%m-%d %H:%M}",
        f"Total unique commands: {len(table)}",
        f"Duplicate command names: {len(duplicates)}",
        f"Handler modules: {len(by_module)}",
        "",
        "## Duplicates",
    ]
    if duplicates:
        lines.extend(
            f"/{command} -> " + " | ".join(owners)
            for command, owners in sorted(duplicates.items())
        )
    else:
        lines.append("None")

    lines += ["", "## By module"]
    for module in sorted(by_module):
        commands = sorted(by_module[module])
        lines.append(f"### {module} ({len(commands)})")
        lines.append(" ".join("/" + command for command in commands))

    lines += ["", "## A-Z"]
    lines.extend("/" + command for command in sorted(table))
    return "
".join(lines), len(table), len(duplicates), len(by_module)


def reply_with_catalog(bot, msg) -> None:
    if getattr(getattr(msg, "chat", None), "type", "private") != "private" or not is_owner(msg.from_user.id):
        bot.reply_to(msg, "⛔️ פקודה לבעלים בלבד.")
        return
    text, total, duplicates, modules = render(bot)
    bot.reply_to(
        msg,
        f"📋 פקודות Telegram פעילות: {total}\n"
        f"📦 מודולים: {modules}\n"
        f"⚠️ כפולות: {duplicates}\n"
        f"🕒 נבנה בזמן אמת מה־runtime של הבוט."
    )
    document = io.BytesIO(text.encode("utf-8"))
    document.name = f"SLH_COMMANDS_{datetime.now():%Y%m%d_%H%M}.md"
    bot.send_document(msg.chat.id, document)


def register(bot):
    @bot.message_handler(commands=["commands_all", "cmds"])
    def commands_all(msg):
        reply_with_catalog(bot, msg)

    print("✅ Runtime command catalog loaded")
