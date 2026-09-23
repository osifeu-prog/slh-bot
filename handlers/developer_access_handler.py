from core import developer_access
from core.authority import is_owner


def _reason_message(result):
    reason = result.get("reason")
    if reason == "bitcoin_mastery_incomplete":
        return (
            "🔒 Developer Access עדיין נעול.\n\n"
            f"השלמת Bitcoin Mastery: {result.get('completed', 0)}/{result.get('required', 0)}\n"
            "סיים את כל הקורס ואז שלח שוב /dev_request."
        )
    if reason == "request_not_pending":
        return "ℹ️ אין בקשת Developer ממתינה עבור המשתמש הזה."
    if reason == "owner_only":
        return "⛔ OWNER only"
    if reason == "user_not_found":
        return "❌ משתמש לא נמצא."
    return f"❌ לא ניתן להשלים את הפעולה ({reason or 'unknown'})."


def register(bot):
    @bot.message_handler(commands=["dev_request"])
    def dev_request(m):
        result = developer_access.request_access(str(m.from_user.id))
        if result.get("ok"):
            if result.get("status") == "already_active":
                bot.reply_to(m, "✅ כבר יש לך Developer Access פעיל.")
            else:
                bot.reply_to(
                    m,
                    "📨 בקשת Developer Access נרשמה.\n"
                    "הבקשה ממתינה לאישור Owner.\n"
                    "אין גישה ל-production עד לאישור.",
                )
            return
        bot.reply_to(m, _reason_message(result))

    @bot.message_handler(commands=["dev_requests"])
    def dev_requests(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔ OWNER only")
            return

        pending = developer_access.pending_requests()
        if not pending:
            bot.reply_to(m, "📭 אין בקשות Developer ממתינות.")
            return

        lines = ["📨 Developer Requests:"]
        for uid, req in sorted(pending.items()):
            lines.append(
                f"• {uid} | {req.get('completed', 0)}/{req.get('required', 0)} "
                f"| {req.get('requested_at', '?')}"
            )
        bot.reply_to(m, "\n".join(lines))

    @bot.message_handler(commands=["dev_approve"])
    def dev_approve(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔ OWNER only")
            return

        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /dev_approve <user_id>")
            return

        result = developer_access.approve_access(parts[1].strip(), str(m.from_user.id))
        if not result.get("ok"):
            bot.reply_to(m, _reason_message(result))
            return

        bot.reply_to(
            m,
            f"✅ Developer Access approved for {parts[1].strip()}.\n"
            "RBAC role=DEVELOPER, status=active.",
        )

    @bot.message_handler(commands=["dev_deny"])
    def dev_deny(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔ OWNER only")
            return

        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /dev_deny <user_id>")
            return

        result = developer_access.deny_access(parts[1].strip(), str(m.from_user.id))
        if not result.get("ok"):
            bot.reply_to(m, _reason_message(result))
            return

        bot.reply_to(m, f"⛔ Developer Access denied for {parts[1].strip()}.")

    print("✅ developer_access loaded")
