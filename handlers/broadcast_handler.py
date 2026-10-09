import time

import state_manager
from core.identity import OWNER_TELEGRAM_ID


BROADCAST_RATE_PER_SECOND = 25
BROADCAST_MIN_INTERVAL = 1.0 / BROADCAST_RATE_PER_SECOND
BROADCAST_MAX_RETRY_AFTER = 60.0


def _retry_after_seconds(exc):
    """Return Telegram's retry_after value when the exception exposes it."""
    value = getattr(exc, "retry_after", None)
    if value is not None:
        try:
            return max(0.0, min(float(value), BROADCAST_MAX_RETRY_AFTER))
        except (TypeError, ValueError):
            pass

    payload = getattr(exc, "result_json", None)
    if isinstance(payload, dict):
        parameters = payload.get("parameters")
        if isinstance(parameters, dict):
            value = parameters.get("retry_after")
            if value is not None:
                try:
                    return max(0.0, min(float(value), BROADCAST_MAX_RETRY_AFTER))
                except (TypeError, ValueError):
                    pass

    return None


def _send_one(bot, uid, message_text, next_allowed_at):
    """Send one message while enforcing the global broadcast pacing."""
    delay = next_allowed_at - time.monotonic()
    if delay > 0:
        time.sleep(delay)

    attempts = 0
    while True:
        try:
            bot.send_message(uid, message_text)
            return True, time.monotonic() + BROADCAST_MIN_INTERVAL

        except Exception as exc:
            retry_after = _retry_after_seconds(exc)
            if retry_after is None or attempts >= 1:
                return False, time.monotonic()

            attempts += 1
            time.sleep(retry_after)


def _is_exchange_status_announcement(text):
    value = str(text or "").lower()
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip()
    # Deliberately broad: status/market claims cannot use the generic route.
    protected_terms = (
        "exchange",
        "מסחר",
        "בורסה",
        "trading gate",
        "internal exchange",
        "slh exchange",
    )
    return any(term in value for term in protected_terms)


def register(bot):
    @bot.message_handler(commands=["broadcast"])
    def broadcast_cmd(m):
        if int(m.from_user.id) != int(OWNER_TELEGRAM_ID):
            bot.reply_to(m, "⛔ OWNER only")
            return

        parts = (m.text or "").split(maxsplit=1)
        subcommand = parts[1].strip().lower() if len(parts) >= 2 else ""
        if subcommand in {"status", "--status"}:
            bot.reply_to(m, _broadcast_status_reply(str(m.from_user.id)))
            return
        if subcommand in {"help", "--help"}:
            bot.reply_to(
                m,
                "ℹ️ /broadcast status — בדיקה לקריאה בלבד; אינה שולחת הודעה.\\n"
                "/broadcast <text> — שידור כללי להודעות ניטרליות בלבד.\\n"
                "להודעת מצב מסחר פנימי: אמור בפרטי ״הכן ברודקאסט למסחר פנימי״; "
                "תישלח רק אחרי תצוגה מקדימה ואישור קולי נפרד ובדיקת Exchange רעננה.",
            )
            return
        if len(parts) >= 2 and _is_exchange_status_announcement(parts[1]):
            bot.reply_to(
                m,
                "⛔ הודעות על מצב Exchange/מסחר פנימי חסומות ב־/broadcast הכללי. "
                "השתמש במסלול הקולי המאובטח: ״הכן ברודקאסט למסחר פנימי״, "
                "ואחרי סקירת ההודעה אמור ״אשר ושלח ברודקאסט למסחר פנימי״. "
                "לפני שליחה תתבצע בדיקת Exchange קנונית ורעננה.",
            )
            return

        parts = (m.text or "").split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /broadcast <text>")
            return

        message_text = parts[1].strip()

        try:
            db = state_manager.load_db()
        except Exception as e:
            bot.reply_to(m, f"DB error: {type(e).__name__}")
            return

        users = db.get("users", {})
        if not isinstance(users, dict):
            bot.reply_to(m, "DB error: users registry is invalid")
            return

        sent = 0
        failed = 0
        next_allowed_at = time.monotonic()

        for uid in users.keys():
            ok, next_allowed_at = _send_one(
                bot,
                uid,
                message_text,
                next_allowed_at,
            )
            if ok:
                sent += 1
            else:
                failed += 1

        bot.reply_to(
            m,
            f"✅ Broadcast sent to {sent} users.\n"
            f"Failed: {failed}"
        )


