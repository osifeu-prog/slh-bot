import json
from pathlib import Path

from core.control_center import get_system_snapshot


def _check(name, ok):
    return (name, "OK" if ok else "FAIL")


def _local_checks():
    db_path = Path("state/db.json")
    agents_path = Path("state/agents.json")

    if not db_path.exists():
        return [
            _check("Canonical DB", False),
            _check("Runtime", Path("bot_gateway.py").exists()),
        ]

    try:
        db = json.loads(db_path.read_text(encoding="utf-8"))
    except Exception:
        return [
            _check("Canonical DB", False),
            _check("Runtime", Path("bot_gateway.py").exists()),
        ]

    users = db.get("users")
    ledger = db.get("ledger")
    services = db.get("system_services")
    return [
        _check("Canonical DB", isinstance(users, dict)),
        _check("Runtime", Path("bot_gateway.py").exists()),
        _check("Agents cache", agents_path.exists()),
        _check("System services", isinstance(services, dict)),
        _check("Ledger", bool(ledger)),
    ]


def register(bot, context=None):
    @bot.message_handler(commands=["health_monitor"])
    def health_monitor(m):
        from core.authority import has_permission
        uid = str(m.from_user.id)
        if not has_permission(uid, "exec.audit"):
            bot.reply_to(m, "⛔️ הרשאת ניטור מערכת מלאה נדרשת.")
            return
        try:
            snapshot = get_system_snapshot()
            infrastructure = snapshot.get("infrastructure", {})
            non_green = infrastructure.get("non_green", [])
            checks = _local_checks()

            lines = ["🔍 SLH HEALTH MONITOR", ""]
            for name, status in checks:
                lines.append(f'{"🟢" if status == "OK" else "🔴"} {name}')

            lines.extend([
                "",
                f"Users: {snapshot.get('users', {}).get('count', 0)}",
                f"Agents: {snapshot.get('agents', {}).get('count', 0)}",
                f"Railway application services not green: {len(non_green)}",
            ])

            for service in non_green[:8]:
                lines.append(
                    f"• {service.get('project', '?')}/{service.get('service', '?')}"
                    f" [{service.get('status', 'unknown')}]"
                )

            bot.reply_to(m, "\n".join(lines))
        except Exception as exc:
            bot.reply_to(m, f"Health monitor failed: {type(exc).__name__}")
