"""SLH OS — interactive System Admin Control Plane.

Read-only dashboard surface for the OWNER/ADMIN/DEVELOPER roles.  Mutating
operations remain behind their existing command-specific authorization gates.
"""

import os
import subprocess
from core.authority import get_role, has_permission, normalize_uid


def _is_admin(message):
    uid = normalize_uid(message)
    role = get_role(uid)
    return role in ("OWNER", "ADMIN", "DEVELOPER")


def _status_text():
    checks = []

    checks.append(("Gateway", os.path.exists("bot_gateway.py")))
    checks.append(("Handler loader", os.path.exists("handlers/loader.py")))
    checks.append(("Authority", os.path.exists("core/authority.py")))
    checks.append(("WebApp", os.path.exists("webapp.py")))
    checks.append(("Unified map", os.path.exists("handlers/unified_system_handler.py")))

    try:
        head = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
        ).strip()
    except Exception:
        head = "unavailable"

    try:
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=3,
        ).strip() or "unknown"
    except Exception:
        branch = "unknown"

    lines = [
        "🛡 SLH SYSTEM ADMIN",
        "",
        "Control Plane: central_gateway",
        f"Git: {branch} @ {head}",
        "",
    ]
    for name, ok in checks:
        lines.append(f'{"🟢" if ok else "🔴"} {name}')

    lines += [
        "",
        "Use the menu below for operational shortcuts.",
        "Mutating commands keep their own authorization gates.",
    ]
    return "\n".join(lines)


def _menu_markup():
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🩺 Health", callback_data="admin:health"),
        InlineKeyboardButton("🚂 Railway", callback_data="admin:railway"),
    )
    kb.add(
        InlineKeyboardButton("🐙 GitHub", callback_data="admin:github"),
        InlineKeyboardButton("🤖 Bots", callback_data="admin:bots"),
    )
    kb.add(
        InlineKeyboardButton("🔐 Security", callback_data="admin:security"),
        InlineKeyboardButton("🐛 Bugs / Tasks", callback_data="admin:work"),
    )
    kb.add(
        InlineKeyboardButton("🗺 System Map", callback_data="admin:map"),
        InlineKeyboardButton("📊 Status", callback_data="admin:status"),
    )
    kb.add(
        InlineKeyboardButton("⚙️ Dev", callback_data="admin:dev"),
        InlineKeyboardButton("❓ Help", callback_data="admin:help"),
    )
    return kb


def _page(name):
    pages = {
        "health": (
            "🩺 HEALTH SHORTCUTS\n\n"
            "/health — basic health\n"
            "/doctor — full diagnostic\n"
            "/diagnose — diagnostic\n"
            "/health_monitor — health monitor"
        ),
        "railway": (
            "🚂 RAILWAY SHORTCUTS\n\n"
            "/status — system status\n"
            "/services — service registry\n"
            "/deploy — deployment control\n"
            "/logs — recent logs"
        ),
        "github": (
            "🐙 GITHUB SHORTCUTS\n\n"
            "/git commit <message> — guarded repository sync\n"
            "/project — project information\n"
            "/viewfile <path> — inspect a file"
        ),
        "bots": (
            "🤖 BOT CONTROL\n\n"
            "/status — gateway status\n"
            "/unified_map — federation map\n"
            "/help — command catalog\n"
            "/admin — this Control Plane"
        ),
        "security": (
            "🔐 SECURITY\n\n"
            "OWNER / ADMIN / DEVELOPER are resolved through core.authority.\n"
            "Sensitive execution remains behind its command-specific gates.\n\n"
            "/dev_list — developer access\n"
            "/dev_role <uid> <role> — OWNER only\n"
            "/dev_perm <uid> <permission> — OWNER only"
        ),
        "work": (
            "🐛 WORK QUEUE\n\n"
            "/task — task management\n"
            "/mission — mission control\n"
            "/progress — progress\n"
            "/worklog — work log\n"
            "/report — reports\n"
            "/roadmap — roadmap"
        ),
        "map": (
            "🗺 UNIFIED SYSTEM\n\n"
            "/unified_map — canonical architecture\n"
            "/map — system map\n"
            "/services — registered services"
        ),
        "dev": (
            "⚙️ DEVELOPMENT\n\n"
            "/exec — gated execution\n"
            "/execr — approval request\n"
            "/autoexec — gated batch execution\n"
            "/git commit <message> — guarded Git sync\n"
            "/deploy — deployment control"
        ),
        "help": (
            "❓ ADMIN HELP\n\n"
            "/admin — interactive Control Plane\n"
            "/status — operational status\n"
            "/unified_map — system federation\n"
            "/doctor — diagnostics\n"
            "/task — tasks\n"
            "/roadmap — roadmap"
        ),
    }
    return pages.get(name, "בחר רכיב ניהול.")


def init(bot):
    @bot.message_handler(commands=["admin"])
    def admin_panel(message):
        if not _is_admin(message):
            bot.reply_to(message, "⛔️ Admin access required")
            return
        bot.reply_to(message, _status_text(), reply_markup=_menu_markup())

    @bot.message_handler(commands=["admin_status"])
    def admin_status(message):
        if not _is_admin(message):
            bot.reply_to(message, "⛔️ Admin access required")
            return
        bot.reply_to(message, _status_text(), reply_markup=_menu_markup())

    @bot.callback_query_handler(func=lambda call: str(call.data or "").startswith("admin:"))
    def admin_callback(call):
        if not _is_admin(call.message):
            bot.answer_callback_query(call.id, "⛔️ Access denied", show_alert=True)
            return

        action = str(call.data).split(":", 1)[1]
        if action == "status":
            bot.edit_message_text(
                _status_text(),
                call.message.chat.id,
                call.message.message_id,
                reply_markup=_menu_markup(),
            )
        elif action in {"health", "railway", "github", "bots", "security", "work", "map", "dev", "help"}:
            from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("⬅️ Control Plane", callback_data="admin:status"))
            bot.edit_message_text(
                _page(action),
                call.message.chat.id,
                call.message.message_id,
                reply_markup=kb,
            )
        bot.answer_callback_query(call.id)


print("✅ interactive admin Control Plane loaded")