# Exchange-status announcements are deliberately separate from generic /broadcast.
# The exact body is fixed in code so a voice transcript or LLM cannot invent a
# financial/product claim. It is sent only after a second, explicit voice confirm.
from datetime import datetime, timedelta, timezone
import hashlib
import re
import uuid


EXCHANGE_BROADCAST_TEXT = """🟢 SLH OS — המסחר הפנימי פתוח

הבורסה הפנימית של SLH OS זמינה למסחר.

📊 ניתן להיכנס ל־Mini App:
🚀 SLH OS → 🪙 Exchange

אפשר לראות:
• Order Book אמיתי
• פקודות Buy / Sell
• עסקאות שבוצעו
• יתרות ומצב הפקודה

⚠️ מדובר במסחר הפנימי של SLH OS.
זה אינו DEX חיצוני ואינו IDO / Presale.

🚀 https://slh-cloud-bot-production.up.railway.app/mini-app-v4"""

EXCHANGE_BROADCAST_TTL_SECONDS = 300
EXCHANGE_BROADCAST_CHECK_INTERVAL = 25
EXCHANGE_BROADCAST_AUDIT_LIMIT = 100

_PREPARE_VOICE_PHRASES = {
    "הכן ברודקאסט למסחר פנימי",
    "תכין ברודקאסט למסחר פנימי",
    "הכן הודעת ברודקאסט למסחר פנימי",
    "תכין הודעת ברודקאסט למסחר פנימי",
}
_CONFIRM_VOICE_PHRASES = {
    "אשר ושלח ברודקאסט למסחר פנימי",
    "מאשר ושלח ברודקאסט למסחר פנימי",
    "אשר ושלח את הברודקאסט למסחר פנימי",
    "אני מאשר לשלוח את הברודקאסט למסחר פנימי",
    "אני מאשר שלח ברודקאסט למסחר פנימי",
}


def _utc_now(value=None):
    if value is None:
        value = datetime.now(timezone.utc)
    elif isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        raise TypeError("BROADCAST_TIME_INVALID")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _utc_text(value=None):
    return _utc_now(value).isoformat()


def _normalize_voice_phrase(value):
    value = str(value or "").lower()
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def _proof_is_green(check):
    return (
        isinstance(check, dict)
        and check.get("execution_ready") is True
        and check.get("public_gate") == "OPEN"
        and check.get("verdict") == "OPEN"
        and check.get("public_ready") is True
        and check.get("order_book_integrity") is True
        and check.get("trade_integrity") is True
        and check.get("money_invariants") is True
    )


def _fresh_exchange_check(db):
    try:
        from core.system_checks import check_exchange_for_execution
        result = check_exchange_for_execution(db)
        return result if isinstance(result, dict) else {
            "execution_ready": False,
            "public_gate": "CLOSED",
            "verdict": "BLOCKED",
            "detail": "invalid exchange check result",
        }
    except Exception as exc:
        return {
            "execution_ready": False,
            "public_gate": "CLOSED",
            "verdict": "BLOCKED",
            "detail": f"exchange check failed: {type(exc).__name__}",
        }


def _proof_snapshot(check, checked_at=None):
    fields = (
        "public_gate",
        "verdict",
        "execution_ready",
        "public_ready",
        "order_book_integrity",
        "trade_integrity",
        "money_invariants",
    )
    snapshot = {key: check.get(key) for key in fields} if isinstance(check, dict) else {}
    snapshot["status"] = "PASS" if _proof_is_green(check) else "BLOCKED"
    snapshot["checked_at"] = checked_at or _utc_text()
    snapshot["detail"] = str((check or {}).get("detail") or "No detail")[:300] if isinstance(check, dict) else "invalid check"
    return snapshot


