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
                "ℹ️ /broadcast status — בדיקה לקריאה בלבד; אינה שולחת הודעה.\n"
                "/broadcast <text> — שידור כללי להודעות ניטרליות בלבד.\n"
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
    "הכן לי ברודקאסט למסחר פנימי",
    "תכין לי ברודקאסט למסחר פנימי",
    "הכן הודעת ברודקאסט למסחר פנימי",
    "תכין הודעת ברודקאסט למסחר פנימי",
    "הכן לי הודעת ברודקאסט למסחר פנימי",
    "תכין לי הודעת ברודקאסט למסחר פנימי",
}
_DUPLICATE_ACK_VOICE_PHRASES = {
    "אשר ושלח ברודקאסט מלא למרות כפילויות",
    "אני מאשר שליחה חוזרת לכל הקהל למרות כפילויות",
    "אני מאשר לשלוח שוב לכולם למרות שחלק כבר קיבלו",
}
_CONFIRM_VOICE_PHRASES = {
    "אשר ושלח ברודקאסט למסחר פנימי",
    "מאשר ושלח ברודקאסט למסחר פנימי",
    "מאשר לשלוח ברודקאסט למסחר פנימי",
    "מאשר לשלוח את הברודקאסט למסחר הפנימי",
    "אשר ושלח את הברודקאסט למסחר פנימי",
    "אני מאשר לשלוח את הברודקאסט למסחר פנימי",
    "אני מאשר שלח ברודקאסט למסחר פנימי",
    *_DUPLICATE_ACK_VOICE_PHRASES,
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
    # Hebrew STT commonly adds the definite article or a politeness filler.
    # Normalize only known intent words; sending still requires an explicit
    # confirmation phrase from the allowlist below.
    for article_form, bare_form in (
        ("הברודקאסט", "ברודקאסט"),
        ("הפנימי", "פנימי"),
        ("המסחר", "מסחר"),
        ("הבורסה", "בורסה"),
    ):
        value = value.replace(article_form, bare_form)
    value = re.sub(r"\bבבקשה\b", " ", value, flags=re.UNICODE)
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


def _broadcast_audience(db):
    """Return the stable, eligible numeric Telegram user IDs without exposing them."""
    users = db.get("users", {})
    if not isinstance(users, dict):
        return []
    return sorted({str(key) for key in users if str(key).isdigit() and int(key) > 0})


def _broadcast_audience_hash(audience):
    """Fingerprint the previewed audience without exposing IDs in user-facing output."""
    return hashlib.sha256("|".join(sorted(str(uid) for uid in audience)).encode("utf-8")).hexdigest()


def _trusted_utc_timestamp(value):
    """Parse only timezone-qualified timestamps; naive local/UTC guesses are unsafe."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError, OverflowError):
            return None
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    try:
        if value.utcoffset() is None:
            return None
        return value.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _user_created_at(user):
    """Return a trustworthy persisted creation timestamp, or None if it cannot be proven."""
    if not isinstance(user, dict):
        return None
    profile = user.get("profile")
    candidates = (
        user.get("joined"),
        user.get("joined_at"),
        user.get("created_at"),
        profile.get("created") if isinstance(profile, dict) else None,
        profile.get("created_at") if isinstance(profile, dict) else None,
    )
    for value in candidates:
        parsed = _trusted_utc_timestamp(value)
        if parsed is not None:
            return parsed
    return None


def _new_audience_since(db, cutoff_value):
    """Select only users demonstrably created after a prior delivery; fail closed on ambiguity."""
    cutoff = _trusted_utc_timestamp(cutoff_value)
    users = db.get("users") if isinstance(db, dict) else None
    if cutoff is None or not isinstance(users, dict):
        return None
    audience = []
    for raw_uid, user in users.items():
        uid = str(raw_uid)
        if not uid.isdigit() or int(uid) <= 0:
            continue
        created_at = _user_created_at(user)
        if created_at is not None and created_at > cutoff:
            audience.append(uid)
    return sorted(set(audience))


def _latest_exchange_broadcast_audit(db, uid):
    """Return the latest actual delivery outcome, not a blocked/expired draft audit."""
    audit = db.get("exchange_broadcast_audit", [])
    if not isinstance(audit, list):
        return None
    message_hash = hashlib.sha256(EXCHANGE_BROADCAST_TEXT.encode("utf-8")).hexdigest()
    relevant = []
    for item in audit:
        if (
            not isinstance(item, dict)
            or str(item.get("initiated_by") or "") != str(uid)
            or item.get("message_sha256") not in {"", None, message_hash}
        ):
            continue
        status = str(item.get("status") or "").upper()
        if status in {"SENT", "PARTIAL"}:
            relevant.append(item)
        elif status == "STOPPED_GATE_CLOSED":
            try:
                if int(item.get("sent") or 0) > 0:
                    relevant.append(item)
            except (TypeError, ValueError):
                # Treat an uncertain, possibly-partial delivery as a prior delivery.
                relevant.append(item)
    return relevant[-1] if relevant else None


def _audience_for_record(db, record):
    """Resolve exactly the previewed audience, including safe retry cohorts."""
    current_audience = _broadcast_audience(db)
    scope = str(record.get("audience_scope") or "all")
    if scope == "all":
        return current_audience
    if scope not in {"failed_only", "new_users_only"}:
        return None

    retry_id = str(record.get("retry_of_draft_id") or "")
    audit = db.get("exchange_broadcast_audit", [])
    if not isinstance(audit, list):
        return None
    previous = next((
        item for item in audit
        if isinstance(item, dict)
        and str(item.get("draft_id") or "") == retry_id
        and str(item.get("initiated_by") or "") == str(record.get("uid") or "")
    ), None)
    if (
        not isinstance(previous, dict)
        or previous.get("status") not in {"PARTIAL", "STOPPED_GATE_CLOSED"}
        or previous.get("message_sha256") != hashlib.sha256(EXCHANGE_BROADCAST_TEXT.encode("utf-8")).hexdigest()
    ):
        return None

    if scope == "new_users_only":
        # A timestamp-verified cohort is recomputed at confirmation time.
        return _new_audience_since(db, previous.get("finished_at"))

    failed_ids = previous.get("failed_recipient_uids")
    try:
        expected_failed = int(previous.get("failed") or 0)
    except (TypeError, ValueError):
        return None
    if (
        previous.get("status") != "PARTIAL"
        or not isinstance(failed_ids, list)
        or expected_failed != len(failed_ids)
        or len(set(str(value) for value in failed_ids)) != len(failed_ids)
        or any(not str(value).isdigit() or int(value) <= 0 for value in failed_ids)
    ):
        return None
    available = set(current_audience)
    return sorted({str(value) for value in failed_ids if str(value) in available})


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
        "audience_sha256": str(record.get("audience_sha256") or ""),
        "audience_scope": str(record.get("audience_scope") or "all"),
        "retry_of_draft_id": record.get("retry_of_draft_id"),
        "sent": int(sent),
        "failed": int(failed),
        "failed_recipient_uids": [
            str(value) for value in (record.get("failed_recipient_uids") or [])
            if str(value).isdigit() and int(value) > 0
        ],
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

        previous_audit = _latest_exchange_broadcast_audit(db, uid)
        all_audience = _broadcast_audience(db)
        audience = all_audience
        audience_scope = "all"
        retry_of_draft_id = None
        requires_duplicate_ack = False
        previous_sent = 0
        previous_failed = 0

        if isinstance(previous_audit, dict) and previous_audit.get("status") in {"PARTIAL", "STOPPED_GATE_CLOSED"}:
            if previous_audit.get("message_sha256") != hashlib.sha256(EXCHANGE_BROADCAST_TEXT.encode("utf-8")).hexdigest():
                return {
                    "status": "SAFE_RETRY_UNAVAILABLE",
                    "detail": "Historical delivery record does not prove it was this exact announcement; no retry draft was created",
                }
            try:
                previous_sent = int(previous_audit.get("sent") or 0)
                previous_failed = int(previous_audit.get("failed") or 0)
                previous_target = int(previous_audit.get("target_count") or 0)
            except (TypeError, ValueError):
                return {
                    "status": "SAFE_RETRY_UNAVAILABLE",
                    "detail": "Historical delivery counts are invalid; a full-audience retry is blocked",
                }

            previous_status = str(previous_audit.get("status") or "")
            prior_delivery = previous_sent > 0 or previous_status == "PARTIAL"
            if not prior_delivery:
                return {
                    "status": "SAFE_RETRY_UNAVAILABLE",
                    "detail": "A stopped or partial historical delivery cannot be reconciled safely",
                }

            failed_ids = previous_audit.get("failed_recipient_uids")
            valid_failed_ids = (
                previous_status == "PARTIAL"
                and previous_failed > 0
                and isinstance(failed_ids, list)
                and len(failed_ids) == previous_failed
                and len(set(str(value) for value in failed_ids)) == len(failed_ids)
                and all(str(value).isdigit() and int(value) > 0 for value in failed_ids)
                and previous_sent + previous_failed == previous_target
            )
            if valid_failed_ids:
                available = set(all_audience)
                audience = sorted({str(value) for value in failed_ids if str(value) in available})
                if not audience:
                    return {
                        "status": "NO_FAILED_RECIPIENTS",
                        "detail": "No recorded failed recipients remain eligible; no new draft was created",
                        "previous_failed": previous_failed,
                    }
                audience_scope = "failed_only"
                retry_of_draft_id = str(previous_audit.get("draft_id") or "")
            else:
                # Missing/inconsistent recipient-level evidence: never fall back to all users.
                # A new-user cohort requires timezone-qualified creation timestamps after
                # the last delivery finished; naive timestamps are not considered proof.
                audience = _new_audience_since(db, previous_audit.get("finished_at"))
                if audience is None:
                    return {
                        "status": "SAFE_RETRY_UNAVAILABLE",
                        "detail": "Cannot verify the prior delivery cutoff and user creation times; no draft was created",
                        "previous_sent": previous_sent,
                        "previous_failed": previous_failed,
                    }
                if not audience:
                    return {
                        "status": "NO_SAFE_NEW_RECIPIENTS",
                        "detail": "No users can be proven to have joined after the prior delivery; no draft was created",
                        "previous_sent": previous_sent,
                        "previous_failed": previous_failed,
                    }
                audience_scope = "new_users_only"
                retry_of_draft_id = str(previous_audit.get("draft_id") or "")

        audience_sha256 = _broadcast_audience_hash(audience)
        record = {
            "draft_id": draft_id,
            "uid": uid,
            "status": "PENDING_CONFIRMATION",
            "created_at": created_at,
            "expires_at": expires_at,
            "target_count": len(audience),
            "audience_sha256": audience_sha256,
            "message_sha256": hashlib.sha256(EXCHANGE_BROADCAST_TEXT.encode("utf-8")).hexdigest(),
            "audience_scope": audience_scope,
            "retry_of_draft_id": retry_of_draft_id,
            "requires_duplicate_ack": requires_duplicate_ack,
            "previous_sent": previous_sent,
            "previous_failed": previous_failed,
            "failed_recipient_uids": [],
        }
        pending_map[uid] = record
        return {
            "status": "PREPARED",
            "draft_id": draft_id,
            "expires_at": expires_at,
            "target_count": len(audience),
            "audience_scope": audience_scope,
            "retry_of_draft_id": retry_of_draft_id,
            "requires_duplicate_ack": requires_duplicate_ack,
            "previous_sent": previous_sent,
            "previous_failed": previous_failed,
        }

    return state_manager.atomic_update(mutate)


def _terminal_state(uid, draft_id, status, *, sent=0, failed=0, failed_recipient_uids=None, detail="", check=None, now=None):
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
                "failed_recipient_uids": [
                    str(value) for value in (failed_recipient_uids or [])
                    if str(value).isdigit() and int(value) > 0
                ],
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
            "previous_sent": int(record.get("previous_sent") or 0) if isinstance(record, dict) else 0,
            "previous_failed": int(record.get("previous_failed") or 0) if isinstance(record, dict) else 0,
        }

    return state_manager.atomic_update(mutate)



def send_confirmed_exchange_broadcast(bot, uid, *, now=None, duplicate_acknowledged=False):
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
        # Legacy drafts that offered a full repeat with duplicate acknowledgement are unsafe.
        # Never let the old confirmation phrase bypass the new recipient-safety policy.
        if record.get("requires_duplicate_ack") is True:
            return {
                "status": "SAFE_RETRY_REQUIRED",
                "detail": "Legacy full-audience retry disabled; prepare a safe failed-only or verified-new-user preview",
                "previous_sent": int(record.get("previous_sent") or 0),
                "previous_failed": int(record.get("previous_failed") or 0),
            }
        latest_delivery = _latest_exchange_broadcast_audit(db, uid)
        if isinstance(latest_delivery, dict) and latest_delivery.get("status") in {"PARTIAL", "STOPPED_GATE_CLOSED"}:
            safe_scope = str(record.get("audience_scope") or "all") in {"failed_only", "new_users_only"}
            retry_matches = str(record.get("retry_of_draft_id") or "") == str(latest_delivery.get("draft_id") or "")
            if not (safe_scope and retry_matches):
                return {
                    "status": "SAFE_RETRY_REQUIRED",
                    "detail": "Historical partial delivery requires a verified safe-recipient preview; full-audience confirmation is blocked",
                    "previous_sent": int(latest_delivery.get("sent") or 0),
                    "previous_failed": int(latest_delivery.get("failed") or 0),
                }
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

        audience = _audience_for_record(db, record)
        if audience is None:
            detail = "Retry audit no longer proves the original failed-recipient set"
            record.update({"status": "RECIPIENTS_CHANGED", "finished_at": current_text, "detail": detail})
            _append_exchange_broadcast_audit(
                db, record, "RECIPIENTS_CHANGED", sent=0, failed=0, detail=detail, check=proof, now=current
            )
            return {"status": "RECIPIENTS_CHANGED", "detail": detail, "target_count": int(record.get("target_count") or 0), "sent": 0}
        expected_count = int(record.get("target_count") or 0)
        expected_hash = str(record.get("audience_sha256") or "")
        current_hash = _broadcast_audience_hash(audience)
        if (
            expected_count != len(audience)
            or not expected_hash
            or expected_hash != current_hash
        ):
            detail = "Recipient set changed after preview; prepare a fresh preview"
            record.update({"status": "RECIPIENTS_CHANGED", "finished_at": current_text, "detail": detail})
            _append_exchange_broadcast_audit(
                db, record, "RECIPIENTS_CHANGED", sent=0, failed=0, detail=detail, check=proof, now=current
            )
            return {
                "status": "RECIPIENTS_CHANGED",
                "detail": detail,
                "target_count": expected_count,
                "sent": 0,
            }
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
    failed_recipient_uids = []
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
            failed_recipient_uids.append(str(recipient))

    status = "SENT" if sent == target_count and failed == 0 else "PARTIAL"
    detail = "All recipients sent" if status == "SENT" else "Some recipients could not be reached"
    return _terminal_state(
        uid, draft_id, status, sent=sent, failed=failed,
        failed_recipient_uids=failed_recipient_uids, detail=detail,
        check=latest_check,
    )


def _exchange_broadcast_reply(result):
    status = str((result or {}).get("status") or "BLOCKED")
    if status == "SENT":
        return f"✅ ברודקאסט המסחר הפנימי נשלח ל־{result.get('sent', 0)} משתמשים. בדיקת Exchange רעננה עברה לפני השליחה."
    if status == "PARTIAL":
        return f"🟡 ברודקאסט חלקי: נשלחו {result.get('sent', 0)}; נכשלו {result.get('failed', 0)}. בדיקת Exchange נרשמה. אפשר להכין ניסיון חוזר לנמענים שנכשלו בלבד."
    if status in {"DUPLICATE_ACK_REQUIRED", "SAFE_RETRY_REQUIRED"}:
        return (
            f"⛔ לא נשלח ברודקאסט. ביומן ההיסטורי נשלחו {result.get('previous_sent', 0)} "
            f"והיו {result.get('previous_failed', 0)} כישלונות, אך אין ראיה בטוחה לקהל מלא לניסיון חוזר. "
            "אישור כפילויות ישן אינו עוקף את החסימה. הכן תצוגה חדשה לנמענים שנכשלו בוודאות "
            "או למשתמשים שתאריך יצירת חשבונם מאומת לאחר השידור הקודם."
        )
    if status == "SAFE_RETRY_UNAVAILABLE":
        return (
            "⛔ לא נוצרה טיוטה. אי אפשר לאמת בבטחה את נתוני השידור הקודם או את תאריך הצטרפות המשתמשים. "
            "נדרשת ראיה ברמת הנמען; לא נשלחה הודעה."
        )
    if status == "NO_SAFE_NEW_RECIPIENTS":
        return (
            "ℹ️ לא נוצרה טיוטה: אין משתמשים שתאריך יצירת חשבונם מוכיח שהצטרפו לאחר השידור הקודם. "
            "השליחה חסומה כדי למנוע כפילויות."
        )
    if status == "NO_FAILED_RECIPIENTS":
        return "ℹ️ לא נוצרה טיוטה: אין נמענים שנכשלו ונשארו זכאים לניסיון חוזר."
    if status == "STOPPED_GATE_CLOSED":
        return f"⛔ נעצר באמצע כי בדיקת Exchange כבר לא ירוקה. נשלחו {result.get('sent', 0)} מתוך {result.get('target_count', 'היעד')}. לא נשלחו הודעות נוספות."
    if status == "BLOCKED":
        return f"⛔ לא נשלח ברודקאסט: Fresh Exchange check חסם את השליחה. {result.get('detail', '')}"
    if status == "EXPIRED":
        return "⌛ פג תוקף האישור. הכן תצוגה חדשה ואז אשר בנפרד."
    if status == "RECIPIENTS_CHANGED":
        return "⚠️ רשימת הנמענים השתנתה מאז התצוגה המקדימה. לא נשלחה הודעה; הכן תצוגה חדשה ובדוק את מספר הנמענים."
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
        "🔎 מוכנות ברודקאסט למסחר פנימי — READ ONLY\n\n"
        f"Fresh canonical Exchange check: {gate} · {proof['status']}\n"
        f"פרטים: {proof['detail']}\n\n"
        "לא נשלחה הודעה ולא נוצרה טיוטה.\n"
        f"{next_step}"
    )


def _broadcast_status_reply(uid, *, now=None):
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
    if isinstance(pending, dict) and pending_status == "PENDING_CONFIRMATION":
        try:
            expires_at = _utc_now(pending.get("expires_at"))
            current_time = _utc_now(now)
        except Exception:
            # A malformed/missing expiry can never be presented as confirmable.
            pending_status = "EXPIRED (invalid expiry; confirmation blocked)"
        else:
            if current_time >= expires_at:
                pending_status = "EXPIRED (confirmation window elapsed)"
            else:
                pending_status = f"PENDING_CONFIRMATION · expires {expires_at.isoformat()}"

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

    duplicate_notice = ""
    if isinstance(pending, dict) and pending.get("requires_duplicate_ack") is True:
        duplicate_notice = (
            f"\n⚠️ זיהוי כפילות: שידור קודם הגיע ל־{int(pending.get('previous_sent') or 0)} "
            f"ונכשל ל־{int(pending.get('previous_failed') or 0)}. "
            "אישור רגיל חסום; יש לאשר במפורש שידור מלא חוזר."
        )
    elif isinstance(pending, dict) and pending.get("audience_scope") == "failed_only":
        duplicate_notice = "\n✅ הטיוטה מיועדת רק לנמענים שנכשלו בשידור הקודם."

    return (
        "🔎 BROADCAST STATUS — READ ONLY\n"
        "הפקודה הזו לא שולחת הודעות.\n"
        f"Internal Exchange: {gate} · {proof['status']}\n"
        f"Exchange draft: {pending_status}{duplicate_notice}\n"
        f"Last audited Exchange broadcast: {last_broadcast}\n"
        "להכנת הודעת מסחר: אמור בפרטי ״הכן ברודקאסט למסחר פנימי״; "
        "נדרשים תצוגה מקדימה ואישור קולי נפרד."
    )



def route_exchange_broadcast_text(message, text, *, now=None):
    """Keep Exchange broadcast questions read-only in ordinary text chat.

    Typing either prepare or confirm phrases must never create a draft or send
    a broadcast; those sensitive steps require the separate voice-only path.
    """
    phrase = _normalize_voice_phrase(text)
    prepare_phrases = {_normalize_voice_phrase(x) for x in _PREPARE_VOICE_PHRASES}
    confirm_phrases = {_normalize_voice_phrase(x) for x in _CONFIRM_VOICE_PHRASES}
    is_prepare = phrase in prepare_phrases
    is_confirm = phrase in confirm_phrases

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
        return (
            "🎙️ טקסט רגיל לא יוצר טיוטת ברודקאסט. "
            "כדי להכין תצוגה מקדימה, שלח הודעה קולית בפרטי ואמור: "
            "״הכן ברודקאסט למסחר פנימי״.\n"
            "לא נוצרה טיוטה ולא נשלחה הודעה."
        )
    return (
        "🔒 טקסט רגיל אינו אישור לשליחת ברודקאסט. "
        "רק אחרי תצוגה מקדימה, אמור את האישור בהודעה קולית פרטית: "
        "״אשר ושלח ברודקאסט למסחר פנימי״.\n"
        "לא נשלחה הודעה."
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
        recipient_count = int(result.get("target_count") or 0)
        if result.get("audience_scope") == "failed_only":
            target_note = "✅ ניסיון חוזר ממוקד: רק נמענים שנכשלו בשידור הקודם."
            confirmation = "״אשר ושלח ברודקאסט למסחר פנימי״."
        elif result.get("audience_scope") == "new_users_only":
            target_note = (
                "✅ קהל מצומצם בלבד: רק משתמשים עם חותמת יצירה מאומתת באזור זמן "
                "שנוצרו אחרי סיום השידור הקודם. משתמשים שלא ניתן לאמת — מוחרגים."
            )
            confirmation = "״אשר ושלח ברודקאסט למסחר פנימי״."
        elif result.get("requires_duplicate_ack"):
            # Compatibility with an older draft schema; sending such a draft is blocked.
            target_note = "⛔ טיוטה ישנה עם סיכון לכפילויות אינה ניתנת לאישור."
            confirmation = "הכן תצוגה חדשה עם קהל בטוח."
        else:
            target_note = "קהל היעד הרגיל ננעל לתצוגה הזו."
            confirmation = "״אשר ושלח ברודקאסט למסחר פנימי״."
        return (
            "🧾 תצוגה מקדימה בלבד — לא נשלחה הודעה לאף משתמש.\n"
            f"👥 קהל היעד שננעל לתצוגה הזו: {recipient_count} משתמשים.\n"
            f"{target_note}\n"
            "אם רשימת הנמענים הרלוונטית תשתנה לפני האישור, השליחה תיחסם ותידרש תצוגה חדשה.\n"
            f"טיוטה בתוקף ל־{EXCHANGE_BROADCAST_TTL_SECONDS // 60} דקות.\n\n"
            f"{EXCHANGE_BROADCAST_TEXT}\n\n"
            f"כדי לבצע שליחה אמיתית, אמור עכשיו במפורש: {confirmation} "
            "ברגע האישור תתבצע בדיקת Exchange קנונית רעננה; אם השער לא OPEN וכל האינווריאנטים לא PASS, לא תישלח הודעה."
        )

    duplicate_acknowledged = phrase in {
        _normalize_voice_phrase(item) for item in _DUPLICATE_ACK_VOICE_PHRASES
    }
    result = send_confirmed_exchange_broadcast(
        bot, uid, now=now, duplicate_acknowledged=duplicate_acknowledged
    )
    return _exchange_broadcast_reply(result)
