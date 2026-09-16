from core import profile_manager
from security.permissions import get_role, get_permissions
import state_manager
from core.authority import is_owner, ROLES


def _display_name(uid, data):
    profile = data.get("profile", {}) or {}
    for candidate in (
        profile.get("name"),
        data.get("name"),
        data.get("display_name"),
        data.get("telegram_name"),
    ):
        value = str(candidate or "").strip()
        if value and value != f"User{uid}":
            return value
    return f"User{uid}"


def _role_permissions(role):
    return sorted(ROLES.get(str(role or "").upper(), []))


def register(bot):
    @bot.message_handler(commands=['dev_add'])
    def dev_add(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔ OWNER only")
            return
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /dev_add <user_id>")
            return

        uid = parts[1].strip()
        user = profile_manager.get_user(uid)
        profile_manager.update_user(uid, {
            "role": "developer",
            "permissions": _role_permissions("DEVELOPER"),
        })
        name = _display_name(uid, user)
        bot.reply_to(m, f"✅ {name} ({uid}) promoted to DEVELOPER")

    @bot.message_handler(commands=['dev_remove'])
    def dev_remove(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔ OWNER only")
            return
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /dev_remove <user_id>")
            return
        uid = parts[1].strip()
        profile_manager.update_user(uid, {
            "role": "student",
            "permissions": _role_permissions("USER"),
        })
        bot.reply_to(m, f"✅ User {uid} removed from developer role")

    @bot.message_handler(commands=['dev_list'])
    def dev_list(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔ OWNER only")
            return
        db = state_manager.load_db()
        users = db.get('users', {})
        lines = ["👥 Developer Access:"]
        for uid, data in users.items():
            role = str(data.get('role', '')).lower()
            if role in ['developer', 'admin', 'teacher']:
                name = _display_name(uid, data)
                perms = data.get('permissions', [])
                lines.append(
                    f"• {name} | {uid} | role={role} | "
                    f"perms={', '.join(perms) if perms else 'none'}"
                )
        if len(lines) == 1:
            lines.append("No developers found.")
        bot.reply_to(m, "\n".join(lines))

    @bot.message_handler(commands=['dev_perm'])
    def dev_perm(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔ OWNER only")
            return
        parts = m.text.split()
        if len(parts) < 3:
            bot.reply_to(m, "Usage: /dev_perm <user_id> <permission>")
            return
        uid = parts[1].strip()
        perm = parts[2].lower()
        perms = set(get_permissions(uid))
        if perm in perms:
            perms.remove(perm)
            action = "removed"
        else:
            perms.add(perm)
            action = "added"
        profile_manager.update_user(uid, {"permissions": sorted(perms)})
        bot.reply_to(m, f"✅ Permission '{perm}' {action} for user {uid}")

    @bot.message_handler(commands=['dev_role'])
    def dev_role(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔ OWNER only")
            return
        parts = m.text.split()
        if len(parts) < 3:
            bot.reply_to(m, "Usage: /dev_role <user_id> <role>")
            return
        uid = parts[1].strip()
        role = parts[2].lower()
        profile_manager.update_user(uid, {
            "role": role,
            "permissions": _role_permissions(role),
        })
        bot.reply_to(m, f"✅ User {uid} role changed to {role.upper()}")

    print("✅ dev_admin loaded")