def _append_exchange_broadcast_audit(db, record, status, *, sent=0, failed=0, detail="", check=None, now=None):
    audit = db.setdefault("exchange_broadcast_audit", [])
    if not isinstance(audit, list):
        audit = []
        db["exchange_broadcast_audit"] = audit
    draft_id = str(record.get("draft_id") or "")
    if any(isinstance(item, dict) and item.get("draft_id") == draft_id for item in audit):
        return
    audit.append({
        "draft_id": draft_id,
        "initiated_by": str(record.get("uid") or ""),
        "status": status,
        "created_at": record.get("created_at"),
        "finished_at": _utc_text(now),
        "target_count": int(record.get("target_count") or 0),
        "sent": int(sent),
        "failed": int(failed),
        "detail": str(detail or "")[:300],
        "fresh_exchange_check": check or record.get("pre_send_check") or record.get("claim_check"),
        "message_sha256": hashlib.sha256(EXCHANGE_BROADCAST_TEXT.encode("utf-8")).hexdigest(),
    })
    del audit[:-EXCHANGE_BROADCAST_AUDIT_LIMIT]


def prepare_exchange_broadcast(uid, *, now=None):
    """Create an expiring preview; never contacts recipients."""
    uid = str(uid or "").strip()
    if uid != str(OWNER_TELEGRAM_ID):
        return {"status": "FORBIDDEN", "detail": "OWNER only"}
    current = _utc_now(now)
    created_at = current.isoformat()
    expires_at = (current + timedelta(seconds=EXCHANGE_BROADCAST_TTL_SECONDS)).isoformat()
    draft_id = uuid.uuid4().hex

    def mutate(db):
        pending_map = db.setdefault("exchange_broadcast_pending", {})
        if not isinstance(pending_map, dict):
            pending_map = {}
            db["exchange_broadcast_pending"] = pending_map
        previous = pending_map.get(uid)
        if isinstance(previous, dict) and previous.get("status") == "SENDING":
            return {"status": "IN_PROGRESS", "detail": "A confirmed broadcast is already sending"}
        record = {
            "draft_id": draft_id,
            "uid": uid,
            "status": "PENDING_CONFIRMATION",
            "created_at": created_at,
            "expires_at": expires_at,
            "target_count": 0,
            "message_sha256": hashlib.sha256(EXCHANGE_BROADCAST_TEXT.encode("utf-8")).hexdigest(),
        }
        pending_map[uid] = record
        return {"status": "PREPARED", "draft_id": draft_id, "expires_at": expires_at}

    return state_manager.atomic_update(mutate)


def _terminal_state(uid, draft_id, status, *, sent=0, failed=0, detail="", check=None, now=None):
    finished_at = _utc_text(now)

    def mutate(db):
        pending_map = db.setdefault("exchange_broadcast_pending", {})
        record = pending_map.get(str(uid)) if isinstance(pending_map, dict) else None
        if isinstance(record, dict) and record.get("draft_id") == draft_id:
            record.update({
                "status": status,
                "finished_at": finished_at,
                "sent": int(sent),
                "failed": int(failed),
                "detail": str(detail or "")[:300],
            })
            if check is not None:
                record["last_exchange_check"] = check
            _append_exchange_broadcast_audit(
                db, record, status, sent=sent, failed=failed, detail=detail, check=check, now=now
            )
        target_count = int(record.get("target_count") or 0) if isinstance(record, dict) else 0
        return {
            "status": status,
            "draft_id": draft_id,
            "target_count": target_count,
            "sent": int(sent),
            "failed": int(failed),
            "detail": str(detail or "")[:300],
        }

    return state_manager.atomic_update(mutate)


