import os
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


def _send_stake_confirmation(bot, msg, uid, amount, lock_days):
    """Show terms and require an owner-bound, short-lived Telegram confirmation."""
    if amount <= 0 or lock_days <= 0:
        bot.reply_to(msg, "הסכום ותקופת הנעילה חייבים להיות חיוביים. לא בוצעה נעילה.")
        return

    issued_at_ms = int(time.time() * 1000)
    confirm_data = f"ss:c:{uid}:{amount}:{lock_days}:{issued_at_ms}"
    cancel_data = f"ss:x:{uid}:{amount}:{lock_days}:{issued_at_ms}"
    if max(len(confirm_data.encode("utf-8")), len(cancel_data.encode("utf-8"))) > 64:
        bot.reply_to(msg, "הבקשה ארוכה מדי להצגת אישור בטוח. לא בוצעה נעילה.")
        return

    try:
        release_estimate = (
            datetime.now(ZoneInfo("Asia/Jerusalem")) + timedelta(days=lock_days)
        ).strftime("%d/%m/%Y %H:%M")
        from telebot import types
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✅ אשר/י נעילה", callback_data=confirm_data),
            types.InlineKeyboardButton("ביטול", callback_data=cancel_data),
        )
    except (ImportError, OverflowError, TypeError, ValueError):
        bot.reply_to(
            msg,
            "לא ניתן להציג אישור נעילה בטוח כרגע. לא בוצעה פעולה; נסה/י שוב מאוחר יותר.",
        )
        return

    bot.reply_to(
        msg,
        "🔒 אישור Staking — לפני ביצוע\n\n"
        f"סכום: {_fmt(amount)} Credits\n"
        f"תקופת נעילה: {lock_days} ימים\n"
        f"מועד שחרור משוער: {release_estimate} (שעון ישראל)\n\n"
        "תנאי תגמול: 80% מההכנסה הנקייה בפועל מיועדים לחלוקה יחסית בין פוזיציות זכאיות. "
        "אין תשואה קבועה או מובטחת; אם ההכנסה הנקייה היא 0, החלוקה היא 0.\n"
        "ה-Credits יהיו נעולים עד תום התקופה. רק לחיצה על «אשר/י נעילה» תבצע את הפעולה.\n"
        "לא בוצע שינוי ביתרה בשלב התצוגה.",
        reply_markup=markup,
    )


def _unlock_label(value):
    try:
        return datetime.fromtimestamp(
            float(value), tz=__import__("datetime").timezone.utc
        ).astimezone(ZoneInfo("Asia/Jerusalem")).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError, OverflowError, OSError):
        return "לא זמין"

