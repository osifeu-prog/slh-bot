"""SLH OS — interactive System Admin Control Plane.

Read-only dashboard surface for the OWNER/ADMIN/DEVELOPER roles.  Mutating
operations remain behind their existing command-specific authorization gates.
"""

import os
from telebot.apihelper import ApiTelegramException
from core.authority import get_role, has_permission, normalize_uid
from core.control_center import get_deployment_state


def _is_admin(message):
    uid = normalize_uid(message)
    role = get_role(uid)
    return role in ("OWNER", "ADMIN", "DEVELOPER")


def _status_text(message):
    checks = []

    checks.append(("Gateway", os.path.exists("bot_gateway.py")))
    checks.append(("Handler loader", os.path.exists("handlers/loader.py")))
    checks.append(("Authority", os.path.exists("core/authority.py")))
    checks.append(("WebApp", os.path.exists("webapp.py")))
    checks.append(("Unified map", os.path.exists("handlers/unified_system_handler.py")))

    deployment = get_deployment_state()
    head = str(deployment.get("commit") or "unknown")
    branch = str(deployment.get("branch") or "unknown")
    deployment_id = str(deployment.get("deployment_id") or "unknown")

    if len(head) > 8:
        head = head[:8]
    if len(deployment_id) > 8:
        deployment_id = deployment_id[:8]

    role = get_role(normalize_uid(message))

    lines = [
        "🛡 SLH SUPER ADMIN CONTROL PLANE",
        f"Role: {role}",
        "",
        "Control Plane: central_gateway",
        f"Git: {branch} @ {head}",
        f"Deploy: {deployment_id}",
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
        InlineKeyboardButton("📊 Status", callback_data="admin:status"),
        InlineKeyboardButton("🩺 Health", callback_data="admin:health"),
    )
    kb.add(
        InlineKeyboardButton("🗺 System Map", callback_data="admin:map"),
        InlineKeyboardButton("🚂 Railway", callback_data="admin:railway"),
    )
    kb.add(
        InlineKeyboardButton("🐙 GitHub", callback_data="admin:github"),
        InlineKeyboardButton("🤖 Bots", callback_data="admin:bots"),
    )
    kb.add(
        InlineKeyboardButton("👥 Agents", callback_data="admin:agents"),
        InlineKeyboardButton("🎯 Alpha", callback_data="admin:alpha"),
    )
    kb.add(
        InlineKeyboardButton("💰 Economy", callback_data="admin:economy"),
        InlineKeyboardButton("💎 Staking / Revenue", callback_data="admin:staking"),
    )
    kb.add(
        InlineKeyboardButton("📱 Devices / ESP", callback_data="admin:devices"),
        InlineKeyboardButton("🌐 WebApp", callback_data="admin:web"),
    )
    kb.add(
        InlineKeyboardButton("🔐 Security", callback_data="admin:security"),
        InlineKeyboardButton("📋 Audit / Logs", callback_data="admin:audit"),
    )
    kb.add(
        InlineKeyboardButton("🐛 Bugs / Tasks", callback_data="admin:work"),
        InlineKeyboardButton("⚙️ Dev / Exec", callback_data="admin:dev"),
    )
    kb.add(
        InlineKeyboardButton("♻️ Recovery", callback_data="admin:recovery"),
        InlineKeyboardButton("❓ Help / Commands", callback_data="admin:help"),
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
            "/services — service registry\n"
            "/unified_map — federation map\n"
            "/project — project information\n"
            "/help — command catalog\n"
            "/admin — this Super Admin Control Plane"
        ),
        "agents": (
            "👥 AGENTS\n\n"
            "/agents — agent registry\n"
            "/agent — agent control\n"
            "/task — task management\n"
            "/mission — mission control\n"
            "/progress — progress\n"
            "/monitor_list — monitoring registry\n            /monitor_status — monitoring status\n            /monitor_logs — monitoring logs"
        ),
        "alpha": (
            "🎯 ALPHA CONTROL\n\n"
            "/alpha_status — canonical Alpha evaluation\n"
            "/alpha_state — current Alpha state\n"
            "/alpha_open — OWNER-only open transition\n"
            ""
        ),
        "economy": (
            "💰 ECONOMY / WALLET\n\n"
            "/me — account read model\n"
            "/wallet — wallet surface\n"
            "/transfer <uid> <amount> — Credits transfer\n"
            "/exchange — exchange surface\n"
            "/claim — claim/deposit path\n"
            "/withdraw — withdrawal requests\n"
            "Sensitive mutations remain behind their canonical gates."
        ),
        "staking": (
            "💎 STAKING / REVENUE\n\n"
            "/stake — staking\n"
            "/stake_lock — locked staking\n"
            "/revenue — revenue-share surface\n"
            "/ton_balance — TON balance\n"
            "/revenue_reconcile — revenue reconciliation\n            /revenue_audit — revenue audit\n            /ton_address — TON deposit address + memo\n            /ton_deposit — TON deposit address alias\n            /ton_check <TX hash> — verify one TON transaction\n            /ton_paid — scan recent qualifying TON deposits\n"
            "Read/modify actions remain permission-gated."
        ),
        "devices": (
            "📱 DEVICES / ESP\n\n"
            "/device — device control\n"
            "/esp_start — ESP start\n"
            "/esp_stop — ESP stop\n"
            "/map — system/device map\n"
            "PC_Osif2 live status is derived from the read-only heartbeat model."
        ),
        "web": (
            "🌐 WEB / MINI APP\n\n"
            "/project — project surface\n"
            "/wallet — wallet UI\n"
            "/join — onboarding\n"
            "/me — account read model\n"
            "/gateway — gateway/control-plane surface"
        ),
        "audit": (
            "📋 AUDIT / LOGS\n\n"
            "/logs — recent logs\n"
            "/audit — audit surface\n"
            "/exec_log — execution audit\n"
            "/report — reports\n"
            "/doctor — diagnostics\n"
            "/diagnose — diagnostic"
        ),
        "recovery": (
            "♻️ RECOVERY / MAINTENANCE\n\n"
            "/recovery — recovery flow\n"
            "/backup — database backup\n"
            "/clean — cleanup\n"
            "/refresh — refresh surface\n"
            "/complete — completion checks"
        ),
        "security": (
            "🔐 SECURITY\n\n"
            "OWNER / ADMIN / DEVELOPER are resolved through core.authority.\n"
            "Sensitive execution remains behind its command-specific gates.\n"
            "No token/economy mutation is exposed by this menu itself.\n\n"
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
            "/services — registered services\n"
            "/project — project information\n"
            "/monitor — monitoring\n"
            "/health_monitor — health monitor"
        ),
        "dev": (
            "⚙️ DEVELOPMENT / EXECUTION\n\n"
            "/e <command> — OWNER control-plane execution\n"
            "/e railway — Railway projects\n"
            "/e railway inspect <project_id> — inspect project\n"
            "/e railway up [full_sha] — guarded deploy\n"
            "/exec — gated execution\n"
            "/execr — approval request\n"
            "/autoexec — gated batch execution\n"
            "/git commit <message> — guarded Git sync\n"
            "/deploy — deployment control\n"
            "/dev_list — developer access"
        ),
        "help": (
            "❓ SUPER ADMIN COMMAND INDEX\n\n"
            "/admin — full Control Plane\n"
            "/admin_status — refresh Control Plane\n"
            "/e <command> — OWNER execution/audit gateway\n"
            "/exec <command> — gated execution\n"
            "/execr — approval request\n"
            "/autoexec — gated batch execution\n"
            "/status — operational status\n"
            "/health — health\n"
            "/doctor — diagnostics\n"
            "/unified_map — system federation\n"
            "/services — services\n"
            "/task /mission /progress — work control\n"
            "/dev_list /dev_role /dev_perm — developer authority\n"
            "/backup /clean /recovery — maintenance"
        ),
    }
    return pages.get(name, "בחר רכיב ניהול.")