def send_confirmed_exchange_broadcast(bot, uid, *, now=None):
    """Claim one voice-confirmed draft, re-check the live exchange, then send.

    The claim is atomic and single-use. Exchange readiness is checked against
    the canonical db snapshot at claim time, checked again immediately before
    the first recipient, and refreshed every 25 recipients during long runs.
    """
    uid = str(uid or "").strip()
    if uid != str(OWNER_TELEGRAM_ID):
        return {"status": "FORBIDDEN", "detail": "OWNER only"}
    current = _utc_now(now)
    current_text = current.isoformat()

    def claim(db):
        pending_map = db.setdefault("exchange_broadcast_pending", {})
        record = pending_map.get(uid) if isinstance(pending_map, dict) else None
        if not isinstance(record, dict):
            return {"status": "NOT_PENDING", "detail": "No prepared broadcast"}
        if record.get("status") != "PENDING_CONFIRMATION":
            return {"status": "ALREADY_HANDLED", "detail": "This draft is no longer pending"}
        try:
            expires_at = _utc_now(record.get("expires_at"))
        except Exception:
            expires_at = current - timedelta(seconds=1)
        if current >= expires_at:
            record["status"] = "EXPIRED"
            record["finished_at"] = current_text
            _append_exchange_broadcast_audit(db, record, "EXPIRED", detail="Confirmation window expired", now=current)
            return {"status": "EXPIRED", "detail": "The preview expired; prepare a new one"}

        check = _fresh_exchange_check(db)
        proof = _proof_snapshot(check, checked_at=current_text)
        if not _proof_is_green(check):
            record.update({"status": "BLOCKED", "finished_at": current_text, "claim_check": proof})
            _append_exchange_broadcast_audit(
                db, record, "BLOCKED", detail=proof["detail"], check=proof, now=current
            )
            return {"status": "BLOCKED", "detail": proof["detail"], "check": proof, "sent": 0}

        users = db.get("users", {})
        if not isinstance(users, dict):
            record.update({"status": "BLOCKED", "finished_at": current_text})
            _append_exchange_broadcast_audit(db, record, "BLOCKED", detail="Invalid users registry", check=proof, now=current)
            return {"status": "BLOCKED", "detail": "Invalid users registry", "sent": 0}

        audience = sorted({str(key) for key in users if str(key).isdigit() and int(key) > 0})
        if not audience:
            record.update({"status": "BLOCKED", "finished_at": current_text})
            _append_exchange_broadcast_audit(db, record, "BLOCKED", detail="Empty recipient set", check=proof, now=current)
            return {"status": "BLOCKED", "detail": "No eligible Telegram users found", "sent": 0}

        record.update({
            "status": "SENDING",
            "confirmed_at": current_text,
            "claimed_at": current_text,
            "target_count": len(audience),
            "claim_check": proof,
        })
        return {
            "status": "CLAIMED",
            "draft_id": record["draft_id"],
            "audience": audience,
            "target_count": len(audience),
            "claim_check": proof,
        }

    claim_result = state_manager.atomic_update(claim)
    if claim_result.get("status") != "CLAIMED":
        return claim_result

    draft_id = claim_result["draft_id"]
    audience = claim_result["audience"]
    target_count = int(claim_result["target_count"])

    # This is the decisive send-time check, after the one-shot claim and just
    # before any network send. A blocked/failed check sends to nobody.
    try:
        live_db = state_manager.load_db()
        live_check = _fresh_exchange_check(live_db)
    except Exception as exc:
        live_check = {
            "execution_ready": False,
            "public_gate": "CLOSED",
            "verdict": "BLOCKED",
            "detail": f"live state unreadable: {type(exc).__name__}",
        }
    proof = _proof_snapshot(live_check, checked_at=_utc_text(now))
    if not _proof_is_green(live_check):
        return _terminal_state(
            uid, draft_id, "BLOCKED", detail=proof["detail"], check=proof, now=now
        )

    def store_pre_send(db):
        pending_map = db.setdefault("exchange_broadcast_pending", {})
        record = pending_map.get(uid) if isinstance(pending_map, dict) else None
        if isinstance(record, dict) and record.get("draft_id") == draft_id and record.get("status") == "SENDING":
            record["pre_send_check"] = proof
        return True

    state_manager.atomic_update(store_pre_send)

    sent = 0
    failed = 0
    next_allowed_at = time.monotonic()
    latest_check = proof

    for index, recipient in enumerate(audience):
        if index > 0 and index % EXCHANGE_BROADCAST_CHECK_INTERVAL == 0:
            try:
                live_db = state_manager.load_db()
                live_check = _fresh_exchange_check(live_db)
            except Exception as exc:
                live_check = {
                    "execution_ready": False,
                    "public_gate": "CLOSED",
                    "verdict": "BLOCKED",
                    "detail": f"live state unreadable: {type(exc).__name__}",
                }
            latest_check = _proof_snapshot(live_check)
            if not _proof_is_green(live_check):
                return _terminal_state(
                    uid, draft_id, "STOPPED_GATE_CLOSED", sent=sent, failed=failed,
                    detail=f"Exchange gate re-check blocked: {latest_check['detail']}",
                    check=latest_check,
                )

        try:
            ok, next_allowed_at = _send_one(bot, recipient, EXCHANGE_BROADCAST_TEXT, next_allowed_at)
        except Exception:
            ok, next_allowed_at = False, time.monotonic()
        if ok:
            sent += 1
        else:
            failed += 1

    status = "SENT" if sent == target_count and failed == 0 else "PARTIAL"
    detail = "All recipients sent" if status == "SENT" else "Some recipients could not be reached"
    return _terminal_state(
        uid, draft_id, status, sent=sent, failed=failed, detail=detail,
        check=latest_check,
    )


