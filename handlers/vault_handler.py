"""Owner-only Bot Vault Telegram commands (private chat only)."""
from __future__ import annotations

from core import bot_vault
from core.authority import get_role, normalize_uid


def _is_owner(uid) -> bool:
    return get_role(normalize_uid(uid)) == "OWNER"


def _bot(name: str) -> str:
    return str(name or "").strip().lstrip("@")


def _install_owner_commands(bot, context=None):
    """Expose Vault commands in the Telegram menu only for the canonical owner chat."""
    try:
        if (context or {}).get("bot_name") not in (None, "Me_ad_main"):
            return
        from core.identity import OWNER_TELEGRAM_ID
        from telebot import types
        existing = bot.get_my_commands() if hasattr(bot, "get_my_commands") else []
        names = {getattr(c, "command", "") for c in existing}
        vault = [
            ("vault", "כספת בוטים"),
            ("vault_verify", "אימות הכספת"),
            ("vault_add", "הוספת בוט לכספת"),
            ("vault_rotate", "סיבוב טוקן"),
            ("vault_remove", "הסרת בוט"),
            ("vault_health", "בריאות בוטים"),
            ("vault_exposed", "רישום חשיפה"),
            ("vault_log", "Audit הכספת"),
            ("vault_help", "עזרת הכספת"),
        ]
        merged = list(existing)
        for command, description in vault:
            if command not in names:
                merged.append(types.BotCommand(command, description))
        bot.set_my_commands(merged[:100], scope=types.BotCommandScopeChat(int(OWNER_TELEGRAM_ID)))
    except Exception as exc:
        print("[VAULT] owner command menu skipped:", type(exc).__name__)

def register(bot, context=None):
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

    @bot.message_handler(commands=["vault_verify"])
    def vault_verify(msg):
        if not guard(msg):
            return
        parts = (msg.text or "").split()
        names = [_bot(parts[1])] if len(parts) > 1 else [row["username"] for row in bot_vault.list_bots()]
        out = ["🔎 Bot Vault verification"]
        for name in names:
            try:
                db = __import__("state_manager").load_db()
                entry = (db.get("bot_vault") or {}).get(name)
                if not entry:
                    raise ValueError("BOT_NOT_IN_VAULT")
                token = bot_vault.get_token(name)
                info = bot_vault._verify(token)
                identity_ok = str(entry.get("bot_id")) == str(info.get("bot_id")) and name == info.get("username")
                encrypted_ok = bool(entry.get("token_enc"))
                exposures = len([x for x in entry.get("exposures", []) if not x.get("resolved_at")])
                state = "✅" if identity_ok and encrypted_ok else "❌"
                out.append(f"{state} @{name} · encrypted={'yes' if encrypted_ok else 'no'} · identity={'match' if identity_ok else 'MISMATCH'} · module={entry.get('module','home')} · {entry.get('token_tail','')} · exposures={exposures}")
            except ValueError as exc:
                out.append(f"❌ @{name}: {exc}")
            except Exception:
                out.append(f"❌ @{name}: VAULT_VERIFY_FAILED")
        bot.reply_to(msg, "\n".join(out))

    @bot.message_handler(commands=["vault_help"])
    def vault_help(msg):
        if not guard(msg):
            return
        bot.reply_to(msg, """🔐 Bot Vault — Owner

/vault — רשימת בוטים ומטא־דאטה
/vault_verify [@bot] — אימות הצפנה + זהות Telegram לכל הרשומות
/vault_add <token> [module] — הוספה מוצפנת; ההודעה נמחקת
/vault_rotate <@bot> <new_token> — סיבוב טוקן
/vault_remove <@bot> — הסרה ושמירת audit
/vault_health [@bot] — getMe + webhook + pending
/vault_exposed <@bot> <source> [note] — רישום חשיפה כהמלצה
/vault_log — 20 פעולות אחרונות ללא טוקנים

⚠️ טוקנים לעולם לא מוחזרים בתשובה.""")
 
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

    _install_owner_commands(bot, context)
