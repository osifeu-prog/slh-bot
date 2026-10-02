from core import profile_manager
from core import developer_access
from security.permissions import get_permissions
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

def _parse_target_uid(parts):
    """Return a positive numeric Telegram UID or None for invalid input."""
    if len(parts) < 2:
        return None
    raw = str(parts[1] or "").strip()
    if not raw.isdigit() or int(raw) <= 0:
        return None
    return raw


def _target_user_exists(uid):
    db = state_manager.load_db()
    return str(uid) in db.get("users", {})



def _parse_permission_command(parts):
    """Parse explicit permission actions without treating action words as permissions."""
    if len(parts) >= 4 and parts[2].lower() in {"add", "remove", "toggle"}:
        return parts[2].lower(), parts[3].lower()
    raw = parts[2].strip()
    if raw.startswith("+") and len(raw) > 1:
        return "add", raw[1:].lower()
    if raw.startswith("-") and len(raw) > 1:
        return "remove", raw[1:].lower()
    return "toggle", raw.lower()


def _normalize_role_action(raw_role):
    role = str(raw_role or "").strip().lower()
    if role in {"revoke", "remove", "none"}:
        return "revoke"
    if role == "lock":
        return "lock"
    return role


def _approve_requested(bot, m, uid):
    result = developer_access.approve_access(uid, str(m.from_user.id))
    if not result.get("ok"):
        reason = result.get("reason")
        if reason == "request_not_pending":
            bot.reply_to(m, "⛔ אין בקשת Developer ממתינה. המשתמש חייב להשלים Bitcoin Mastery ואז לשלוח /dev_request.")
        elif reason == "bitcoin_mastery_incomplete":
            bot.reply_to(
                m,
                f"🔒 Bitcoin Mastery לא הושלם: {result.get('completed', 0)}/{result.get('required', 0)}."
            )
        elif reason == "user_not_found":
            bot.reply_to(m, "❌ משתמש לא נמצא.")
        else:
            bot.reply_to(m, f"❌ Developer approval failed: {reason or 'unknown'}")
        return False

    bot.reply_to(
        m,
        f"✅ Developer Access approved for {uid}.\n"
        "RBAC role=DEVELOPER, status=active."
    )
    return True


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
        _approve_requested(bot, m, parts[1].strip())

    @bot.message_handler(commands=['dev_remove'])
    def dev_remove(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔ OWNER only")
            return
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /dev_remove <user_id>")
            return
        uid = _parse_target_uid(parts)
        if not uid:
            bot.reply_to(m, "❌ user_id חייב להיות מספר Telegram חיובי.")
            return
        if not _target_user_exists(uid):
            bot.reply_to(m, f"❌ משתמש {uid} לא נמצא.")
            return
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
        uid = _parse_target_uid(parts)
        if not uid:
            bot.reply_to(m, "❌ user_id חייב להיות מספר Telegram חיובי.")
            return
        if not _target_user_exists(uid):
            bot.reply_to(m, f"❌ משתמש {uid} לא נמצא.")
            return
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
        uid = _parse_target_uid(parts)
        if not uid:
            bot.reply_to(m, "❌ user_id חייב להיות מספר Telegram חיובי.")
            return
        if not _target_user_exists(uid):
            bot.reply_to(m, f"❌ משתמש {uid} לא נמצא.")
            return
        profile_manager.update_user(uid, {
            "role": "student",
            "permissions": _role_permissions("USER"),
            "developer_access_status": "revoked",
        })
        bot.reply_to(m, f"⛔ Developer access permanently revoked for {uid}")

    @bot.message_handler(commands=['dev_activate'])
    def dev_activate(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔ OWNER only")
            return
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /dev_activate <user_id>")
            return
        _approve_requested(bot, m, parts[1].strip())

    @bot.message_handler(commands=['dev_reward'])
    def dev_reward(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔ OWNER only")
            return
        parts = m.text.split()
        if len(parts) < 3:
            bot.reply_to(m, "Usage: /dev_reward <user_id> <credits> [reason]")
            return
        uid = _parse_target_uid(parts)
        if not uid:
            bot.reply_to(m, "❌ user_id חייב להיות מספר Telegram חיובי.")
            return
        if not _target_user_exists(uid):
            bot.reply_to(m, f"❌ משתמש {uid} לא נמצא.")
            return
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
            bot.reply_to(
                m,
                "Usage: /dev_perm <user_id> <add|remove|toggle> <permission>\n"
                "Also: /dev_perm <user_id> +<permission> | -<permission>",
            )
            return
        uid = _parse_target_uid(parts)
        if not uid:
            bot.reply_to(m, "❌ user_id חייב להיות מספר Telegram חיובי.")
            return
        if not _target_user_exists(uid):
            bot.reply_to(m, f"❌ משתמש {uid} לא נמצא.")
            return
        action, perm = _parse_permission_command(parts)
        if not perm or perm in {"add", "remove", "toggle"}:
            bot.reply_to(m, "❌ Permission name is required.")
            return

        perms = set(get_permissions(uid))
        if action == "add":
            perms.add(perm)
        elif action == "remove":
            perms.discard(perm)
        else:
            if perm in perms:
                perms.remove(perm)
                action = "remove"
            else:
                perms.add(perm)
                action = "add"

        profile_manager.update_user(uid, {"permissions": sorted(perms)})
        bot.reply_to(m, f"✅ Permission '{perm}' {action}d for user {uid}")

    @bot.message_handler(commands=['dev_role'])
    def dev_role(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔ OWNER only")
            return
        parts = m.text.split()
        if len(parts) < 3:
            bot.reply_to(m, "Usage: /dev_role <user_id> <role>")
            return
        uid = _parse_target_uid(parts)
        if not uid:
            bot.reply_to(m, "❌ user_id חייב להיות מספר Telegram חיובי.")
            return
        if not _target_user_exists(uid):
            bot.reply_to(m, f"❌ משתמש {uid} לא נמצא.")
            return
        role = _normalize_role_action(parts[2])
        if role not in {"revoke", "lock"} and role.upper() not in ROLES:
            bot.reply_to(m, f"❌ תפקיד לא מוכר: {role}.")
            return

        if role == "developer":
            bot.reply_to(
                m,
                "🔒 Direct Developer role assignment is disabled. "
                "User must complete Bitcoin Mastery, send /dev_request, then Owner approves."
            )
            return

        if role == "revoke":
            profile_manager.update_user(uid, {
                "role": "student",
                "permissions": _role_permissions("USER"),
                "developer_access_status": "revoked",
            })
            bot.reply_to(m, f"⛔ Developer access revoked for {uid}")
            return

        if role == "lock":
            profile_manager.update_user(uid, {
                "role": "student",
                "permissions": _role_permissions("USER"),
                "developer_access_status": "locked",
            })
            bot.reply_to(m, f"🔒 Developer access locked for {uid}")
            return

        update = {
            "role": role,
            "permissions": _role_permissions(role),
        }
        profile_manager.update_user(uid, update)
        bot.reply_to(m, f"✅ User {uid} role changed to {role.upper()}")

    @bot.message_handler(commands=['dist_wallet_status'])
    def dist_wallet_status(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔ OWNER only")
            return
        parts = m.text.split()
        if len(parts) != 2 or not parts[1].isdigit() or int(parts[1]) <= 0:
            bot.reply_to(m, "Usage: /dist_wallet_status <user_id>")
            return
        from core.distribution_wallet_registry import get_secondary_distribution_wallet
        record = get_secondary_distribution_wallet(parts[1])
        if not record:
            bot.reply_to(m, "ℹ️ אין ארנק חלוקה משני רשום למשתמש הזה.")
            return
        bot.reply_to(
            m,
            "🔐 Secondary Distribution Wallet\n"
            f"UID: {record.get('uid')}\n"
            f"Address: {record.get('address')}\n"
            f"Status: {record.get('status')}\n"
            f"Mode: {record.get('mode')}\n"
            f"Limit mode: {record.get('limit_mode', 'bounded')}\n"
            f"Per-tx: {record.get('per_tx_limit_slh') or 'unlimited'} SLH\n"
            f"Daily: {record.get('daily_limit_slh') or 'unlimited'} SLH\n"
            f"Asset: {record.get('asset')} | Chain: {record.get('chain_id')}"
        )

    @bot.message_handler(commands=['dist_wallet_set'])
    def dist_wallet_set(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔ OWNER only")
            return
        parts = m.text.split()
        if len(parts) not in {3, 4}:
            bot.reply_to(
                m,
                "Usage: /dist_wallet_set <user_id> unlimited\n"
                "or: /dist_wallet_set <user_id> <per_tx_limit_slh> <daily_limit_slh>"
            )
            return
        uid = _parse_target_uid(parts)
        if not uid:
            bot.reply_to(m, "❌ user_id חייב להיות מספר Telegram חיובי.")
            return
        try:
            from core.distribution_wallet_registry import set_secondary_distribution_wallet
            unlimited = len(parts) == 3 and parts[2].lower() == "unlimited"
            if len(parts) == 3 and not unlimited:
                raise ValueError("Usage: /dist_wallet_set <user_id> unlimited")
            result = set_secondary_distribution_wallet(
                m.from_user.id,
                uid,
                per_tx_limit=None if unlimited else parts[2],
                daily_limit=None if unlimited else parts[3],
                limit_mode="unbounded" if unlimited else "bounded",
            )
            bot.reply_to(
                m,
                "✅ Secondary Distribution Wallet registered\n"
                f"UID: {result['uid']}\n"
                f"Address: {result['address']}\n"
                f"Limit mode: {result.get('limit_mode', 'bounded')}\n"
                f"Per-tx: {result.get('per_tx_limit_slh') or 'unlimited'} SLH\n"
                f"Daily: {result.get('daily_limit_slh') or 'unlimited'} SLH\n"
                "🔐 user_signed_only · wallet signs/broadcasts · no server custody"
            )
        except (PermissionError, ValueError) as exc:
            bot.reply_to(m, f"❌ {exc}")
        except Exception as exc:
            bot.reply_to(m, f"❌ Registration failed safely: {type(exc).__name__}")

    @bot.message_handler(commands=['dist_wallet_revoke'])
    def dist_wallet_revoke(m):
        if not is_owner(m):
            bot.reply_to(m, "⛔ OWNER only")
            return
        parts = m.text.split()
        if len(parts) != 2:
            bot.reply_to(m, "Usage: /dist_wallet_revoke <user_id>")
            return
        uid = _parse_target_uid(parts)
        if not uid:
            bot.reply_to(m, "❌ user_id חייב להיות מספר Telegram חיובי.")
            return
        try:
            from core.distribution_wallet_registry import revoke_secondary_distribution_wallet
            result = revoke_secondary_distribution_wallet(m.from_user.id, uid)
            bot.reply_to(
                m,
                f"✅ Secondary Distribution Wallet revoked for {uid}\n"
                f"Address: {result.get('address')}"
            )
        except (PermissionError, ValueError) as exc:
            bot.reply_to(m, f"❌ {exc}")
        except Exception as exc:
            bot.reply_to(m, f"❌ Revoke failed safely: {type(exc).__name__}")

    print("✅ dev_admin loaded")
