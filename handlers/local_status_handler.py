"""Owner-only, read-only local status via fresh authenticated device telemetry."""
from __future__ import annotations

import re

from core.authority import is_owner
from core.device_read_model import get_device_status

_LOCAL_TARGETS = ("PC_Osif2", "PC_MAIN_001")
_FRESHNESS_SECONDS = 120
_STATUS = {"UP", "DOWN", "UNKNOWN"}
_BOT_STATUS = {"UP", "RESTARTING", "EXITED", "UNKNOWN"}


def _format_target(target: str, result: dict | None = None) -> str:
    result = result if isinstance(result, dict) else get_device_status(target_name=target)
    status = str(result.get("status") or "unknown").lower()
    icon = {"online": "🟢", "offline": "🔴"}.get(status, "⚪️")
    age = result.get("age_seconds")
    records = int(result.get("records") or 0)

    if not records:
        detail = "no heartbeat record"
    elif isinstance(age, (int, float)):
        detail = f"last heartbeat {int(max(0, age))}s ago"
    else:
        detail = "heartbeat time unknown"

    return f"{icon} {target}: {status.upper()} · {detail}"


def _format_snapshot(snapshot: dict) -> list[str]:
    """Render only explicitly allow-listed diagnostic fields; never logs/env values."""
    lines: list[str] = []
    docker = snapshot.get("docker") if isinstance(snapshot.get("docker"), dict) else {}
    daemon = docker.get("daemon") if docker.get("daemon") in _STATUS else "UNKNOWN"
    total = docker.get("container_count")
    running = docker.get("running_count")
    if type(total) is int and type(running) is int:
        lines.append(f"  Docker: {daemon} · {total} containers · {running} running")
    else:
        lines.append(f"  Docker: {daemon}")

    postgres = snapshot.get("postgres") if snapshot.get("postgres") in _STATUS else "UNKNOWN"
    redis = snapshot.get("redis") if snapshot.get("redis") in _STATUS else "UNKNOWN"
    lines.append(f"  PostgreSQL: {postgres} · Redis: {redis}")

    git = snapshot.get("git") if isinstance(snapshot.get("git"), dict) else {}
    branch = str(git.get("branch") or "UNKNOWN")
    commit = str(git.get("commit") or "UNKNOWN")
    if not re.fullmatch(r"[A-Za-z0-9._/-]{1,80}", branch):
        branch = "UNKNOWN"
    if commit != "UNKNOWN" and not re.fullmatch(r"[0-9a-f]{7,40}", commit):
        commit = "UNKNOWN"
    dirty = git.get("dirty") if isinstance(git.get("dirty"), bool) else False
    dirty_files = git.get("dirty_files")
    if type(dirty_files) is not int or dirty_files < 0 or dirty_files > 100000:
        dirty_files = 0
    tree = f"dirty ({dirty_files} paths)" if dirty else "clean"
    lines.append(f"  Git: {branch} @ {commit} · {tree}")

    compose = snapshot.get("compose") if isinstance(snapshot.get("compose"), dict) else {}
    utf8 = compose.get("utf8") if compose.get("utf8") in {"PASS", "FAIL", "UNKNOWN"} else "UNKNOWN"
    bad = compose.get("bad_byte_97_count")
    if type(bad) is not int or bad < 0 or bad > 1000000:
        bad = 0
    root_env = "present" if compose.get("root_env_present") is True else "missing"
    claude_env = "present" if compose.get("claude_env_present") is True else "missing"
    lines.append(
        f"  Compose UTF-8: {utf8} · 0x97={bad} · root .env {root_env} · Claude .env {claude_env}"
    )

    bots = snapshot.get("bots") if isinstance(snapshot.get("bots"), dict) else {}
    bot_statuses = []
    for key, label in (
        ("slh-ton-mnh", "ton-mnh"),
        ("slh-nifti", "nifti"),
        ("slh-crazy-panel", "crazy-panel"),
    ):
        value = bots.get(key)
        if not isinstance(value, str) or value not in _BOT_STATUS:
            value = "UNKNOWN"
        bot_statuses.append(f"{label} {value}")
    lines.append("  Bots: " + " · ".join(bot_statuses))

    restarting = docker.get("restarting_names")
    if isinstance(restarting, list):
        safe_names = [
            name for name in restarting[:20]
            if isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", name)
        ]
        if safe_names:
            lines.append("  Restarting containers: " + ", ".join(safe_names))
    return lines


def register(bot):
    @bot.message_handler(commands=["local_status"])
    def local_status(message):
        if getattr(getattr(message, "chat", None), "type", "private") != "private":
            bot.reply_to(message, "🔒 Use /local_status in a private chat with the owner bot.")
            return
        if not is_owner(message):
            bot.reply_to(message, "⛔️ Owner only.")
            return

        lines = ["🖥 SLH LOCAL STATUS — READ ONLY", ""]
        fresh_snapshots = 0
        for target in _LOCAL_TARGETS:
            try:
                result = get_device_status(target_name=target)
                lines.append(_format_target(target, result))
                snapshot = result.get("diagnostics") if isinstance(result, dict) else None
                snapshot_age = result.get("diagnostics_age_seconds") if isinstance(result, dict) else None
                if (
                    isinstance(snapshot, dict)
                    and isinstance(snapshot_age, (int, float))
                    and snapshot_age <= _FRESHNESS_SECONDS
                    and snapshot.get("version") == 1
                ):
                    lines.extend(_format_snapshot(snapshot))
                    fresh_snapshots += 1
                else:
                    lines.append("  Local diagnostics: NOT REPORTED · no fresh signed snapshot")
            except Exception:
                lines.append(f"⚪️ {target}: UNKNOWN · status read failed")
                lines.append("  Local diagnostics: NOT REPORTED")

        lines.append("")
        if fresh_snapshots:
            lines.append("✅ Diagnostics: fresh signed snapshots received.")
        else:
            lines.append("⚪️ Docker / Git diagnostics: NOT REPORTED")
            lines.append("Next step: the supervised PC agent must publish the signed diagnostics heartbeat.")
        lines.append("Logs and secret values are never returned.")
        lines.append("Read-only: no commands, files, containers, balances, or gates were changed.")
        bot.reply_to(message, "\n".join(lines))