def _exchange_broadcast_reply(result):
    status = str((result or {}).get("status") or "BLOCKED")
    if status == "SENT":
        return f"✅ ברודקאסט המסחר הפנימי נשלח ל־{result.get('sent', 0)} משתמשים. בדיקת Exchange רעננה עברה לפני השליחה."
    if status == "PARTIAL":
        return f"🟡 ברודקאסט חלקי: נשלחו {result.get('sent', 0)}; נכשלו {result.get('failed', 0)}. בדיקת Exchange נרשמה."
    if status == "STOPPED_GATE_CLOSED":
        return f"⛔ נעצר באמצע כי בדיקת Exchange כבר לא ירוקה. נשלחו {result.get('sent', 0)} מתוך {result.get('target_count', 'היעד')}. לא נשלחו הודעות נוספות."
    if status == "BLOCKED":
        return f"⛔ לא נשלח ברודקאסט: Fresh Exchange check חסם את השליחה. {result.get('detail', '')}"
    if status == "EXPIRED":
        return "⌛ פג תוקף האישור. הכן תצוגה חדשה ואז אשר בנפרד."
    if status == "FORBIDDEN":
        return "⛔ הפעולה זמינה לבעלים בלבד."
    if status == "IN_PROGRESS":
        return "⏳ כבר מתבצעת שליחה מאושרת; לא נוצרה שליחה נוספת."
    if status in {"ALREADY_HANDLED", "NOT_PENDING"}:
        return "⛔ אין טיוטה מאושרת לשליחה. הכן קודם ברודקאסט חדש."
    return f"⛔ הברודקאסט לא נשלח: {result.get('detail', status)}"


def _is_exchange_broadcast_query(phrase):
    """Recognize questions about the Exchange broadcast without treating them as consent."""
    broadcast_terms = ("ברודקאסט", "broadcast", "הודעת שידור")
    exchange_terms = ("מסחר", "בורסה", "exchange", "trading")
    return any(term in phrase for term in broadcast_terms) and any(term in phrase for term in exchange_terms)


def _exchange_broadcast_status_answer(message, *, now=None):
    """Return a read-only canonical readiness answer; never prepare or send."""
    uid = str(getattr(getattr(message, "from_user", None), "id", "") or "")
    if uid != str(OWNER_TELEGRAM_ID):
        return "⛔ בדיקת מוכנות לברודקאסט מסחר פנימי זמינה רק ל־OWNER."
    if str(getattr(getattr(message, "chat", None), "type", "")).lower() != "private":
        return "⛔ בדיקת ברודקאסט מסחר פנימי זמינה רק בשיחה הפרטית עם הבוט."

    try:
        db = state_manager.load_db()
        check = _fresh_exchange_check(db)
    except Exception as exc:
        check = {
            "execution_ready": False,
            "public_gate": "CLOSED",
            "verdict": "BLOCKED",
            "detail": f"live state unavailable: {type(exc).__name__}",
        }
    proof = _proof_snapshot(check, checked_at=_utc_text(now))
    ready = _proof_is_green(check)
    gate = "OPEN" if ready else "CLOSED/BLOCKED"
    next_step = (
        "אם תרצה להתחיל, אמור: ״הכן ברודקאסט למסחר פנימי״. זה יפתח תצוגה מקדימה בלבד; "
        "שליחה תדרוש אישור קולי נפרד ובדיקת Exchange רעננה נוספת."
        if ready
        else "לא לשדר הודעת ״המסחר הפנימי פתוח״ עד שכל בדיקות ה־Exchange יהיו OPEN/PASS."
    )
    return (
        "🔎 מוכנות ברודקאסט למסחר פנימי — READ ONLY\\n\\n"
        f"Fresh canonical Exchange check: {gate} · {proof['status']}\\n"
        f"פרטים: {proof['detail']}\\n\\n"
        "לא נשלחה הודעה ולא נוצרה טיוטה.\\n"
        f"{next_step}"
    )


