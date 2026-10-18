"""Owner-confirmed invitation to the SLH music-learning lab.

The preview command sends nothing. A short-lived, private-chat confirmation is
required before delivery. Users can opt out of future Music Lab invitations.
The handler never calls a financial, trading, wallet, or payment path.
"""
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone

import state_manager
from core.identity import OWNER_TELEGRAM_ID

_PENDING = {}
_TTL_SECONDS = 300
_ALLOWED_GROUP_ROLES = {"free", "vip", "academy"}
_ALLOWED_BOT_GROUP_STATUSES = {"administrator", "creator"}

INVITE_TEXT = (
    "🎹 SLH Music Lab — מעבדת לימוד מוזיקלי\n\n"
    "אפשר לנסות ממשק סינתיסייזר אינטראקטיבי וללמוד קריאת תווים, "
    "תאוריה מוזיקלית, הרמוניה, אימון שמיעה ופיתוח קול בקצב אישי.\n\n"
    "פתחו את SLH OS ובחרו Synth או Academy. "
    "הכלים בשלב לימוד ותרגול בלבד — לא מסחר ולא מוצר פיננסי פתוח.\n\n"
    "להסרה מהזמנות מוזיקליות: לחצו על ״לא לקבל הזמנות״."
)


def _base_url():
    return (
        str(os.getenv("SLH_PUBLIC_BASE_URL") or os.getenv("PUBLIC_BASE_URL")
            or "https://slh-cloud-bot-production.up.railway.app")
        .strip()
        .rstrip("/")
    )


def _targets(db):
    users = db.get("users", {})
    users = users if isinstance(users, dict) else {}
    optouts = db.get("music_lab_invite_opt_outs", {})
    optouts = optouts if isinstance(optouts, dict) else {}
    user_ids = []
    for key, record in users.items():
        uid = str(key).strip()
        if not uid.isdigit() or int(uid) <= 0 or uid == str(OWNER_TELEGRAM_ID):
            continue
        if str(optouts.get(uid, "")).strip():
            continue
        if isinstance(record, dict) and record.get("is_bot") is True:
            continue
        user_ids.append(uid)

    groups = db.get("community_groups", {})
    groups = groups if isinstance(groups, dict) else {}
    group_ids = []
    for raw_id, record in groups.items():
        if not isinstance(record, dict):
            continue
        chat_id = str(record.get("chat_id") or raw_id).strip()
        role = str(record.get("role") or "").strip().lower()
        bot_status = str(record.get("bot_status") or "").strip().lower()
        if not (chat_id.startswith("-") and chat_id[1:].isdigit()):
            continue
        if role in _ALLOWED_GROUP_ROLES and bot_status in _ALLOWED_BOT_GROUP_STATUSES:
            group_ids.append(chat_id)
    return sorted(set(user_ids)), sorted(set(group_ids))


def _markup(*, private):
    from telebot import types

    markup = types.InlineKeyboardMarkup(row_width=1)
    if private:
        markup.add(types.InlineKeyboardButton(
            "🎹 פתיחת מעבדת המוזיקה",
            web_app=types.WebAppInfo(url=_base_url() + "/synth-ui"),
        ))
    else:
        markup.add(types.InlineKeyboardButton(
            "🎹 פתיחת מעבדת המוזיקה",
            url=_base_url() + "/synth-ui",
        ))
    markup.add(types.InlineKeyboardButton(
        "📚 מסלולי הלימוד ב־SLH Academy",
        url="https://t.me/Me_ad_main_bot",
    ))
    markup.add(types.InlineKeyboardButton(
        "🔕 לא לקבל הזמנות מוזיקליות",
        callback_data="mliv:optout",
    ))
    return markup


def _owner_private(message, bot):
    if str(getattr(getattr(message, "from_user", None), "id", "")) != str(OWNER_TELEGRAM_ID):
        bot.reply_to(message, "⛔ הפעולה מיועדת לבעלים בלבד.")
        return False
    if str(getattr(getattr(message, "chat", None), "type", "")).lower() != "private":
        bot.reply_to(message, "⛔ יש להכין ולאשר קמפיין רק בשיחה הפרטית עם הבוט.")
        return False
    return True


