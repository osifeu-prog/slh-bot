"""Consent-based, owner-confirmed invitations to the music learning experience.

This handler deliberately does not reuse /broadcast: recipients must opt in
individually, or an owner must explicitly enable the current community group.
A preview creates a short-lived campaign; sending requires a second command
with the exact preview token. No finance or Exchange claims are included.
"""
from __future__ import annotations

import secrets
import time
from datetime import datetime, timedelta, timezone

import state_manager
from core.identity import OWNER_TELEGRAM_ID


CAMPAIGN_KEY = "music_academy_invite_campaign"
OPTED_USERS_KEY = "music_academy_invite_opted_users"
OPTED_GROUPS_KEY = "music_academy_invite_opted_groups"
CAMPAIGN_TTL_SECONDS = 900
INVITE_URL = "https://slh-cloud-bot-production.up.railway.app/mini-app-v4"
INVITE_TEXT = (
    "🎹 מזמינים אותך לנסות את מרחב המוזיקה והלמידה של SLH OS!\n\n"
    "🎼 לימוד תווים וקצב\n"
    "🎵 תאוריה מוזיקלית, סולמות ואינטרוולים\n"
    "🎹 הרמוניה והובלת קולות\n"
    "🎤 אימון שמיעה, קול אנושי ותרגול הדרגתי\n"
    "🔊 כלי נגינה אינטראקטיביים ותרגול שמיעה\n\n"
    "המרחב מיועד ללמידה ולניסוי. אפשר להתחיל בקצב שלך:\n"
    + INVITE_URL
    + "\n\n"
    "לא מעוניין/ת בהזמנות נוספות? אפשר לכתוב לבוט /music_invite_unsubscribe."
)


def _now():
    return datetime.now(timezone.utc)


def _owner(message):
    try:
        return int(message.from_user.id) == int(OWNER_TELEGRAM_ID)
    except (AttributeError, TypeError, ValueError):
        return False


def _private(message):
    return getattr(getattr(message, "chat", None), "type", None) == "private"


def _safe_map(db, key):
    value = db.get(key, {})
    return value if isinstance(value, dict) else {}


def _active_opt_in_count(mapping, now=None):
    current = now or _now()
    count = 0
    for entry in mapping.values():
        if not isinstance(entry, dict) or entry.get("opted_in") is not True:
            continue
        # Users can be blocked/inactive; a later Telegram send will record that.
        count += 1
    return count


def _pending_campaign(db, token, now=None):
    campaign = _safe_map(db, CAMPAIGN_KEY)
    current = now or _now()
    if campaign.get("status") != "PREPARED" or not secrets.compare_digest(
        str(campaign.get("token") or ""), str(token or "")
    ):
        return None
    try:
        created = datetime.fromisoformat(str(campaign.get("created_at")).replace("Z", "+00:00"))
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    if (current - created).total_seconds() > CAMPAIGN_TTL_SECONDS:
        return None
    return campaign


def _prepare_campaign():
    token = secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8].upper()
    created_at = _now().isoformat()

    def mutate(db):
        users = _safe_map(db, OPTED_USERS_KEY)
        groups = _safe_map(db, OPTED_GROUPS_KEY)
        user_targets = sorted(
            str(uid) for uid, entry in users.items()
            if isinstance(entry, dict) and entry.get("opted_in") is True
        )
        group_targets = sorted(
            str(chat_id) for chat_id, entry in groups.items()
            if isinstance(entry, dict) and entry.get("opted_in") is True
        )
        campaign = {
            "status": "PREPARED",
            "token": token,
            "created_at": created_at,
            "user_targets": user_targets,
            "group_targets": group_targets,
            "sent_user_ids": [],
            "sent_group_ids": [],
            "failed_users": 0,
            "failed_groups": 0,
        }
        db[CAMPAIGN_KEY] = campaign
        return {
            "users": len(user_targets),
            "groups": len(group_targets),
            "token": token,
            "created_at": created_at,
        }

    return state_manager.atomic_update(mutate)


def _record_send(token, target_type, target_id, ok):
    sent_key = "sent_user_ids" if target_type == "user" else "sent_group_ids"
    failed_key = "failed_users" if target_type == "user" else "failed_groups"

    def mutate(db):
        campaign = _safe_map(db, CAMPAIGN_KEY)
        if campaign.get("token") != token:
            return False
        if ok:
            sent = campaign.setdefault(sent_key, [])
            if target_id not in sent:
                sent.append(target_id)
        else:
            campaign[failed_key] = int(campaign.get(failed_key, 0) or 0) + 1
        return True

    return state_manager.atomic_update(mutate)


