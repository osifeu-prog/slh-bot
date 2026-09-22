from core import profile_manager
from security.permissions import get_role, get_permissions
import state_manager
from core.authority import is_owner, ROLES, get_role


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
            "developer_access_status": "active",
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
            "developer_access_status": "revoked",
        })
        bot.reply_to(m, f"✅ Developer access revoked for {uid}")

    @bot.message_handler(commands=['dev_lock'])
    def dev_lock(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔ OWNER only")
            return
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /dev_lock <user_id>")
            return
        uid = parts[1].strip()
        profile_manager.update_user(uid, {
            "role": "student",
            "permissions": _role_permissions("USER"),
            "developer_access_status": "locked",
        })
        bot.reply_to(m, f"🔒 Developer access locked for {uid}")

    @bot.message_handler(commands=['dev_revoke'])
    def dev_revoke(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔ OWNER only")
            return
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /dev_revoke <user_id>")
            return
        uid = parts[1].strip()
        profile_manager.update_user(uid, {
            "role": "student",
            "permissions": _role_permissions("USER"),
            "developer_access_status": "revoked",
        })
        bot.reply_to(m, f"⛔ Developer access permanently revoked for {uid}")

    @bot.message_handler(commands=['dev_add'])
    def dev_activate(m):
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
            "developer_access_status": "active",
        })
        name = _display_name(uid, user)
        bot.reply_to(m, f"✅ {name} ({uid}) developer access activated")

    @bot.message_handler(commands=['dev_reward'])
    def dev_reward(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔ OWNER only")
            return
        parts = m.text.split()
        if len(parts) < 3:
            bot.reply_to(m, "Usage: /dev_reward <user_id> <credits> [reason]")
            return
        uid = parts[1].strip()
        try:
            credits = float(parts[2])
        except (TypeError, ValueError):
            bot.reply_to(m, "❌ Credits must be numeric.")
            return
        if credits <= 0:
            bot.reply_to(m, "❌ Credits must be positive.")
            return
        reason = " ".join(parts[3:]).strip() or "developer contribution"
        from core import economy_service
        try:
            balance = economy_service.record_transaction(
                uid=uid,
                amount=credits,
                reason="developer:reward",
                meta={
                    "source": "owner_developer_reward",
                    "reason": reason,
                    "idempotency_key": f"DEV-REWARD-{uid}-{m.message_id}",
                },
            )
        except Exception as exc:
            bot.reply_to(m, f"❌ Reward failed safely: {type(exc).__name__}")
            return
        bot.reply_to(m, f"💰 {credits:g} Credits rewarded to {uid}. Balance: {balance:g}")

    @bot.message_handler(commands=['dev_list'])
    def dev_list(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔ OWNER only")
            return
        db = state_manager.load_db()
        users = db.get('users', {})
        import os
        env_ids = {
            x.strip() for x in os.getenv("SLH_DEVELOPER_IDS", "").split(",")
            if x.strip().isdigit()
        }
        candidate_ids = set(env_ids)
        for uid, data in users.items():
            role = str(data.get('role', '')).lower()
            status = str(data.get('developer_access_status', '')).lower()
            if role in ['developer', 'admin', 'teacher'] or status in ['active', 'locked', 'revoked']:
                candidate_ids.add(str(uid))

        lines = ["👥 Developer Access:"]
        for uid in sorted(candidate_ids):
            data = users.get(uid, {}) or {}
            name = _display_name(uid, data)
            status = str(data.get('developer_access_status', '') or 'legacy/env').lower()
            effective = get_role(uid)
            perms = data.get('permissions', [])
            lines.append(
                f"• {name} | {uid} | effective={effective} | status={status} | "
                f"perms={', '.join(perms) if perms else 'none'}"
            )
        if len(lines) == 1:
            lines.append("No developer access records found.")
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