def init(bot):
    @bot.message_handler(commands=["admin"])
    def admin_panel(message):
        if not _is_admin(message):
            bot.reply_to(message, "⛔️ Admin access required")
            return
        bot.reply_to(message, _status_text(message), reply_markup=_menu_markup())

    @bot.message_handler(commands=["admin_status"])
    def admin_status(message):
        if not _is_admin(message):
            bot.reply_to(message, "⛔️ Admin access required")
            return
        bot.reply_to(message, _status_text(message), reply_markup=_menu_markup())

    @bot.callback_query_handler(func=lambda call: str(call.data or "").startswith("admin:"))
    def admin_callback(call):
        if not _is_admin(call.from_user):
            bot.answer_callback_query(call.id, "⛔️ Access denied", show_alert=True)
            return

        action = str(call.data).split(":", 1)[1]
        if action == "status":
            # Acknowledge immediately so Telegram never leaves the callback
            # spinner running while the status edit is being processed.
            bot.answer_callback_query(call.id, "✅ Status refreshed")
            try:
                bot.edit_message_text(
                    _status_text(call.from_user),
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=_menu_markup(),
                )
            except ApiTelegramException as exc:
                # Telegram returns 400 when the user presses Status while the
                # message already contains the exact same text and markup.
                if "message is not modified" not in str(exc):
                    raise
        elif action in {"health", "railway", "github", "bots", "agents", "alpha", "economy", "staking", "devices", "web", "security", "audit", "work", "map", "dev", "recovery", "help"}:
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