def _send_campaign(bot, token):
    db = state_manager.load_db()
    campaign = _pending_campaign(db, token)
    if campaign is None:
        return {"status": "INVALID_OR_EXPIRED_PREVIEW"}

    # Reload opt-in state immediately before sending; recipients who withdrew
    # consent after preview are excluded.
    users = _safe_map(db, OPTED_USERS_KEY)
    groups = _safe_map(db, OPTED_GROUPS_KEY)
    user_targets = [
        uid for uid in campaign.get("user_targets", [])
        if isinstance(users.get(str(uid)), dict)
        and users[str(uid)].get("opted_in") is True
        and str(uid) not in set(map(str, campaign.get("sent_user_ids", [])))
    ]
    group_targets = [
        chat_id for chat_id in campaign.get("group_targets", [])
        if isinstance(groups.get(str(chat_id)), dict)
        and groups[str(chat_id)].get("opted_in") is True
        and str(chat_id) not in set(map(str, campaign.get("sent_group_ids", [])))
    ]

    sent_users = sent_groups = failed_users = failed_groups = 0
    for uid in user_targets:
        try:
            bot.send_message(int(uid), INVITE_TEXT, disable_web_page_preview=False)
            _record_send(token, "user", str(uid), True)
            sent_users += 1
        except Exception:
            _record_send(token, "user", str(uid), False)
            failed_users += 1
        time.sleep(0.05)

    for chat_id in group_targets:
        try:
            bot.send_message(int(chat_id), INVITE_TEXT, disable_web_page_preview=False)
            _record_send(token, "group", str(chat_id), True)
            sent_groups += 1
        except Exception:
            _record_send(token, "group", str(chat_id), False)
            failed_groups += 1
        time.sleep(0.05)

    def finish(db2):
        current = _safe_map(db2, CAMPAIGN_KEY)
        if current.get("token") == token:
            current["status"] = "SENT" if not (failed_users or failed_groups) else "PARTIAL"
            current["finished_at"] = _now().isoformat()
            current["last_result"] = {
                "sent_users": sent_users,
                "sent_groups": sent_groups,
                "failed_users": failed_users,
                "failed_groups": failed_groups,
            }
    state_manager.atomic_update(finish)
    return {
        "status": "SENT" if not (failed_users or failed_groups) else "PARTIAL",
        "sent_users": sent_users,
        "sent_groups": sent_groups,
        "failed_users": failed_users,
        "failed_groups": failed_groups,
    }