def _broadcast_status_reply(uid):
    """Read-only status for /broadcast status; never accesses send APIs."""
    try:
        db = state_manager.load_db()
    except Exception as exc:
        return f"⛔ BROADCAST STATUS unavailable (read-only): {type(exc).__name__}"

    check = _fresh_exchange_check(db)
    proof = _proof_snapshot(check)
    gate = "OPEN" if _proof_is_green(check) else "CLOSED/BLOCKED"

    pending_map = db.get("exchange_broadcast_pending", {})
    pending = pending_map.get(str(uid)) if isinstance(pending_map, dict) else None
    pending_status = str(pending.get("status") or "UNKNOWN") if isinstance(pending, dict) else "NONE"

    audit = db.get("exchange_broadcast_audit", [])
    relevant = [
        item for item in audit
        if isinstance(item, dict) and str(item.get("initiated_by") or "") == str(uid)
    ] if isinstance(audit, list) else []
    latest = relevant[-1] if relevant else None
    if latest:
        last_broadcast = (
            f"{latest.get('status', 'UNKNOWN')} · sent={latest.get('sent', 0)} "
            f"failed={latest.get('failed', 0)}"
        )
    else:
        last_broadcast = "אין שליחת Exchange מתועדת ביומן הקנוני."

    return (
        "🔎 BROADCAST STATUS — READ ONLY\\n"
        "הפקודה הזו לא שולחת הודעות.\\n"
        f"Internal Exchange: {gate} · {proof['status']}\\n"
        f"Exchange draft: {pending_status}\\n"
        f"Last audited Exchange broadcast: {last_broadcast}\\n"
        "להכנת הודעת מסחר: אמור בפרטי ״הכן ברודקאסט למסחר פנימי״; "
        "נדרשים תצוגה מקדימה ואישור קולי נפרד."
    )


def route_exchange_broadcast_voice(bot, message, transcript, *, now=None):
    """Strict owner/private allowlist for preparing or confirming the fixed notice."""
    phrase = _normalize_voice_phrase(transcript)
    is_prepare = phrase in {_normalize_voice_phrase(x) for x in _PREPARE_VOICE_PHRASES}
    is_confirm = phrase in {_normalize_voice_phrase(x) for x in _CONFIRM_VOICE_PHRASES}
    if not is_prepare and not is_confirm:
        if _is_exchange_broadcast_query(phrase):
            return _exchange_broadcast_status_answer(message, now=now)
        return None

    uid = str(getattr(getattr(message, "from_user", None), "id", "") or "")
    if uid != str(OWNER_TELEGRAM_ID):
        return "⛔ רק OWNER יכול להכין או לאשר ברודקאסט מסחר פנימי."
    if str(getattr(getattr(message, "chat", None), "type", "")).lower() != "private":
        return "⛔ ברודקאסט מסחר פנימי זמין רק בשיחה הפרטית עם הבוט."

    if is_prepare:
        result = prepare_exchange_broadcast(uid, now=now)
        if result.get("status") != "PREPARED":
            return _exchange_broadcast_reply(result)
        return (
            "🧾 תצוגה מקדימה בלבד — לא נשלחה הודעה לאף משתמש.\n"
            f"טיוטה בתוקף ל־{EXCHANGE_BROADCAST_TTL_SECONDS // 60} דקות.\n\n"
            f"{EXCHANGE_BROADCAST_TEXT}\n\n"
            "כדי לבצע שליחה אמיתית, אמור עכשיו במפורש: ״אשר ושלח ברודקאסט למסחר פנימי״. "
            "ברגע האישור תתבצע בדיקת Exchange קנונית רעננה; אם השער לא OPEN וכל האינווריאנטים לא PASS, לא תישלח הודעה."
        )

    result = send_confirmed_exchange_broadcast(bot, uid, now=now)
    return _exchange_broadcast_reply(result)