def _set_optout(uid, opted_out):
    uid = str(uid).strip()
    if not uid.isdigit() or int(uid) <= 0:
        return False

    def mutate(db):
        values = db.get("music_lab_invite_opt_outs", {})
        if not isinstance(values, dict):
            raise ValueError("MUSIC_INVITE_PREFS_INVALID")
        if opted_out:
            values[uid] = datetime.now(timezone.utc).isoformat()
        else:
            values.pop(uid, None)
        db["music_lab_invite_opt_outs"] = values
        return True

    try:
        return bool(state_manager.atomic_update(mutate))
    except Exception:
        return False


def _append_audit(entry):
    def mutate(db):
        audit = db.get("music_lab_invite_audit", [])
        if not isinstance(audit, list):
            raise ValueError("MUSIC_INVITE_AUDIT_INVALID")
        audit.append(entry)
        db["music_lab_invite_audit"] = audit[-100:]
        return True
    try:
        state_manager.atomic_update(mutate)
        return True
    except Exception as exc:
        print("[MUSIC_INVITE] audit write failed:", type(exc).__name__)
        return False


def _send_campaign(bot, pending):
    campaign_id = pending["campaign_id"]
    user_ids = pending["user_ids"]
    group_ids = pending["group_ids"]
    sent = 0
    failed = 0
    skipped_optout = 0
    stopped_on_state_error = False

    from handlers.broadcast_handler import _send_one

    next_allowed_at = time.monotonic()
    for uid in user_ids:
        # Re-read preferences just before each direct message. If preferences
        # cannot be checked, fail closed rather than continue a mass send.
        try:
            current = state_manager.load_db()
            optouts = current.get("music_lab_invite_opt_outs", {})
            optouts = optouts if isinstance(optouts, dict) else {}
        except Exception:
            stopped_on_state_error = True
            break
        if str(optouts.get(uid, "")).strip():
            skipped_optout += 1
            continue
        ok, next_allowed_at = _send_one(
            bot, uid, INVITE_TEXT, next_allowed_at, reply_markup=_markup(private=True)
        )
        if ok:
            sent += 1
        else:
            failed += 1

    if not stopped_on_state_error:
        for chat_id in group_ids:
            ok, next_allowed_at = _send_one(
                bot, chat_id, INVITE_TEXT, next_allowed_at, reply_markup=_markup(private=False)
            )
            if ok:
                sent += 1
            else:
                failed += 1

    audit_entry = {
        "campaign_id": campaign_id,
        "kind": "music_lab_invitation",
        "initiated_by_owner": str(pending["owner_uid"]) == str(OWNER_TELEGRAM_ID),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "target_users": len(user_ids),
        "target_groups": len(group_ids),
        "sent": sent,
        "failed": failed,
        "skipped_optout": skipped_optout,
        "stopped_on_state_error": stopped_on_state_error,
    }
    audit_ok = _append_audit(audit_entry)
    result = (
        "📣 SLH MUSIC LAB — סיכום שליחה\n"
        f"קמפיין: {campaign_id}\n"
        f"יעדי משתמשים: {len(user_ids)} · קבוצות: {len(group_ids)}\n"
        f"נשלחו: {sent} · נכשלו: {failed}\n"
        f"דולגו עקב הסרה: {skipped_optout}\n"
        f"נעצר עקב בעיית אימות העדפות: {'כן' if stopped_on_state_error else 'לא'}"
    )
    if not audit_ok:
        result += "\n⚠️ לא ניתן לאמת שמירת אודיט — יש לשמור את הסיכום לבדיקה."
    return result


