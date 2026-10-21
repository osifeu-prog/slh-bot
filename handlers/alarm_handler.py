"""Owner-only, persistent one-shot alarm for the SLH Telegram bot."""
import hashlib
import json
import os
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

OWNER_UID = str(os.getenv("SLH_OWNER_UID", "8789977826")).strip()
TZ_NAME = os.getenv("SLH_TIMEZONE", "Asia/Jerusalem")
TZ = ZoneInfo(TZ_NAME)
_LOCK = threading.RLock()
_SCHEDULER_STARTED = False
_SCHEDULER_BOTS = {}


def state_path():
    override = os.getenv("SLH_ALARM_STATE_FILE")
    if override:
        return Path(override)
    mounted = Path("/app/state")
    if mounted.is_dir():
        return mounted / "slh_owner_alarm.json"
    return Path("state/slh_owner_alarm.json")


def load_state():
    path = state_path()
    with _LOCK:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}


def save_state(data):
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        fd, temp_name = tempfile.mkstemp(prefix=".slh-alarm-", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_name, path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass


def next_fire_time(hhmm, now=None):
    try:
        hour_text, minute_text = str(hhmm).split(":", 1)
        hour, minute = int(hour_text), int(minute_text)
    except (ValueError, TypeError):
        raise ValueError("TIME_FORMAT") from None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("TIME_RANGE")
    current = (now or datetime.now(TZ)).astimezone(TZ)
    target = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= current:
        target += timedelta(days=1)
    return target


def _bot_key(bot):
    token = str(getattr(bot, "token", "") or "").strip()
    if token:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
    return f"process-local:{id(bot)}"


def schedule_alarm(chat_id, hhmm, now=None, bot_key=None):
    target = next_fire_time(hhmm, now=now)
    data = {
        "enabled": True,
        "chat_id": int(chat_id),
        "bot_key": bot_key,
        "attempts": 0,
        "fire_at": target.astimezone(timezone.utc).isoformat(),
        "timezone": TZ_NAME,
        "local_time": target.strftime("%Y-%m-%d %H:%M"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    save_state(data)
    return data


def disable_alarm():
    data = load_state()
    data.update({"enabled": False, "disabled_at": datetime.now(timezone.utc).isoformat()})
    save_state(data)
    return data


def _morning_message():
    lines = [
        "⏰ בוקר טוב! שעון SLH הופעל.",
        "",
        "📋 התחלת יום:",
        "• /morning_check — דוח בוקר, בריאות ומשימות",
        "• /task — רשימת המשימות",
        "• /doctor — אבחון מערכת",
        "• /agent_status — מצב הסוכן",
        "• /check_exchange — בדיקת Exchange לקריאה בלבד",
        "",
        "ההתראות מפעילות בדיקות ודיווח בלבד; הן לא פותחות מסחר, לא משנות יתרות ולא מבצעות העברות.",
    ]
    try:
        from state_manager import load_db
        db = load_db()
        tasks = db.get("tasks", {}) if isinstance(db, dict) else {}
        active = sum(1 for task in tasks.values() if str(task.get("status", "active")).lower() not in {"done", "completed", "closed"})
        lines.insert(3, f"• משימות במאגר: {active}")
    except Exception:
        lines.insert(3, "• מצב המשימות יופיע בדוח /morning_check")
    return "\n".join(lines)


def _deliver_due_alarm(now=None):
    """Attempt a due alarm with persisted retry state; delivery is at-least-once."""
    data = load_state()
    if not data.get("enabled") or not data.get("fire_at"):
        return "not_due"

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    due = datetime.fromisoformat(data["fire_at"])
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    if current < due.astimezone(timezone.utc):
        return "not_due"

    retry_value = data.get("next_attempt_at")
    if retry_value:
        retry_at = datetime.fromisoformat(retry_value)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        if current < retry_at.astimezone(timezone.utc):
            return "retry_wait"

    with _LOCK:
        bot = _SCHEDULER_BOTS.get(data.get("bot_key"))
    if bot is None:
        data.update({
            "attempts": int(data.get("attempts", 0)) + 1,
            "last_attempt_at": current.isoformat(),
            "next_attempt_at": (current + timedelta(minutes=1)).isoformat(),
            "last_error": "ALARM_BOT_NOT_REGISTERED",
        })
        save_state(data)
        return "bot_unavailable"

    # Persist a retry deadline before the network call. If the process dies during
    # delivery, the alarm remains enabled and is retried after this deadline.
    data.update({
        "attempts": int(data.get("attempts", 0)) + 1,
        "last_attempt_at": current.isoformat(),
        "next_attempt_at": (current + timedelta(minutes=1)).isoformat(),
    })
    save_state(data)
    try:
        bot.send_message(int(data["chat_id"]), _morning_message())
    except Exception as exc:
        data["last_error"] = type(exc).__name__
        save_state(data)
        print("[OWNER_ALARM] delivery failed; retry scheduled:", type(exc).__name__)
        return "send_failed"

    data.update({"enabled": False, "fired_at": current.isoformat()})
    data.pop("next_attempt_at", None)
    data.pop("last_error", None)
    save_state(data)
    return "sent"


def _scheduler_loop():
    while True:
        try:
            _deliver_due_alarm()
        except Exception as exc:
            print("[OWNER_ALARM] scheduler iteration failed:", type(exc).__name__)
        time.sleep(10)


def start_scheduler(bot):
    global _SCHEDULER_STARTED
    key = _bot_key(bot)
    with _LOCK:
        _SCHEDULER_BOTS[key] = bot
        if _SCHEDULER_STARTED:
            return
        _SCHEDULER_STARTED = True
    thread = threading.Thread(target=_scheduler_loop, name="slh-owner-alarm", daemon=True)
    thread.start()


def register(bot, context=None):
    from telebot import types

    start_scheduler(bot)

    def is_owner_private(message):
        user = getattr(message, "from_user", None)
        chat = getattr(message, "chat", None)
        return (
            str(getattr(user, "id", "")) == OWNER_UID
            and str(getattr(chat, "type", "")).lower() == "private"
        )

    def keyboard():
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("06:30", callback_data="owner_alarm:set:06:30"),
            types.InlineKeyboardButton("07:00", callback_data="owner_alarm:set:07:00"),
            types.InlineKeyboardButton("07:30", callback_data="owner_alarm:set:07:30"),
            types.InlineKeyboardButton("08:00", callback_data="owner_alarm:set:08:00"),
        )
        markup.add(types.InlineKeyboardButton("🔕 כיבוי השעון", callback_data="owner_alarm:off"))
        return markup

    def show_status(chat_id):
        data = load_state()
        if data.get("enabled") and data.get("fire_at"):
            target = datetime.fromisoformat(data["fire_at"]).astimezone(TZ)
            status = f"🟢 השעון פעיל\n⏰ {target.strftime('%A, %d/%m/%Y בשעה %H:%M')} ({TZ_NAME})"
        else:
            status = "⚪ השעון כבוי ואין התראה מתוזמנת."
        bot.send_message(
            chat_id,
            "⏰ שעון מעורר SLH\n\n" + status
            + "\n\nבחר שעה או שלח /alarm_set HH:MM.\nלדוגמה: /alarm_set 07:00",
            reply_markup=keyboard(),
        )

    @bot.message_handler(commands=["alarm"])
    def alarm_status(message):
        if not is_owner_private(message):
            return
        show_status(message.chat.id)

    @bot.message_handler(commands=["alarm_set"])
    def alarm_set(message):
        if not is_owner_private(message):
            return
        parts = (getattr(message, "text", "") or "").split()
        if len(parts) != 2:
            bot.reply_to(message, "שימוש: /alarm_set HH:MM\nדוגמה: /alarm_set 07:00")
            return
        try:
            data = schedule_alarm(message.chat.id, parts[1], bot_key=_bot_key(bot))
        except ValueError:
            bot.reply_to(message, "שעה לא תקינה. השתמש בתבנית HH:MM, למשל 07:00.")
            return
        target = datetime.fromisoformat(data["fire_at"]).astimezone(TZ)
        bot.send_message(message.chat.id, f"✅ השעון נשמר: {target.strftime('%d/%m/%Y בשעה %H:%M')} ({TZ_NAME}).\nההתראה חד־פעמית ותציג את פתיחת יום SLH.", reply_markup=keyboard())

    @bot.message_handler(commands=["alarm_off"])
    def alarm_off(message):
        if not is_owner_private(message):
            return
        disable_alarm()
        bot.send_message(message.chat.id, "🔕 השעון בוטל.")

    @bot.callback_query_handler(func=lambda call: str(getattr(call, "data", "")).startswith("owner_alarm:"))
    def alarm_callback(call):
        user = getattr(call, "from_user", None)
        chat = getattr(getattr(call, "message", None), "chat", None)
        if str(getattr(user, "id", "")) != OWNER_UID or str(getattr(chat, "type", "")).lower() != "private":
            bot.answer_callback_query(call.id, "אין הרשאה.")
            return
        data = str(call.data)
        if data == "owner_alarm:off":
            disable_alarm()
            bot.answer_callback_query(call.id, "השעון כובה.")
            show_status(chat.id)
            return
        prefix = "owner_alarm:set:"
        if data.startswith(prefix):
            hhmm = data[len(prefix):]
            try:
                saved = schedule_alarm(chat.id, hhmm, bot_key=_bot_key(bot))
            except ValueError:
                bot.answer_callback_query(call.id, "שעה לא תקינה.")
                return
            target = datetime.fromisoformat(saved["fire_at"]).astimezone(TZ)
            bot.answer_callback_query(call.id, f"נשמר ל-{target.strftime('%H:%M')}")
            show_status(chat.id)