def register(bot):
    @bot.message_handler(commands=["music_invite_subscribe"])
    def subscribe(message):
        if not _private(message):
            bot.reply_to(message, "לשמירת פרטיות, יש להירשם לקבלת הזמנות בהודעה פרטית לבוט.")
            return
        uid = str(message.from_user.id)

        def mutate(db):
            users = db.setdefault(OPTED_USERS_KEY, {})
            if not isinstance(users, dict):
                users = {}
                db[OPTED_USERS_KEY] = users
            users[uid] = {
                "opted_in": True,
                "updated_at": _now().isoformat(),
                "source": "explicit_command",
            }
        state_manager.atomic_update(mutate)
        bot.reply_to(
            message,
            "✅ נרשמת לקבלת הזמנות למרחב המוזיקה. "
            "אפשר לבטל בכל עת עם /music_invite_unsubscribe."
        )

    @bot.message_handler(commands=["music_invite_unsubscribe"])
    def unsubscribe(message):
        if not _private(message):
            bot.reply_to(message, "לביטול הרשמה, כתוב/י לבוט בפרטי /music_invite_unsubscribe.")
            return
        uid = str(message.from_user.id)

        def mutate(db):
            users = db.setdefault(OPTED_USERS_KEY, {})
            if isinstance(users, dict):
                users[uid] = {
                    "opted_in": False,
                    "updated_at": _now().isoformat(),
                    "source": "explicit_unsubscribe",
                }
            campaign = _safe_map(db, CAMPAIGN_KEY)
            if isinstance(campaign.get("user_targets"), list):
                campaign["user_targets"] = [
                    item for item in campaign["user_targets"] if str(item) != uid
                ]
        state_manager.atomic_update(mutate)
        bot.reply_to(message, "בוצע: לא תקבל/י הזמנות עתידיות למרחב המוזיקה.")

    @bot.message_handler(commands=["music_invite"])
    def music_invite(message):
        if not _owner(message):
            bot.reply_to(
                message,
                "פקודת הניהול מיועדת לבעלים. להצטרפות לקבלת הזמנות: /music_invite_subscribe"
            )
            return
        parts = (message.text or "").split(maxsplit=2)
        action = parts[1].strip().lower() if len(parts) > 1 else "help"

        if action in {"help", "--help"}:
            bot.reply_to(
                message,
                "🎵 Music invite — מסלול בטוח\n"
                "/music_invite status — מספר נרשמים וקבוצות מורשות\n"
                "/music_invite group_on — אישור הזמנות לקבוצה הנוכחית (מתוך הקבוצה)\n"
                "/music_invite group_off — ביטול הזמנות לקבוצה הנוכחית\n"
                "/music_invite preview — הכנת תצוגה מקדימה ומספר נמענים\n"
                "/music_invite confirm TOKEN — שליחה לנמענים שהסכימו בלבד\n"
                "הודעה לא נשלחת בעת preview. כל תצוגה מקדימה פגה אחרי 15 דקות."
            )
            return

        if action == "group_on":
            if getattr(message.chat, "type", None) not in {"group", "supergroup"}:
                bot.reply_to(message, "יש להריץ group_on בתוך הקבוצה שתרצה לקבל הזמנות.")
                return
            try:
                member = bot.get_chat_member(message.chat.id, message.from_user.id)
                if str(getattr(member, "status", "")).lower() not in {"administrator", "creator"}:
                    bot.reply_to(message, "⛔ נדרש מנהל/ת קבוצה כדי לאשר הזמנות לקבוצה.")
                    return
            except Exception:
                bot.reply_to(message, "⛔ לא ניתן לאמת הרשאת מנהל בקבוצה; לא בוצע שינוי.")
                return
            chat_id = str(message.chat.id)

            def enable_group(db):
                groups = db.setdefault(OPTED_GROUPS_KEY, {})
                if not isinstance(groups, dict):
                    groups = {}
                    db[OPTED_GROUPS_KEY] = groups
                groups[chat_id] = {
                    "opted_in": True,
                    "title": getattr(message.chat, "title", None),
                    "username": getattr(message.chat, "username", None),
                    "updated_at": _now().isoformat(),
                    "enabled_by": str(message.from_user.id),
                }
            state_manager.atomic_update(enable_group)
            bot.reply_to(message, "✅ הקבוצה הזו אישרה לקבל הזמנות לימוד מוזיקה. לביטול: /music_invite group_off")
            return

        if action == "group_off":
            if getattr(message.chat, "type", None) not in {"group", "supergroup"}:
                bot.reply_to(message, "יש להריץ group_off בתוך הקבוצה.")
                return
            try:
                member = bot.get_chat_member(message.chat.id, message.from_user.id)
                if str(getattr(member, "status", "")).lower() not in {"administrator", "creator"}:
                    bot.reply_to(message, "⛔ נדרש מנהל/ת קבוצה כדי לבטל את ההרשאה.")
                    return
            except Exception:
                bot.reply_to(message, "⛔ לא ניתן לאמת הרשאת מנהל בקבוצה; לא בוצע שינוי.")
                return
            chat_id = str(message.chat.id)

            def disable_group(db):
                groups = db.setdefault(OPTED_GROUPS_KEY, {})
                if not isinstance(groups, dict):
                    groups = {}
                    db[OPTED_GROUPS_KEY] = groups
                groups[chat_id] = {
                    "opted_in": False,
                    "title": getattr(message.chat, "title", None),
                    "updated_at": _now().isoformat(),
                    "disabled_by": str(message.from_user.id),
                }
            state_manager.atomic_update(disable_group)
            bot.reply_to(message, "בוצע: הקבוצה לא תקבל הזמנות מוזיקה נוספות.")
            return

        if action == "status":
            db = state_manager.load_db()
            users = _safe_map(db, OPTED_USERS_KEY)
            groups = _safe_map(db, OPTED_GROUPS_KEY)
            campaign = _safe_map(db, CAMPAIGN_KEY)
            bot.reply_to(
                message,
                "🎵 Music invite status\n"
                f"נרשמים פרטיים פעילים: {_active_opt_in_count(users)}\n"
                f"קבוצות מאושרות פעילות: {_active_opt_in_count(groups)}\n"
                f"מצב קמפיין אחרון: {campaign.get('status', 'NONE')}"
            )
            return

        if action == "preview":
            try:
                result = _prepare_campaign()
            except Exception as exc:
                bot.reply_to(message, f"❌ לא ניתן להכין תצוגה מקדימה: {type(exc).__name__}")
                return
            bot.reply_to(
                message,
                "👁️ תצוגה מקדימה — לא נשלחה הודעה\n\n"
                + INVITE_TEXT
                + "\n\n"
                + f"נמענים פרטיים שהסכימו: {result['users']}\n"
                + f"קבוצות שאישרו: {result['groups']}\n"
                + f"אסימון אישור חד־פעמי: {result['token']}\n"
                + f"בתוקף עד 15 דקות. לשליחה מפורשת: /music_invite confirm {result['token']}"
            )
            return

        if action == "confirm":
            token = parts[2].strip().upper() if len(parts) > 2 else ""
            if not token:
                bot.reply_to(message, "חסר אסימון. הרץ /music_invite preview ובדוק את הנוסח והנמענים.")
                return
            result = _send_campaign(bot, token)
            if result.get("status") == "INVALID_OR_EXPIRED_PREVIEW":
                bot.reply_to(message, "⛔ התצוגה המקדימה אינה בתוקף. הרץ preview מחדש.")
                return
            bot.reply_to(
                message,
                "📣 תוצאת הזמנה למרחב המוזיקה\n"
                f"נשלח למשתמשים שנרשמו: {result['sent_users']}\n"
                f"נשלח לקבוצות שאישרו: {result['sent_groups']}\n"
                f"נכשל למשתמשים: {result['failed_users']}\n"
                f"נכשל לקבוצות: {result['failed_groups']}\n"
                f"מצב: {result['status']}"
            )
            return

        bot.reply_to(message, "פקודה לא מוכרת. הרץ /music_invite help.")
