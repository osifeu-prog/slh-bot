from core.firewall import firewall_status, log_deny
from security import permissions


def _can_view_firewall(uid):
    return permissions._is_owner(uid)


def register(bot):
    @bot.message_handler(commands=["firewall"])
    def firewall_cmd(m):
        uid = str(m.from_user.id)
        print(f"[FIREWALL DEBUG] uid={uid} first_name={getattr(m.from_user, 'first_name', '')} username={getattr(m.from_user, 'username', '')}")
        if not _can_view_firewall(uid):
            log_deny(uid, "/firewall", "firewall_visibility_denied")
            bot.reply_to(m, "🛡 SLH FIREWALL\n\n❌ Access denied.\nYou are not authorized to view firewall status.")
            return
        st = firewall_status(uid)
        bot.reply_to(m, "🛡 SLH FIREWALL\n\n" f"👤 Role: {st['role']}\n" f"👑 Owner: {'✅' if st['is_owner'] else '❌'}\n" f"🔐 Permissions: {', '.join(st['permissions']) or 'none'}\n\n" "Protected commands:\n" "exec / deploy / restart / broadcast / db_write / git_push")
