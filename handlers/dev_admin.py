from core import profile_manager
from security.permissions import get_role, get_permissions, has_permission\nfrom core.authority import is_owner\nfrom core.authority import is_owner\nfrom core.authority import is_owner
import state_manager

OWNER_TELEGRAM_ID = 8789977826

def register(bot):
    @bot.message_handler(commands=['dev_add'])
    def dev_add(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔ OWNER only")
            return
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /dev_add <user_id> [role]")
            return
        uid = parts[1]
        role = parts[2].lower() if len(parts) >= 3 else "developer"
        profile_manager.update_user(uid, {"role": role, "permissions": get_permissions(uid)})
        if role == "developer":
            perms = set(get_permissions(uid))
            perms.add("exec_request")
            perms.add("read_logs")
            perms.add("db_read")
            profile_manager.update_user(uid, {"permissions": sorted(perms)})
        bot.reply_to(m, f"✅ User {uid} promoted to {role.upper()}")

    @bot.message_handler(commands=['dev_remove'])
    def dev_remove(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔ OWNER only")
            return
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /dev_remove <user_id>")
            return
        uid = parts[1]
        profile_manager.update_user(uid, {"role": "student", "permissions": []})
        bot.reply_to(m, f"✅ User {uid} removed from developer role")

    @bot.message_handler(commands=['dev_list'])
    def dev_list(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔ OWNER only")
            return
        db = state_manager.load_db()
        users = db.get('users', {})
        lines = ["👥 Registered Developers:"]
        for uid, data in users.items():
            role = data.get('role')
            if role in ['developer', 'admin', 'teacher']:
                perms = data.get('permissions', [])
                lines.append(f"• {uid} | role={role} | perms={', '.join(perms) if perms else 'none'}")
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
        uid = parts[1]
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
        uid = parts[1]
        role = parts[2].lower()
        profile_manager.update_user(uid, {"role": role})
        bot.reply_to(m, f"✅ User {uid} role changed to {role.upper()}")