def register(bot):
    @bot.message_handler(commands=["music_invite", "music_invite_preview"])
    def music_invite_preview(message):
        if not _owner_private(message, bot):
            return
        try:
            db = state_manager.load_db()
            if not isinstance(db, dict):
                raise ValueError("DB_INVALID")
            user_ids, group_ids = _targets(db)
        except Exception as exc:
            bot.reply_to(message, "⛔ התצוגה המקדימה חסומה: " + type(exc).__name__)
            return

        if not user_ids and not group_ids:
            bot.reply_to(
                message,
                "אין יעדים כשירים כרגע. לא נשלחה הודעה. "
                "בדוק משתמשים מוכרים והגדרות קבוצות עם תפקיד וסטטוס בוט מאומת.",
            )
            return

        now = time.time()
        for key, value in list(_PENDING.items()):
            if not isinstance(value, dict) or float(value.get("expires_at") or 0) < now:
                _PENDING.pop(key, None)
        campaign_id = uuid.uuid4().hex[:12]
        _PENDING[campaign_id] = {
            "campaign_id": campaign_id,
            "owner_uid": str(message.from_user.id),
            "user_ids": user_ids,
            "group_ids": group_ids,
            "expires_at": now + _TTL_SECONDS,
        }

        from telebot import types
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton(
            f"✅ אשר שליחה · {len(user_ids)} משתמשים · {len(group_ids)} קבוצות",
            callback_data=f"mliv:send:{campaign_id}",
        ))
        markup.add(types.InlineKeyboardButton(
            "ביטול — לא לשלוח",
            callback_data=f"mliv:cancel:{campaign_id}",
        ))
        bot.reply_to(
            message,
            "🔎 תצוגה מקדימה — הזמנת SLH Music Lab\n\n"
            f"משתמשים כשירים כרגע: {len(user_ids)}\n"
            f"קבוצות עם תפקיד וסטטוס בוט מאומתים: {len(group_ids)}\n\n"
            + INVITE_TEXT
            + "\n\nלא נשלחה הודעה בשלב הזה. האישור תקף ל־5 דקות בלבד.",
            reply_markup=markup,
        )

    @bot.message_handler(commands=["music_invite_stop"])
    def music_invite_stop(message):
        ok = _set_optout(str(message.from_user.id), True)
        bot.reply_to(
            message,
            "✅ נשמרה העדפה לא לקבל הזמנות נוספות ל־Music Lab."
            if ok else "❌ לא הצלחתי לשמור את ההעדפה. נסה שוב מאוחר יותר.",
        )

    @bot.message_handler(commands=["music_invite_start"])
    def music_invite_start(message):
        ok = _set_optout(str(message.from_user.id), False)
        bot.reply_to(
            message,
            "✅ הזמנות Music Lab הופעלו מחדש."
            if ok else "❌ לא הצלחתי לעדכן את ההעדפה.",
        )

    @bot.callback_query_handler(func=lambda call: str(call.data or "").startswith("mliv:"))
    def music_invite_callback(call):
        data = str(call.data or "").split(":")
        action = data[1] if len(data) > 1 else ""
        uid = str(getattr(call.from_user, "id", ""))

        if action == "optout":
            ok = _set_optout(uid, True)
            bot.answer_callback_query(
                call.id,
                "העדפה נשמרה." if ok else "לא ניתן לשמור כרגע; נסה /music_invite_stop בפרטי.",
                show_alert=not ok,
            )
            return

        if action not in {"send", "cancel"} or len(data) != 3:
            bot.answer_callback_query(call.id, "פעולה לא תקינה.", show_alert=True)
            return
        campaign_id = data[2]
        pending = _PENDING.get(campaign_id)
        if not pending or pending.get("owner_uid") != uid:
            bot.answer_callback_query(call.id, "התצוגה המקדימה אינה פעילה.", show_alert=True)
            return
        if uid != str(OWNER_TELEGRAM_ID):
            bot.answer_callback_query(call.id, "בעלים בלבד.", show_alert=True)
            return
        if str(getattr(getattr(call.message, "chat", None), "type", "")).lower() != "private":
            bot.answer_callback_query(call.id, "אישור זמין רק בשיחה פרטית.", show_alert=True)
            return
        if float(pending.get("expires_at") or 0) <= time.time():
            _PENDING.pop(campaign_id, None)
            bot.answer_callback_query(call.id, "התצוגה פגה. הפק תצוגה חדשה.", show_alert=True)
            return
        _PENDING.pop(campaign_id, None)
        if action == "cancel":
            bot.answer_callback_query(call.id, "בוטל — לא נשלחה הודעה.")
            try:
                bot.edit_message_reply_markup(
                    call.message.chat.id, call.message.message_id, reply_markup=None
                )
            except Exception:
                pass
            return

        bot.answer_callback_query(call.id, "התחילה שליחת ההזמנה.")
        try:
            result = _send_campaign(bot, pending)
        except Exception as exc:
            result = "⛔ הקמפיין נעצר: " + type(exc).__name__
        bot.send_message(call.message.chat.id, result)


print("✅ music_lab_invite_handler loaded")
