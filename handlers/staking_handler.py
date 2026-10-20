import os
import secrets
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from core.stake_position import get_positions, get_position
from core import staking_service


ACADEMY_NOTE = (
    "Academy נשאר פעיל ונפרד מ-Staking. "
    "אין צורך להשלים קורס כדי לבצע Staking.\n\n"
    "Staking הוא מנגנון פנימי של Credits ואינו נכס on-chain."
)



def _fmt(x):
    """Show money without float noise (3.9000000000000004 -> 3.9)."""
    try:
        return ("%.8f" % float(x)).rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return str(x)


_STAKING_TZ = ZoneInfo("Asia/Jerusalem")
_PENDING_STAKE_TTL_SECONDS = 600
_PENDING_STAKES = {}


def _local_time(epoch):
    try:
        return datetime.fromtimestamp(float(epoch), tz=_STAKING_TZ).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError, OverflowError, OSError):
        return "לא זמין"


def _stake_preview_text(amount, lock_days, unlocks_at):
    return (
        "🔒 אישור נעילת Credits ב-Staking\n\n"
        f"סכום לנעילה: {_fmt(amount)} Credits\n"
        f"תקופת נעילה: {int(lock_days)} ימים\n"
        f"מועד שחרור משוער אם תאשר עכשיו: {_local_time(unlocks_at)} (שעון ישראל)\n\n"
        "ה-Credits יהיו נעולים עד מועד השחרור ולא יהיו זמינים לשימוש רגיל.\n"
        "תגמול אינו מובטח; הוא עשוי להיות אפס ומשתנה בהתאם למנגנון חלוקת ההכנסות הפעיל "
        "ולתנאים החלים. אין כאן הבטחת תשואה.\n"
        "זה Staking פנימי של Credits, לא עסקת on-chain.\n\n"
        "בדוק את הסכום ואת תקופת הנעילה לפני האישור."
    )


def _queue_stake_confirmation(uid, amount, lock_days, command):
    """Prepare a short-lived, process-local confirmation without touching the DB."""
    token = secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:8]
    _PENDING_STAKES[token] = {
        "uid": str(uid),
        "amount": int(amount),
        "lock_days": int(lock_days),
        "command": str(command),
        "created_at": time.time(),
    }
    # Prune stale confirmations to keep the process-local cache bounded.
    cutoff = time.time() - _PENDING_STAKE_TTL_SECONDS
    for key, item in list(_PENDING_STAKES.items()):
        if float(item.get("created_at", 0) or 0) < cutoff:
            _PENDING_STAKES.pop(key, None)
    return token

