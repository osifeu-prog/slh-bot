"""Owner-only Telegram Markdown collector.

Only messages sent after /md_start are collected. Existing messages can be
selected explicitly by replying to them with /md_add. The collector is
deterministic, stores a bounded per-owner buffer under state/, and never runs
user-supplied code or reads Telegram chat history.
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path
import re
import time

from core.authority import is_owner
from telebot.handler_backends import ContinueHandling

STATE_DIR = Path("state")
MAX_MESSAGES = 300
MAX_MESSAGE_CHARS = 24_000
MAX_BUFFER_CHARS = 500_000
MAX_LAST = 50
CAPTURE_CONTENT_TYPES = ["text", "photo", "document", "audio", "voice", "video", "animation"]

# Best-effort redaction is a safety net, not a guarantee that arbitrary secrets
# can be recognized. Operators must still avoid sending credentials to Telegram.
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(\b[A-Z0-9_]*(?:API[ _-]?KEY|ACCESS[ _-]?TOKEN|AUTH[ _-]?TOKEN|BOT[ _-]?TOKEN|MCP[ _-]?TOKEN|BRIDGE[ _-]?TOKEN|SECRET(?:[ _-]?KEY)?|PASSWORD|PASSWD|PRIVATE[ _-]?KEY|SEED(?:[ _-]?PHRASE)?|MNEMONIC|CREDENTIALS?)[A-Z0-9_]*\s*[:=]\s*)"
    r'(?:"[^"\n]*"|\'[^\'\n]*\'|[^\s,;]+)',
    re.IGNORECASE,
)
_SECRET_TOKEN_RES = (
    re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b"),
    re.compile(r"\b(?:gsk_[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|hf_[A-Za-z0-9]{20,})\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]+=*", re.IGNORECASE),
)
_PRIVATE_KEY_BLOCK_RE = re.compile(
    r"-----BEGIN [^\r\n]*PRIVATE KEY-----.*?-----END [^\r\n]*PRIVATE KEY-----",
    re.IGNORECASE | re.DOTALL,
)


def _redact_secrets(text: str) -> str:
    """Remove common credentials before anything is persisted or exported."""
    safe = _PRIVATE_KEY_BLOCK_RE.sub("[REDACTED PRIVATE KEY BLOCK]", text)
    safe = _SECRET_ASSIGNMENT_RE.sub(r"\1[REDACTED]", safe)
    for pattern in _SECRET_TOKEN_RES:
        safe = pattern.sub("[REDACTED TOKEN]", safe)
    return safe



def _buffer_path(uid) -> Path:
    uid = str(uid or "").strip()
    if not uid.isdigit():
        raise ValueError("INVALID_UID")
    return STATE_DIR / "md_collector" / ("md_buffer_%s.json" % uid)


def _empty_buffer() -> dict:
    return {"active": False, "started_at": None, "messages": []}


def _load_buffer(uid) -> dict:
    path = _buffer_path(uid)
    if not path.exists():
        return _empty_buffer()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("MD_BUFFER_UNREADABLE") from exc
    if not isinstance(data, dict) or not isinstance(data.get("messages"), list):
        raise ValueError("MD_BUFFER_INVALID")
    data.setdefault("active", False)
    data.setdefault("started_at", None)
    return data


def _save_buffer(uid, data: dict) -> None:
    path = _buffer_path(uid)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    temp = path.with_name(path.name + ".tmp")
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.chmod(temp, 0o600)
    except OSError:
        pass
    os.replace(temp, path)


def _message_text(message):
    value = getattr(message, "text", None)
    if value is None:
        value = getattr(message, "caption", None)
    return value if isinstance(value, str) and value else None


def _message_kind(message) -> str:
    entities = getattr(message, "entities", None) or []
    if not entities:
        entities = getattr(message, "caption_entities", None) or []
    types = {str(getattr(entity, "type", "")) for entity in entities}
    if "pre" in types:
        return "code"
    if "code" in types:
        return "inline-code"
    return "text"


def _is_owner_private(message) -> bool:
    chat = getattr(message, "chat", None)
    user = getattr(message, "from_user", None)
    if not chat or not user:
        return False
    if str(getattr(chat, "type", "")).lower() != "private":
        return False
    return bool(is_owner(str(getattr(user, "id", ""))))


def _is_capture_message(message) -> bool:
    if not _is_owner_private(message):
        return False
    text = _message_text(message)
    # Commands must continue to the normal handlers (including /md_stop).
    if not text or text.lstrip().startswith("/"):
        return False
    try:
        return bool(_load_buffer(message.from_user.id).get("active"))
    except ValueError:
        return False


def _append_message(data: dict, *, text: str, kind: str, timestamp=None, message_id=None) -> str | None:
    if not isinstance(text, str) or not text:
        return "EMPTY_MESSAGE"
    text = _redact_secrets(text)
    if len(text) > MAX_MESSAGE_CHARS:
        return "MESSAGE_TOO_LONG"
    messages = data.setdefault("messages", [])
    if len(messages) >= MAX_MESSAGES:
        data["active"] = False
        return "BUFFER_MESSAGE_LIMIT"
    total = sum(len(str(item.get("text", ""))) for item in messages if isinstance(item, dict))
    if total + len(text) > MAX_BUFFER_CHARS:
        data["active"] = False
        return "BUFFER_SIZE_LIMIT"
    stamp = timestamp or time.time()
    messages.append({
        "t": float(stamp),
        "kind": str(kind or "text"),
        "text": text,
        "message_id": int(message_id or 0),
    })
    return None


def _format_timestamp(value) -> str:
    try:
        return datetime.fromtimestamp(float(value), timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError, OverflowError, OSError):
        return "unknown time"


def _code_fence(text: str) -> str:
    tick = chr(96)
    runs = [len(match.group(0)) for match in re.finditer(tick + r"+", text)]
    return tick * max(3, (max(runs) + 1) if runs else 3)


def render_markdown(messages, *, title="SLH MD Collection") -> str:
    lines = [
        "# " + title,
        "",
        "Messages: %d" % len(messages),
        "Generated UTC: " + datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "",
        "---",
        "",
    ]
    for index, item in enumerate(messages, 1):
        stamp = _format_timestamp(item.get("t"))
        kind = str(item.get("kind") or "text")
        text = _redact_secrets(str(item.get("text") or ""))
        lines.extend(["## %d. %s" % (index, stamp), ""])
        if kind in {"code", "inline-code"}:
            fence = _code_fence(text)
            info = "python" if kind == "code" else ""
            lines.extend([fence + info, text, fence, ""])
        else:
            lines.extend([text, ""])
    return "\n".join(lines).rstrip() + "\n"


def _send_markdown(bot, chat_id, messages, *, title, filename):
    body = render_markdown(messages, title=title)
    document = BytesIO(body.encode("utf-8"))
    document.name = filename
    bot.send_document(
        chat_id,
        document,
        caption="📄 %d הודעות · קובץ Markdown" % len(messages),
        visible_file_name=filename,
    )


def register(bot):
    # Register this first in handlers/loader.py, before conversational catch-alls.
    # It only matches owner-private, non-command text while collection is active.
    @bot.message_handler(func=_is_capture_message, content_types=CAPTURE_CONTENT_TYPES)
    def capture_message(message):
        text = _message_text(message)
        if text is None:
            return ContinueHandling()
        try:
            data = _load_buffer(message.from_user.id)
            if data.get("active"):
                err = _append_message(
                    data,
                    text=text,
                    kind=_message_kind(message),
                    timestamp=getattr(message, "date", None),
                    message_id=getattr(message, "message_id", None),
                )
                if err in {"BUFFER_MESSAGE_LIMIT", "BUFFER_SIZE_LIMIT"}:
                    _save_buffer(message.from_user.id, data)
                    bot.reply_to(message, "⚠️ הבאפר הגיע למגבלה; האיסוף נעצר. התוכן הקיים נשמר. ייצא עם /md_stop.")
                elif err == "MESSAGE_TOO_LONG":
                    bot.reply_to(message, "⚠️ ההודעה ארוכה מדי ולא נאספה. מגבלת הודעה: %d תווים." % MAX_MESSAGE_CHARS)
                elif not err:
                    _save_buffer(message.from_user.id, data)
        except Exception as exc:
            print("[MD_COLLECTOR] capture failed:", type(exc).__name__)
            try:
                bot.reply_to(message, "⚠️ שמירת ההודעה נכשלה; בדוק עם /md_status.")
            except Exception:
                pass
        # Do not consume the message: allow /ask, natural chat and other handlers
        # to process it after it has been copied into the owner's buffer.
        return ContinueHandling()

    def authorized(message) -> bool:
        if _is_owner_private(message):
            return True
        try:
            bot.reply_to(message, "⛔ הפקודה זמינה לבעלים בלבד, בשיחה פרטית עם הבוט.")
        except Exception:
            pass
        return False

    @bot.message_handler(commands=["md"])
    def md_help(message):
        if not authorized(message):
            return
        bot.reply_to(
            message,
            "📝 MD Collector — אוסף ידני\n\n"
            "/md_start — התחלת איסוף הודעות חדשות\n"
            "/md_stop — עצירת האיסוף וייצוא לקובץ .md\n"
            "/md_add — הוסף הודעה קיימת (בתשובה/Reply אליה)\n"
            "/md_last [N] — ייצוא N הודעות אחרונות שנאספו (ברירת מחדל 10)\n"
            "/md_status — מצב ומספר הודעות\n"
            "/md_cancel — עצירת האיסוף בלי לייצא\n"
            "/md_clear — מחיקת הבאפר\n\n"
            "נאספות רק הודעות שתשלח אחרי /md_start. הבוט אינו קורא היסטוריה ישנה אוטומטית. "
            "יש סינון אוטומטי חלקי בלבד. לעולם אל תשלח מפתחות פרטיים, seed phrases או API tokens. הבאפר נשמר בקובץ תחת state/."
        )

    @bot.message_handler(commands=["md_start"])
    def md_start(message):
        if not authorized(message):
            return
        try:
            data = _load_buffer(message.from_user.id)
            if data.get("active"):
                bot.reply_to(message, "🟢 האיסוף כבר פעיל. הודעות שנאספו: %d. סיום: /md_stop" % len(data["messages"]))
                return
            data["active"] = True
            if not data.get("started_at"):
                data["started_at"] = datetime.now(timezone.utc).isoformat()
            data["last_started_at"] = datetime.now(timezone.utc).isoformat()
            _save_buffer(message.from_user.id, data)
            bot.reply_to(
                message,
                "🟢 MD Collector פעיל. הודעות טקסט/קוד שתשלח מעכשיו ייאספו.\n"
                "סיום וייצוא: /md_stop · עצירה בלי ייצוא: /md_cancel · הוספת הודעה קיימת: Reply + /md_add\n"
                "יש סינון אוטומטי חלקי בלבד — לעולם אל תשלח מפתחות פרטיים, seed phrases או API tokens."
            )
        except Exception as exc:
            print("[MD_COLLECTOR] start failed:", type(exc).__name__)
            bot.reply_to(message, "⛔ לא הצלחתי להפעיל את האיסוף.")

    @bot.message_handler(commands=["md_stop"])
    def md_stop(message):
        if not authorized(message):
            return
        try:
            data = _load_buffer(message.from_user.id)
            data["active"] = False
            _save_buffer(message.from_user.id, data)
            messages = data.get("messages") or []
            if not messages:
                bot.reply_to(message, "⏹ האיסוף נעצר; אין הודעות לייצוא. ניתן להתחיל שוב עם /md_start.")
                return
            _send_markdown(
                bot,
                message.chat.id,
                messages,
                title="SLH MD Collection",
                filename="slh_md_collection.md",
            )
        except Exception as exc:
            print("[MD_COLLECTOR] stop/export failed:", type(exc).__name__)
            bot.reply_to(message, "⛔ הייצוא נכשל. הבאפר נשמר; נסה /md_last.")

    @bot.message_handler(commands=["md_add"])
    def md_add(message):
        if not authorized(message):
            return
        source = getattr(message, "reply_to_message", None)
        text = _message_text(source) if source is not None else None
        if not text:
            bot.reply_to(message, "השב (Reply) להודעה שברצונך לשמור ואז שלח /md_add.")
            return
        try:
            data = _load_buffer(message.from_user.id)
            err = _append_message(
                data,
                text=text,
                kind=_message_kind(source),
                timestamp=getattr(source, "date", None),
                message_id=getattr(source, "message_id", None),
            )
            if err:
                bot.reply_to(message, "⛔ לא נוספה ההודעה: %s. הבאפר נשמר ללא שינוי." % err)
                return
            _save_buffer(message.from_user.id, data)
            bot.reply_to(message, "✅ נוספה ההודעה לבאפר. סך הכול: %d. לייצוא: /md_last" % len(data["messages"]))
        except Exception as exc:
            print("[MD_COLLECTOR] add failed:", type(exc).__name__)
            bot.reply_to(message, "⛔ לא הצלחתי להוסיף את ההודעה.")

    @bot.message_handler(commands=["md_last"])
    def md_last(message):
        if not authorized(message):
            return
        parts = (getattr(message, "text", None) or "").split(maxsplit=1)
        try:
            count = int(parts[1]) if len(parts) > 1 else 10
        except ValueError:
            bot.reply_to(message, "שימוש: /md_last [N]")
            return
        count = max(1, min(count, MAX_LAST))
        try:
            messages = (_load_buffer(message.from_user.id).get("messages") or [])[-count:]
            if not messages:
                bot.reply_to(message, "📭 הבאפר ריק. התחל עם /md_start או השב להודעה עם /md_add.")
                return
            _send_markdown(
                bot,
                message.chat.id,
                messages,
                title="SLH MD — Last %d" % len(messages),
                filename="slh_md_last_%d.md" % len(messages),
            )
        except Exception as exc:
            print("[MD_COLLECTOR] last failed:", type(exc).__name__)
            bot.reply_to(message, "⛔ לא הצלחתי לייצא את הבאפר.")

    @bot.message_handler(commands=["md_status"])
    def md_status(message):
        if not authorized(message):
            return
        try:
            data = _load_buffer(message.from_user.id)
            size = sum(len(str(item.get("text", ""))) for item in data["messages"] if isinstance(item, dict))
            bot.reply_to(
                message,
                "MD Collector: %s\nהודעות: %d/%d\nתווים: %d/%d\nהתחלה: %s\n"
                % (
                    "ACTIVE" if data.get("active") else "STOPPED",
                    len(data["messages"]),
                    MAX_MESSAGES,
                    size,
                    MAX_BUFFER_CHARS,
                    data.get("started_at") or "—",
                ),
            )
        except Exception as exc:
            print("[MD_COLLECTOR] status failed:", type(exc).__name__)
            bot.reply_to(message, "⛔ לא הצלחתי לקרוא את מצב הבאפר.")

    @bot.message_handler(commands=["md_cancel"])
    def md_cancel(message):
        if not authorized(message):
            return
        try:
            data = _load_buffer(message.from_user.id)
            data["active"] = False
            _save_buffer(message.from_user.id, data)
            bot.reply_to(
                message,
                "⏹ האיסוף נעצר ללא ייצוא. נשמרו %d הודעות. למחיקה מלאה: /md_clear."
                % len(data["messages"]),
            )
        except Exception as exc:
            print("[MD_COLLECTOR] cancel failed:", type(exc).__name__)
            bot.reply_to(message, "⛔ לא הצלחתי לעצור את האיסוף.")

    @bot.message_handler(commands=["md_clear"])
    def md_clear(message):
        if not authorized(message):
            return
        try:
            _save_buffer(message.from_user.id, _empty_buffer())
            bot.reply_to(message, "🧹 הבאפר נוקה. לא בוצע שינוי ב־Ledger או ביתרות.")
        except Exception as exc:
            print("[MD_COLLECTOR] clear failed:", type(exc).__name__)
            bot.reply_to(message, "⛔ ניקוי הבאפר נכשל.")
