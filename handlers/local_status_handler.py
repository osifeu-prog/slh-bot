"""Owner-only, read-only local-agent presence status.

This first phase reports authenticated heartbeat freshness only. It deliberately
does not claim Docker/Git health until the local agent publishes a verified,
bounded diagnostics snapshot.
"""
from __future__ import annotations

from core.authority import is_owner
from core.device_read_model import get_device_status

_LOCAL_TARGETS = ("PC_Osif2", "PC_MAIN_001")


def _format_target(target: str) -> str:
    result = get_device_status(target_name=target)
    status = str(result.get("status") or "unknown").lower()
    icon = {
        "online": "🟢",
        "offline": "🔴",
    }.get(status, "⚪️")
    age = result.get("age_seconds")
    records = int(result.get("records") or 0)

    if not records:
        detail = "no heartbeat record"
    elif isinstance(age, (int, float)):
        detail = f"last heartbeat {int(max(0, age))}s ago"
    else:
        detail = "heartbeat time unknown"

    return f"{icon} {target}: {status.upper()} · {detail}"


def register(bot):
    @bot.message_handler(commands=["local_status"])
    def local_status(message):
        if getattr(getattr(message, "chat", None), "type", "private") != "private":
            bot.reply_to(message, "🔒 Use /local_status in a private chat with the owner bot.")
            return
        if not is_owner(message):
            bot.reply_to(message, "⛔️ Owner only.")
            return

        lines = [
            "🖥 SLH LOCAL STATUS — READ ONLY",
            "",
        ]
        for target in _LOCAL_TARGETS:
            try:
                lines.append(_format_target(target))
            except Exception:
                # Diagnostics fail closed; never show tracebacks or secrets.
                lines.append(f"⚪️ {target}: UNKNOWN · status read failed")

        lines += [
            "",
            "Docker / Git / container logs: NOT REPORTED",
            "Reason: the current local-agent channel reports presence only; "
            "an authenticated diagnostics payload is not yet connected.",
            "",
            "No commands were executed and no files, containers, balances, or gates were changed.",
        ]
        bot.reply_to(message, "\n".join(lines))
