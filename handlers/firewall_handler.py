from core.firewall import firewall_status, log_deny
from security import permissions


def _can_view_firewall(uid):
    """
    Firewall visibility is separate from privileged command execution.

    OWNER:
        always allowed.

    ADMIN:
        allowed to view firewall status.

    Other users:
        denied.

    This does NOT grant exec/deploy/restart/db_write/git_push.
    """
    if permissions._is_owner(uid):
        return True

    role = permissions.get_role(uid)

    if str(role).lower() == "admin":
        return True

    # Optional explicit read permission.
    if permissions.has_permission(uid, "firewall_view"):
        return True

    return False


def register(bot):
    @bot.message_handler(commands=["firewall"])
    def firewall_cmd(m):

        uid = str(m.from_user.id)
        print(f"[FIREWALL DEBUG] uid={uid} first_name={getattr(m.from_user, "first_name", "")} username={getattr(m.from_user, "username", "")}")

        if not _can_view_firewall(uid):
            log_deny(
                uid,
                "/firewall",
                "firewall_visibility_denied"
            )

            bot.reply_to(
                m,
                "🛡 SLH FIREWALL\n\n"
                "❌ Access denied.\n"
                "You are not authorized to view firewall status."
            )
            return

        st = firewall_status(uid)

        bot.reply_to(
            m,
            "🛡 SLH FIREWALL\n\n"
            f"👤 Role: {st['role']}\n"
            f"👑 Owner: {'✅' if st['is_owner'] else '❌'}\n"
            f"🔐 Permissions: "
            f"{', '.join(st['permissions']) or 'none'}\n\n"
            "Protected commands:\n"
            "exec / deploy / restart / broadcast / db_write / git_push"
        )
