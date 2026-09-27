"""Owner-only Bot Vault Telegram commands (private chat only)."""
from __future__ import annotations

from core import bot_vault
from core.authority import get_role, normalize_uid


def _is_owner(uid) -> bool:
    return get_role(normalize_uid(uid)) == "OWNER"


def _bot(name: str) -> str:
    return str(name or "").strip().lstrip("@")


def register(bot):
    def guard(msg):
        if getattr(msg.chat, "type", "private") != "private":
            return False
        if not _is_owner(msg.from_user.id):
            bot.reply_to(msg, "⛔️ פקודה לבעלים בלבד.")
            return False
        return True

    def wipe(msg):
        try:
            bot.delete_message(msg.chat.id, msg.message_id)
        except Exception:
            pass

    @bot.message_handler(commands=["vault"])
    def vault_list(msg):
        if not guard(msg):
            return
        rows = bot_vault.list_bots()
        if not rows:
            bot.reply_to(msg, "🔐 הכספת ריקה.\nהוסף: /vault_add <token> [module]")
            return
        lines = ["🔐 Bot Vault"]
        for row in rows:
            warn = f" ⚠️{row['open_exposures']}" if row["open_exposures"] else ""
            lines.append(f"• @{row['username']} · {row['module']} · {row['token_tail']}{warn}")
        lines.append("\n⚠️ = נחשף, המלצה לסיבוב; אין חסימה אוטומטית.")
        bot.reply_to(msg, "\n".join(lines))

    @bot.message_handler(commands=["vault_add"])
    def vault_add(msg):
        if not guard(msg):
            return
        parts = (msg.text or "").split()
        wipe(msg)
        if len(parts) < 2:
            bot.send_message(msg.chat.id, "שימוש: /vault_add <token> [module]")
            return
        try:
            info = bot_vault.add_bot(parts[1], actor=msg.from_user.id, module=parts[2] if len(parts) > 2 else "home")
            bot.send_message(msg.chat.id, f"✅ @{info['username']} נשמר מוצפן ({info['token_tail']}).")
        except ValueError as exc:
            bot.send_message(msg.chat.id, f"❌ {exc}")

    @bot.message_handler(commands=["vault_rotate"])
    def vault_rotate(msg):
        if not guard(msg):
            return
        parts = (msg.text or "").split()
        wipe(msg)
        if len(parts) < 3:
            bot.send_message(msg.chat.id, "שימוש: /vault_rotate <@bot> <new_token>")
            return
        try:
            info = bot_vault.rotate_bot(_bot(parts[1]), parts[2], actor=msg.from_user.id)
            bot.send_message(msg.chat.id, f"🔄 @{info['username']} סובב ({info['token_tail']}).")
        except ValueError as exc:
            bot.send_message(msg.chat.id, f"❌ {exc}")

    @bot.message_handler(commands=["vault_remove"])
    def vault_remove(msg):
        if not guard(msg):
            return
        parts = (msg.text or "").split()
        if len(parts) < 2:
            bot.reply_to(msg, "שימוש: /vault_remove <@bot>")
            return
        try:
            bot_vault.remove_bot(_bot(parts[1]), actor=msg.from_user.id)
            bot.reply_to(msg, f"🗑 @{_bot(parts[1])} הוסר מהכספת. היומן נשמר.")
        except ValueError as exc:
            bot.reply_to(msg, f"❌ {exc}")

    @bot.message_handler(commands=["vault_health"])
    def vault_health(msg):
        if not guard(msg):
            return
        parts = (msg.text or "").split()
        names = [_bot(parts[1])] if len(parts) > 1 else [row["username"] for row in bot_vault.list_bots()]
        out = ["🩺 Bot Vault health"]
        for name in names:
            try:
                item = bot_vault.health(name)
                state = "✅" if item["alive"] else "❌"
                extra = " · webhook" if item["webhook"] else ""
                if item["pending"]:
                    extra += f" · pending {item['pending']}"
                if item["last_error"]:
                    extra += f" · ⚠️ {item['last_error'][:60]}"
                out.append(f"{state} @{name}{extra}")
            except ValueError as exc:
                out.append(f"❌ @{name}: {exc}")
        bot.reply_to(msg, "\n".join(out))

    @bot.message_handler(commands=["vault_exposed"])
    def vault_exposed(msg):
        if not guard(msg):
            return
        parts = (msg.text or "").split(maxsplit=3)
        if len(parts) < 3:
            bot.reply_to(msg, "שימוש: /vault_exposed <@bot> <source> [note]")
            return
        try:
            bot_vault.mark_exposed(_bot(parts[1]), parts[2], actor=msg.from_user.id, note=parts[3] if len(parts) > 3 else "")
            bot.reply_to(msg, f"⚠️ נרשם: @{_bot(parts[1])} נחשף ({parts[2]}). המלצה לסיבוב; הבוט ממשיך לעבוד.")
        except ValueError as exc:
            bot.reply_to(msg, f"❌ {exc}")

    @bot.message_handler(commands=["vault_log"])
    def vault_log(msg):
        if not guard(msg):
            return
        import state_manager
        log = (state_manager.load_db().get("bot_vault_audit") or [])[-20:]
        if not log:
            bot.reply_to(msg, "📜 היומן ריק.")
            return
        lines = ["📜 Bot Vault — 20 אחרונים"]
        for entry in log:
            lines.append(
                f"{entry.get('at', '')[:16].replace('T', ' ')} · "
                f"{entry.get('action', '')} · @{entry.get('bot', '')} "
                f"{entry.get('token_tail', '')} {entry.get('note', '')}".strip()
            )
        bot.reply_to(msg, "\n".join(lines))