def register(bot):
    @bot.message_handler(commands=["stake"])
    def stake(msg):
        parts = msg.text.split()
        if len(parts) < 2:
            bot.reply_to(msg, "Usage: /stake <amount>\n\n" + ACADEMY_NOTE)
            return
        try:
            amount = int(parts[1])
            uid = str(msg.from_user.id)
            _send_stake_confirmation(bot, msg, uid, amount, 30)
        except ValueError:
            bot.reply_to(msg, "שימוש: /stake <amount>\n\n" + ACADEMY_NOTE)
        except Exception as e:
            bot.reply_to(msg, str(e))

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
        parts = msg.text.split()
        if len(parts) < 3:
            bot.reply_to(msg, "שימוש: /stake_lock <amount> <days>\n\n" + ACADEMY_NOTE)
            return
        try:
            amount = int(parts[1])
            days = int(parts[2])
            uid = str(msg.from_user.id)
            _send_stake_confirmation(bot, msg, uid, amount, days)
        except ValueError:
            bot.reply_to(msg, "שימוש: /stake_lock <amount> <days>\n\n" + ACADEMY_NOTE)
        except Exception as e:
            bot.reply_to(msg, str(e))



    @bot.callback_query_handler(func=lambda call: str(getattr(call, "data", "") or "").startswith("ss:"))
    def stake_confirmation_callback(call):
        parts = str(getattr(call, "data", "") or "").split(":")
        if len(parts) != 6 or parts[0] != "ss":
            bot.answer_callback_query(call.id, "בקשת אישור לא תקינה.", show_alert=True)
            return

        action, uid, amount_raw, days_raw, issued_raw = parts[1:]
        if str(getattr(getattr(call, "from_user", None), "id", "")) != uid:
            bot.answer_callback_query(call.id, "האישור שייך למשתמש אחר.", show_alert=True)
            return

        try:
            amount = int(amount_raw)
            lock_days = int(days_raw)
            issued_at_ms = int(issued_raw)
        except (TypeError, ValueError):
            bot.answer_callback_query(call.id, "נתוני האישור אינם תקינים.", show_alert=True)
            return

        age_ms = int(time.time() * 1000) - issued_at_ms
        if age_ms < 0 or age_ms > 10 * 60 * 1000:
            bot.answer_callback_query(call.id, "האישור פג תוקף. שלח/י את הפקודה מחדש.", show_alert=True)
            return
        if amount <= 0 or lock_days <= 0:
            bot.answer_callback_query(call.id, "הסכום או תקופת הנעילה אינם תקינים.", show_alert=True)
            return

        if action == "x":
            bot.answer_callback_query(call.id, "הנעילה בוטלה.")
            bot.reply_to(call.message, "הבקשה בוטלה. לא בוצעה נעילה ולא שונו יתרות.")
            return
        if action != "c":
            bot.answer_callback_query(call.id, "פעולת אישור לא מוכרת.", show_alert=True)
            return

        try:
            result = staking_service.stake_locked(
                uid,
                amount,
                lock_days=lock_days,
                meta={"source": "telegram", "command": "stake_confirmation"},
                request_id=f"telegram-stake-{uid}-{issued_at_ms}",
            )
        except ValueError as exc:
            bot.answer_callback_query(call.id, "הנעילה לא בוצעה.", show_alert=True)
            bot.reply_to(call.message, f"לא בוצעה נעילה: {str(exc)[:200]}")
            return
        except Exception:
            bot.answer_callback_query(call.id, "הנעילה נכשלה; לא ניתן לאשר הצלחה.", show_alert=True)
            bot.reply_to(call.message, "לא ניתן להשלים את הנעילה כרגע. בדוק/י את היתרה והפוזיציות לפני ניסיון נוסף.")
            return

        if result.get("status") == "duplicate":
            bot.answer_callback_query(call.id, "האישור הזה כבר טופל.")
            bot.reply_to(call.message, "האישור הזה כבר עובד בעבר. לא נוצרה נעילה נוספת.")
            return

        position = result.get("position") or {}
        if result.get("status") != "completed" or not position:
            bot.answer_callback_query(call.id, "לא התקבל אישור ביצוע.", show_alert=True)
            bot.reply_to(call.message, "לא התקבל אישור חד-משמעי לביצוע. בדוק/י /positions לפני ניסיון נוסף.")
            return

        bot.answer_callback_query(call.id, "הנעילה בוצעה.")
        bot.reply_to(
            call.message,
            "✅ נעילת Credits הושלמה\n"
            f"סכום: {_fmt(amount)} Credits\n"
            f"תקופת נעילה: {lock_days} ימים\n"
            f"מועד שחרור: {_unlock_label(position.get('unlocks_at'))} (שעון ישראל)\n"
            f"יתרה זמינה: {_fmt(result.get('credits'))}\n"
            f"סה״כ בסטייקינג: {_fmt(result.get('staked'))}\n"
            f"Position: {position.get('id', '—')}\n\n"
            "התגמול אינו מובטח ותלוי בהכנסה נקייה בפועל ובזכאות לחלוקה.",
        )

    @bot.message_handler(commands=["positions"])
    def positions_cmd(msg):
        uid = str(msg.from_user.id)
        positions = get_positions(uid)
        if not positions:
            bot.reply_to(msg, "אין לך פוזיציות פתוחות.")
            return
        lines = ["הפוזיציות שלך:"]
        for pid, pos in positions.items():
            lines.append(
                f"{_fmt(pos.get('amount'))} Credits | {pos.get('lock_days')} ימים | "
                f"{pos.get('status')} | שחרור: {_unlock_label(pos.get('unlocks_at'))}"
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
            "/stake <amount> - הצגת תנאים ואישור נעילה ל-30 יום\n"
            "/stake_lock <amount> <days> - הצגת תנאים ואישור נעילה לתקופה\n"
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