def register(bot):
    def _handle_stake_callback(call):
        data = str(getattr(call, "data", "") or "")
        parts = data.split(":")
        token = parts[-1] if len(parts) == 2 else ""
        pending = _PENDING_STAKES.get(token)
        caller_uid = str(getattr(getattr(call, "from_user", None), "id", ""))
        if not pending or caller_uid != str(pending.get("uid")):
            try:
                bot.answer_callback_query(call.id, "האישור פג או שאינו שייך לחשבונך.")
            except Exception:
                pass
            return

        age = time.time() - float(pending.get("created_at", 0) or 0)
        if age < 0 or age > _PENDING_STAKE_TTL_SECONDS:
            _PENDING_STAKES.pop(token, None)
            try:
                bot.answer_callback_query(call.id, "האישור פג. שלח שוב את פקודת ה-Staking.")
            except Exception:
                pass
            return

        if parts[0] == "slh_stake_cancel":
            _PENDING_STAKES.pop(token, None)
            try:
                bot.answer_callback_query(call.id, "הפעולה בוטלה. לא בוצע שינוי ביתרה.")
            except Exception:
                pass
            try:
                bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            except Exception:
                pass
            return

        amount = int(pending["amount"])
        days = int(pending["lock_days"])
        command = str(pending["command"])
        try:
            result = staking_service.stake_locked(
                caller_uid,
                amount,
                lock_days=days,
                meta={"source": "telegram", "command": command, "confirmed_via": "inline_button"},
                request_id=f"telegram-stake-confirm:{token}",
            )
            status = str(result.get("status") or "unknown")
            if status == "duplicate":
                reply = "ℹ️ בקשת הנעילה הזו כבר טופלה; לא נוצרה נעילה נוספת."
            elif status == "completed":
                position = result.get("position") or {}
                reply = (
                    "✅ נעילת Credits אושרה והושלמה.\n"
                    f"סכום: {_fmt(amount)} Credits\n"
                    f"תקופה: {days} ימים\n"
                    f"מועד שחרור: {_local_time(position.get('unlocks_at'))} (שעון ישראל)\n"
                    f"יתרה זמינה: {_fmt(result.get('credits'))}\n"
                    f"נעול כעת: {_fmt(result.get('staked'))}\n"
                    "תגמול אינו מובטח ויכול להיות אפס.\n"
                    f"מזהה פוזיציה: {position.get('id', '—')}"
                )
            else:
                reply = "הפעולה לא הושלמה. בדוק את מצב הפוזיציות לפני ניסיון חוזר."
            try:
                bot.answer_callback_query(call.id, "האישור התקבל.")
            except Exception:
                pass
            try:
                bot.send_message(call.message.chat.id, reply)
            except Exception:
                bot.reply_to(call.message, reply)
            if status in {"completed", "duplicate"}:
                _PENDING_STAKES.pop(token, None)
        except ValueError as exc:
            try:
                bot.answer_callback_query(call.id, "לא ניתן להשלים את הפעולה.")
            except Exception:
                pass
            try:
                bot.send_message(call.message.chat.id, "⛔ " + str(exc)[:250])
            except Exception:
                bot.reply_to(call.message, "⛔ " + str(exc)[:250])
        except Exception as exc:
            try:
                bot.answer_callback_query(call.id, "הפעולה נכשלה.")
            except Exception:
                pass
            try:
                bot.send_message(call.message.chat.id, "⛔ הפעולה לא הושלמה: " + type(exc).__name__)
            except Exception:
                pass

    callback_registrar = getattr(bot, "callback_query_handler", None)
    if callable(callback_registrar):
        callback_registrar(
            func=lambda call: str(getattr(call, "data", "") or "").startswith(
                ("slh_stake_confirm:", "slh_stake_cancel:")
            )
        )(_handle_stake_callback)

    @bot.message_handler(commands=["stake"])
    def stake(msg):
        parts = (msg.text or "").split()
        if len(parts) != 2:
            bot.reply_to(msg, "שימוש: /stake <amount>\n\n" + ACADEMY_NOTE)
            return
        try:
            amount = int(parts[1])
            if amount <= 0:
                raise ValueError("amount must be positive")
            uid = str(msg.from_user.id)
            token = _queue_stake_confirmation(uid, amount, 30, "stake")
            unlocks_at = time.time() + 30 * 86400
            from telebot import types
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton(
                    "✅ אשר נעילה",
                    callback_data=f"slh_stake_confirm:{token}",
                ),
                types.InlineKeyboardButton(
                    "✖️ ביטול",
                    callback_data=f"slh_stake_cancel:{token}",
                ),
            )
            bot.reply_to(msg, _stake_preview_text(amount, 30, unlocks_at), reply_markup=markup)
        except ValueError:
            bot.reply_to(msg, "הסכום חייב להיות מספר שלם וחיובי.\n\n" + ACADEMY_NOTE)
        except Exception as e:
            bot.reply_to(msg, "לא ניתן להציג את מסך האישור: " + type(e).__name__)

    @bot.message_handler(commands=["unstake"])
    def unstake(msg):
        parts = msg.text.split()
        if len(parts) < 2:
            bot.reply_to(msg, "שימוש: /unstake <position_id>\nהשחרור מתבצע רק לאחר תום תקופת הנעילה.\nבדיקת פוזיציות: /positions")
            return
        uid = str(msg.from_user.id)
        pos_id = parts[1]
        pos = get_position(pos_id)
        if not pos or str(pos.get("uid")) != uid:
            bot.reply_to(msg, "הפוזיציה לא נמצאה או לא שייכת לך.")
            return
        try:
            res = staking_service.unstake_locked(uid, pos_id, meta={"source": "telegram", "command": "unstake"})
            if res.get("status") in {"duplicate", "already_unlocked"}:
                bot.reply_to(msg, "הפוזיציה כבר שוחררה.")
                return
            if res.get("status") in {"legacy_refund_review_required", "position_state_review_required"}:
                code = res.get("code") or res.get("status")
                bot.reply_to(
                    msg,
                    "⛔ השחרור נחסם לבדיקה חשבונאית (" + str(code) + "). "
                    "לא בוצע שינוי ביתרה או בסטייק. אין לנסות שוב עד לבדיקת המקור.",
                )
                return
            bot.reply_to(msg, f"שוחררו {pos.get('amount')} credits.\nיתרה: {_fmt(res.get('credits'))}\nסטייק: {_fmt(res.get('staked'))}")
        except Exception as e:
            bot.reply_to(msg, str(e))

    @bot.message_handler(commands=["stake_lock"])
    def stake_lock(msg):
        parts = (msg.text or "").split()
        if len(parts) != 3:
            bot.reply_to(msg, "שימוש: /stake_lock <amount> <days>\n\n" + ACADEMY_NOTE)
            return
        try:
            amount = int(parts[1])
            days = int(parts[2])
            if amount <= 0 or days <= 0 or days > 3650:
                raise ValueError("amount/days out of range")
            uid = str(msg.from_user.id)
            token = _queue_stake_confirmation(uid, amount, days, "stake_lock")
            unlocks_at = time.time() + days * 86400
            from telebot import types
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton(
                    "✅ אשר נעילה",
                    callback_data=f"slh_stake_confirm:{token}",
                ),
                types.InlineKeyboardButton(
                    "✖️ ביטול",
                    callback_data=f"slh_stake_cancel:{token}",
                ),
            )
            bot.reply_to(msg, _stake_preview_text(amount, days, unlocks_at), reply_markup=markup)
        except ValueError:
            bot.reply_to(msg, "הסכום חייב להיות חיובי והתקופה בין 1 ל-3650 ימים.\n\n" + ACADEMY_NOTE)
        except Exception as e:
            bot.reply_to(msg, "לא ניתן להציג את מסך האישור: " + type(e).__name__)

    @bot.message_handler(commands=["positions"])
    def positions_cmd(msg):
        uid = str(msg.from_user.id)
        positions = get_positions(uid)
        if not positions:
            bot.reply_to(msg, "אין לך פוזיציות פתוחות.")
            return
        lines = ["🔒 הפוזיציות שלך:"]
        for pid, pos in positions.items():
            lines.append(
                f"• {_fmt(pos.get('amount'))} Credits | {int(pos.get('lock_days', 0) or 0)} ימים "
                f"| {pos.get('status', 'unknown')}\n"
                f"  שחרור: {_local_time(pos.get('unlocks_at'))} | מזהה: {pid}"
            )
        bot.reply_to(msg, "\n".join(lines))

    @bot.message_handler(commands=["stake_rewards"])
    def rewards_cmd(msg):
        uid = str(msg.from_user.id)
        from core.reward_engine import calculate_reward, claim_reward, accrue
        positions = get_positions(uid)
        if not positions:
            bot.reply_to(msg, "אין פוזיציות.")
            return
        parts = msg.text.split()
        if len(parts) >= 3 and parts[1].lower() == "claim":
            pos_id = parts[2]
            pos = get_position(pos_id)
            if not pos or str(pos.get("uid")) != uid:
                bot.reply_to(msg, "הפוזיציה לא נמצאה או לא שייכת לך.")
                return
            try:
                accrued = accrue(pos_id)
                if accrued.get("status") == "closed":
                    bot.reply_to(msg, "הפוזיציה כבר נסגרה.")
                    return
                result = claim_reward(pos_id)
                if result.get("status") in {"already_paid", "duplicate", "nothing_to_claim"}:
                    bot.reply_to(msg, "אין כרגע תגמול חדש למימוש.")
                    return
                bot.reply_to(msg, f"תגמול שולם: {_fmt(result.get('amount', 0))} credits\nיתרה: {_fmt(result.get('after', 'עודכנה'))}")
            except Exception as e:
                bot.reply_to(msg, str(e))
            return
        lines = ["תגמולים צפויים:", "למימוש: /stake_rewards claim <position_id>"]
        for pid in positions:
            try:
                r = calculate_reward(pid)
            except Exception:
                r = 0
            lines.append(f"{pid}: {r} credits")
        bot.reply_to(msg, "\n".join(lines))

    @bot.message_handler(commands=["unstake_lock"])
    def unstake_lock_cmd(msg):
        parts = msg.text.split()
        if len(parts) < 2:
            bot.reply_to(msg, "שימוש: /unstake_lock <position_id>")
            return
        uid = str(msg.from_user.id)
        pos_id = parts[1]
        pos = get_position(pos_id)
        if not pos or str(pos.get("uid")) != uid:
            bot.reply_to(msg, "הפוזיציה לא נמצאה או לא שייכת לך.")
            return
        try:
            res = staking_service.unstake_locked(uid, pos_id, meta={"source": "telegram", "command": "unstake_lock"})
            if res.get("status") in {"duplicate", "already_unlocked"}:
                bot.reply_to(msg, "הפוזיציה כבר שוחררה.")
                return
            if res.get("status") in {"legacy_refund_review_required", "position_state_review_required"}:
                code = res.get("code") or res.get("status")
                bot.reply_to(
                    msg,
                    "⛔ השחרור נחסם לבדיקה חשבונאית (" + str(code) + "). "
                    "לא בוצע שינוי ביתרה או בסטייק. אין לנסות שוב עד לבדיקת המקור.",
                )
                return
            bot.reply_to(msg, f"שוחררו {pos.get('amount')} credits.\nיתרה: {_fmt(res.get('credits'))}\nסטייק: {_fmt(res.get('staked'))}")
        except Exception as e:
            bot.reply_to(msg, str(e))

    @bot.message_handler(commands=["staking"])
    def staking_help(msg):
        message = (
            "🔒 Staking של Credits\n\n"
            + ACADEMY_NOTE
            + "\n\nCredits נעולים אינם זמינים לשימוש עד לשחרור לפי תנאי הפוזיציה. "
            "אין הבטחת רווח.\n\n"
            "פקודות:\n"
            "/stake <amount> - נעילה ל-30 יום\n"
            "/stake_lock <amount> <days> - נעילה לתקופה\n"
            "/unstake <position_id> - שחרור לאחר תום הנעילה\n"
            "/unstake_lock <position_id> - alias לשחרור\n"
            "/positions - הפוזיציות שלך\n"
            "/stake_rewards - תגמולים\n"
            "/stake_rewards claim <position_id> - מימוש תגמול חדש"
        )
        mini_app_url = (
            os.getenv("SLH_MINI_APP_URL")
            or "https://slh-cloud-bot-production.up.railway.app/mini-app-v4"
        ).strip()
        url_parts = urlsplit(mini_app_url)
        query = [
            (key, value)
            for key, value in parse_qsl(url_parts.query, keep_blank_values=True)
            if key != "screen"
        ]
        query.append(("screen", "stake"))
        target = urlunsplit((
            url_parts.scheme,
            url_parts.netloc,
            url_parts.path,
            urlencode(query),
            url_parts.fragment,
        ))
        try:
            from telebot import types
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    "🔒 פתח Staking והעבר Credits לנעילה",
                    web_app=types.WebAppInfo(url=target),
                )
            )
        except (ImportError, TypeError, ValueError):
            markup = None

        if markup is not None:
            bot.reply_to(msg, message, reply_markup=markup)
        else:
            bot.reply_to(msg, message)
