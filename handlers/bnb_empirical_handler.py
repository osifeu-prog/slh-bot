"""Owner-only BNB empirical smoke and existing-TX reconciliation entrypoints.

The legacy /bnb_smoke path opens the wallet-signing UI for a new 0.01 BNB
canary transfer. The /bnb_reconcile path is separate: it can only inspect an
already-confirmed transaction, then requires a second explicit command before
the canonical idempotent settlement check. Neither path opens public BNB.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import re
import uuid

import state_manager
from core.authority import is_owner


RECONCILE_TTL_SECONDS = 300
RECONCILE_AUDIT_LIMIT = 50
_TX_HASH_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")


def _utc_now(value=None):
    if value is None:
        value = datetime.now(timezone.utc)
    elif isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        raise TypeError("BNB_RECONCILE_TIME_INVALID")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _utc_text(value=None):
    return _utc_now(value).isoformat()


def _idempotency_key(tx_hash):
    return f"bnb:deposit:{str(tx_hash or '').lower()}"


def _current_pass_evidence(db, evidence):
    """A stored PASS blocks reconciliation only if it revalidates now."""
    if not isinstance(evidence, dict) or evidence.get("status") != "PASS":
        return False
    try:
        from core.bnb_gate import _effective_config, _empirical_evidence_revalidated

        return _empirical_evidence_revalidated(
            evidence, _effective_config(db), db=db
        ) is True
    except Exception:
        return False


def _matching_ledger_entries(db, tx_hash):
    ledger = db.get("ledger", []) if isinstance(db, dict) else []
    if not isinstance(ledger, list):
        return None
    key = _idempotency_key(tx_hash)
    return [
        entry for entry in ledger
        if isinstance(entry, dict)
        and isinstance(entry.get("meta"), dict)
        and entry["meta"].get("idempotency_key") == key
    ]


def _inspect_existing_bnb_tx(uid, tx_hash):
    """Read-only revalidation for the preview and immediately before confirm."""
    uid = str(uid or "").strip()
    tx_hash = str(tx_hash or "").strip()
    if not is_owner(uid):
        return {"status": "FORBIDDEN"}
    if not _TX_HASH_RE.fullmatch(tx_hash):
        return {"status": "INVALID_TX_HASH"}

    try:
        from core.bnb_gate import bnb_deposits_open, bnb_readiness, _effective_config
        from core.deposit_monitor import verify_bnb_deposit
        from core.wallet_binding import get_binding

        # This flow is specifically for empirical evidence while public BNB
        # is closed. It is not an alternate route to opening the public gate.
        if bnb_deposits_open():
            return {"status": "GATE_OPEN"}
        readiness = bnb_readiness()
        if not isinstance(readiness, dict) or readiness.get("ready") is not True:
            return {"status": "BNB_CONFIGURATION_NOT_READY"}

        db = state_manager.load_db()
        evidence_root = db.get("settlement_evidence", {}) if isinstance(db, dict) else {}
        existing = evidence_root.get("bnb") if isinstance(evidence_root, dict) else None
        if _current_pass_evidence(db, existing):
            return {"status": "ALREADY_COMPLETED"}

        binding = get_binding(uid)
        if not isinstance(binding, dict) or not str(binding.get("address") or "").strip():
            return {"status": "BNB_WALLET_NOT_VERIFIED"}

        verified = verify_bnb_deposit(tx_hash)
        if not isinstance(verified, dict) or verified.get("ok") is not True:
            return {"status": "TX_NOT_VERIFIED"}

        sender = str(verified.get("from") or "").strip()
        bound_address = str(binding.get("address") or "").strip()
        if not sender or sender.lower() != bound_address.lower():
            return {"status": "BNB_TX_SENDER_NOT_BOUND_WALLET"}

        config = _effective_config()
        treasury = str(config.get("treasury_wallet") or "").strip()
        receiver = str(verified.get("to") or "").strip()
        if not treasury or not receiver or receiver.lower() != treasury.lower():
            return {"status": "BNB_TX_RECEIVER_NOT_CANONICAL_TREASURY"}

        try:
            confirmations = int(verified.get("confirmations") or 0)
            required = int(readiness.get("confirmations_required") or 15)
            amount_wei = int(verified.get("amount_wei") or 0)
        except (TypeError, ValueError, OverflowError):
            return {"status": "TX_FIELDS_INVALID"}
        if required < 1 or confirmations < required:
            return {
                "status": "INSUFFICIENT_CONFIRMATIONS",
                "confirmations": confirmations,
                "required_confirmations": required,
            }
        if amount_wei <= 0:
            return {"status": "INVALID_BNB_AMOUNT"}

        matching = _matching_ledger_entries(db, tx_hash)
        if matching is None:
            return {"status": "LEDGER_UNREADABLE"}
        if matching:
            # Do not reuse an already-settled transaction as fresh empirical
            # evidence. It would not prove first-pass settlement semantics.
            return {"status": "ALREADY_SETTLED"}

        return {
            "status": "OK",
            "tx_hash": tx_hash,
            "amount_wei": amount_wei,
            "amount_bnb": amount_wei / 10**18,
            "estimated_credits": (amount_wei / 10**18) * 1000,
            "confirmations": confirmations,
            "required_confirmations": required,
            "sender": sender,
            "treasury": receiver,
        }
    except Exception as exc:
        return {"status": "VALIDATION_FAILED", "detail": type(exc).__name__}


def _append_reconcile_audit(db, record, status, *, detail="", settlement=None, now=None):
    audit = db.setdefault("bnb_empirical_reconcile_audit", [])
    if not isinstance(audit, list):
        audit = []
        db["bnb_empirical_reconcile_audit"] = audit
    reconcile_id = str(record.get("reconcile_id") or "")
    if any(
        isinstance(item, dict) and item.get("reconcile_id") == reconcile_id
        for item in audit
    ):
        return
    audit.append({
        "reconcile_id": reconcile_id,
        "uid": str(record.get("uid") or ""),
        "tx_hash": str(record.get("tx_hash") or ""),
        "status": status,
        "created_at": record.get("created_at"),
        "finished_at": _utc_text(now),
        "detail": str(detail or "")[:120],
        "settlement": settlement or {},
    })
    del audit[:-RECONCILE_AUDIT_LIMIT]


def _finish_reconcile(uid, reconcile_id, status, *, detail="", settlement=None, now=None):
    finished_at = _utc_text(now)

    def mutate(db):
        pending = db.setdefault("bnb_empirical_reconcile_pending", {})
        record = pending.get(str(uid)) if isinstance(pending, dict) else None
        if not isinstance(record, dict) or record.get("reconcile_id") != reconcile_id:
            return {"status": "ALREADY_HANDLED"}
        record.update({
            "status": status,
            "finished_at": finished_at,
            "detail": str(detail or "")[:120],
        })
        if settlement is not None:
            record["settlement"] = settlement
        _append_reconcile_audit(
            db, record, status, detail=detail, settlement=settlement, now=now
        )
        result = {
            "status": status,
            "reconcile_id": reconcile_id,
            "tx_hash": record.get("tx_hash"),
            "detail": str(detail or "")[:120],
        }
        if isinstance(settlement, dict):
            for key in ("credits", "amount_wei", "confirmations", "gate_remained_closed"):
                if key in settlement:
                    result[key] = settlement[key]
        return result

    return state_manager.atomic_update(mutate)


def prepare_existing_bnb_reconcile(uid, tx_hash, *, now=None):
    """Preview a previously submitted BNB TX. Does not settle or send anything."""
    uid = str(uid or "").strip()
    tx_hash = str(tx_hash or "").strip()
    inspected = _inspect_existing_bnb_tx(uid, tx_hash)
    if inspected.get("status") != "OK":
        return inspected

    current = _utc_now(now)
    reconcile_id = uuid.uuid4().hex
    record = {
        "reconcile_id": reconcile_id,
        "uid": uid,
        "tx_hash": tx_hash,
        "status": "PENDING_CONFIRMATION",
        "created_at": current.isoformat(),
        "expires_at": (current + timedelta(seconds=RECONCILE_TTL_SECONDS)).isoformat(),
        "amount_wei": inspected["amount_wei"],
        "amount_bnb": inspected["amount_bnb"],
        "confirmations": inspected["confirmations"],
        "required_confirmations": inspected["required_confirmations"],
        "sender": inspected["sender"],
        "treasury": inspected["treasury"],
    }

    def mutate(db):
        evidence_root = db.get("settlement_evidence", {})
        existing = evidence_root.get("bnb") if isinstance(evidence_root, dict) else None
        if _current_pass_evidence(db, existing):
            return {"status": "ALREADY_COMPLETED"}
        matching = _matching_ledger_entries(db, tx_hash)
        if matching is None:
            return {"status": "LEDGER_UNREADABLE"}
        if matching:
            return {"status": "ALREADY_SETTLED"}
        pending = db.setdefault("bnb_empirical_reconcile_pending", {})
        if not isinstance(pending, dict):
            pending = {}
            db["bnb_empirical_reconcile_pending"] = pending
        previous = pending.get(uid)
        if isinstance(previous, dict) and previous.get("status") == "SENDING":
            return {"status": "IN_PROGRESS"}
        pending[uid] = record
        return {
            "status": "PREPARED",
            "reconcile_id": reconcile_id,
            "tx_hash": tx_hash,
            "amount_wei": inspected["amount_wei"],
            "amount_bnb": inspected["amount_bnb"],
            "estimated_credits": inspected["estimated_credits"],
            "confirmations": inspected["confirmations"],
            "required_confirmations": inspected["required_confirmations"],
            "expires_at": record["expires_at"],
        }

    return state_manager.atomic_update(mutate)



def prepare_auto_existing_bnb_reconcile(uid, *, now=None):
    """Discover one already-sent exact 0.01 BNB canary, then prepare—not settle—a preview."""
    uid = str(uid or "").strip()
    if not is_owner(uid):
        return {"status": "FORBIDDEN"}

    try:
        from core.bnb_auto_discovery import discover_bnb_transfer
        discovered = discover_bnb_transfer(uid)
    except Exception as exc:
        return {
            "status": "DISCOVERY_FAILED",
            "detail": type(exc).__name__,
            "scope": "read_only_discovery",
        }

    if not isinstance(discovered, dict):
        return {"status": "DISCOVERY_INVALID", "scope": "read_only_discovery"}

    status = str(discovered.get("status") or "DISCOVERY_INVALID")
    if status != "FOUND":
        candidates = discovered.get("candidates", [])
        safe_candidates = []
        if isinstance(candidates, list):
            for item in candidates[:5]:
                if isinstance(item, dict):
                    candidate_hash = str(item.get("tx_hash") or "").strip()
                    if _TX_HASH_RE.fullmatch(candidate_hash):
                        safe_candidates.append({"tx_hash": candidate_hash})
        return {
            "status": status,
            "scope": "read_only_discovery",
            "candidates": safe_candidates,
            "detail": str(discovered.get("detail") or "")[:120],
        }

    candidate = discovered.get("candidate")
    tx_hash = str(candidate.get("tx_hash") or "").strip() if isinstance(candidate, dict) else ""
    if not _TX_HASH_RE.fullmatch(tx_hash):
        return {"status": "INVALID_DISCOVERED_TX_HASH", "scope": "read_only_discovery"}

    # Existing preview path revalidates through canonical BSC RPC, wallet binding,
    # treasury and confirmations. If the ledger already contains this TX, do not
    # treat it as a new deposit or run the first-pass credit path. Prove it with
    # the dedicated idempotent replay, which must leave the current balance
    # unchanged and keeps the public BNB gate closed.
    preview = prepare_existing_bnb_reconcile(uid, tx_hash, now=now)
    if str(preview.get("status") or "").upper() == "ALREADY_SETTLED":
        try:
            from core.bnb_empirical_smoke import reconcile_existing_settlement

            proof = reconcile_existing_settlement(uid, tx_hash)
        except Exception as exc:
            return {
                "status": "REPLAY_FAILED",
                "tx_hash": tx_hash,
                "detail": type(exc).__name__,
                "scope": "existing_ledger_replay",
            }
        if not isinstance(proof, dict):
            return {
                "status": "REPLAY_RESULT_INVALID",
                "tx_hash": tx_hash,
                "scope": "existing_ledger_replay",
            }
        proof["tx_hash"] = str(proof.get("tx_hash") or tx_hash)
        proof["scope"] = "existing_ledger_replay"
        return proof
    return preview


def _auto_preview_reply(result):
    status = str((result or {}).get("status") or "BLOCKED")
    if status in {"PASS", "ALREADY_PASS"}:
        if result.get("gate_remained_closed") is not True:
            return (
                "⛔ הוכחת BNB לא סומנה כ־PASS כי לא הוכח שהשער נשאר סגור. "
                "לא לפתוח שימוש ציבורי; יש לבדוק את הדוח הקנוני."
            )
        tx_hash = str(result.get("tx_hash") or "")
        heading = "PASS" if status == "PASS" else "ALREADY PASS"
        lines = [
            f"✅ BNB — הוכחת העברה קיימת: {heading}",
            f"TX: {tx_hash}",
            "ה־ledger הקנוני וה־BSC RPC אומתו מחדש.",
            "Replay: DUPLICATE · Credits חדשים מה־replay: 0",
            "היתרה הנוכחית נשארה ללא שינוי.",
            "🔒 שער BNB הציבורי נשאר CLOSED.",
            "לא נשלחה עסקת BNB חדשה ולא נוצר זיכוי נוסף.",
        ]
        return "\\n".join(lines)
    if status == "ALREADY_COMPLETED":
        return (
            "✅ הוכחת BNB קיימת ונבדקה מחדש מול ה־BSC וה־ledger. "
            "שער BNB הציבורי נשאר CLOSED; לא נשלחה עסקה חדשה ולא נוצר זיכוי נוסף."
        )
    if status == "PREPARED":
        return (
            "🔎 נמצאה העברה קיימת שמתאימה לבדיקה; לא נשלחה עסקת BNB חדשה.\n"
            + _preview_reply(result)
        )
    if status == "NOT_FOUND":
        return (
            "🔎 לא נמצאה העברה קיימת שמתאימה בדיוק ל־0.01 BNB מהארנק המאומת ל־Treasury הקנוני.\n"
            "לא נשלחה עסקה, לא שונו יתרות, ו־BNB נשאר CLOSED. אין לבצע העברה נוספת רק כדי לצבוע את הדוח בירוק."
        )
    if status == "AMBIGUOUS":
        candidates = (result or {}).get("candidates") or []
        hashes = [str(x.get("tx_hash") or "") for x in candidates if isinstance(x, dict) and x.get("tx_hash")]
        listed = "\n".join(hashes[:5])
        suffix = f"\nמועמדים:\n{listed}" if listed else ""
        return (
            "⛔ נמצאו כמה העברות קיימות אפשריות. לא נוצר preview ולא בוצע settlement. "
            "צריך לזהות את ה־TX המדויק לפני השלב הבא."
            + suffix
        )
    if status == "DISCOVERY_FAILED":
        return (
            "⛔ גילוי ההעברה הקיימת לא הצליח. לא בוצעה עסקה ולא שונו יתרות. "
            f"קוד אבחון: {str((result or {}).get('detail') or status)[:80]}. "
            "BNB נשאר CLOSED."
        )
    if status == "FORBIDDEN":
        return "⛔ BNB reconciliation זמין לבעלים בלבד."
    if status == "DISCOVERY_INVALID":
        return "⛔ מקור גילוי ההעברה החזיר תוצאה לא תקינה. לא בוצע settlement; BNB נשאר CLOSED."
    return _preview_reply(result)

def confirm_existing_bnb_reconcile(uid, *, tx_hash=None, now=None):
    """Explicitly settle a prepared existing TX once; public BNB stays closed."""
    uid = str(uid or "").strip()
    if not is_owner(uid):
        return {"status": "FORBIDDEN"}

    current = _utc_now(now)
    try:
        db = state_manager.load_db()
    except Exception:
        return {"status": "STATE_UNREADABLE"}
    pending = db.get("bnb_empirical_reconcile_pending", {}) if isinstance(db, dict) else {}
    record = pending.get(uid) if isinstance(pending, dict) else None
    if not isinstance(record, dict):
        return {"status": "NOT_PENDING"}
    if record.get("status") != "PENDING_CONFIRMATION":
        return {"status": "ALREADY_HANDLED"}
    reconcile_id = str(record.get("reconcile_id") or "")
    stored_tx_hash = str(record.get("tx_hash") or "")
    provided_tx_hash = str(tx_hash or "").strip()
    if not _TX_HASH_RE.fullmatch(provided_tx_hash):
        return {"status": "INVALID_TX_HASH"}
    if provided_tx_hash.lower() != stored_tx_hash.lower():
        return {"status": "TX_HASH_MISMATCH"}
    tx_hash = stored_tx_hash
    try:
        expires_at = _utc_now(record.get("expires_at"))
    except Exception:
        expires_at = current - timedelta(seconds=1)
    if current >= expires_at:
        return _finish_reconcile(
            uid, reconcile_id, "EXPIRED",
            detail="Preview expired; prepare the existing TX again", now=current
        )

    inspected = _inspect_existing_bnb_tx(uid, tx_hash)
    if inspected.get("status") != "OK":
        return _finish_reconcile(
            uid, reconcile_id, "BLOCKED",
            detail=str(inspected.get("status") or "TX_REVALIDATION_FAILED"),
            now=current,
        )

    def claim(db_now):
        pending_now = db_now.setdefault("bnb_empirical_reconcile_pending", {})
        item = pending_now.get(uid) if isinstance(pending_now, dict) else None
        if not isinstance(item, dict) or item.get("reconcile_id") != reconcile_id:
            return {"status": "ALREADY_HANDLED"}
        if item.get("status") != "PENDING_CONFIRMATION":
            return {"status": "ALREADY_HANDLED"}
        try:
            if current >= _utc_now(item.get("expires_at")):
                return {"status": "EXPIRED"}
        except Exception:
            return {"status": "EXPIRED"}
        evidence_root = db_now.get("settlement_evidence", {})
        existing = evidence_root.get("bnb") if isinstance(evidence_root, dict) else None
        if _current_pass_evidence(db_now, existing):
            return {"status": "ALREADY_COMPLETED"}
        matching = _matching_ledger_entries(db_now, tx_hash)
        if matching is None:
            return {"status": "LEDGER_UNREADABLE"}
        if matching:
            return {"status": "ALREADY_SETTLED"}
        item["status"] = "SENDING"
        item["confirmed_at"] = current.isoformat()
        return {"status": "CLAIMED"}

    claim_result = state_manager.atomic_update(claim)
    if claim_result.get("status") != "CLAIMED":
        if claim_result.get("status") == "EXPIRED":
            return _finish_reconcile(
                uid, reconcile_id, "EXPIRED",
                detail="Preview expired; prepare the existing TX again", now=current
            )
        return claim_result

    # Canonical service re-verifies chain, bound sender, treasury, confirmations,
    # first-pass balance delta, ledger idempotency and replay. It never opens BNB.
    try:
        from core.bnb_empirical_smoke import run as run_empirical_smoke
        settlement = run_empirical_smoke(uid, tx_hash)
    except Exception as exc:
        return _finish_reconcile(
            uid, reconcile_id, "BLOCKED",
            detail=f"Canonical settlement did not prove PASS ({type(exc).__name__})",
            now=current,
        )

    if not isinstance(settlement, dict) or settlement.get("status") != "PASS":
        return _finish_reconcile(
            uid, reconcile_id, "BLOCKED",
            detail="Canonical settlement evidence did not return PASS",
            settlement=settlement if isinstance(settlement, dict) else None,
            now=current,
        )
    if settlement.get("gate_remained_closed") is not True:
        return _finish_reconcile(
            uid, reconcile_id, "BLOCKED",
            detail="Gate-closed invariant did not pass",
            settlement=settlement,
            now=current,
        )
    return _finish_reconcile(
        uid, reconcile_id, "PASS",
        detail="Existing transaction verified; settlement and replay reconciled; public BNB remains closed",
        settlement=settlement,
        now=current,
    )


def _private_owner_command(message):
    uid = str(getattr(getattr(message, "from_user", None), "id", "") or "")
    if not is_owner(uid):
        return uid, "⛔ הפקודה זמינה לבעלים בלבד."
    if str(getattr(getattr(message, "chat", None), "type", "")).lower() != "private":
        return uid, "⛔ בדיקת BNB זמינה רק בשיחה הפרטית עם הבוט."
    return uid, None


def _preview_reply(result):
    status = str((result or {}).get("status") or "BLOCKED")
    if status == "PREPARED":
        amount = int(result.get("amount_wei") or 0) / 10**18
        credits = float(result.get("estimated_credits") or 0)
        return (
            "🧾 BNB — תצוגה מקדימה בלבד; לא שונו יתרות ולא נשלחה עסקה.\n"
            f"TX: {result.get('tx_hash', '')}\n"
            f"סכום מאומת: {amount:.8f} BNB · confirmations: {result.get('confirmations')}/{result.get('required_confirmations')}\n"
            f"Settlement משוער אם האישור יעבור: +{credits:.8f} Credits פעם אחת.\n"
            "השער הציבורי יישאר CLOSED.\n"
            f"לאישור מפורש של ה־TX הזה בלבד, שלח בתוך 5 דקות: /bnb_reconcile_confirm {result.get('tx_hash', '')}"
        )
    details = {
        "DISCOVERY_FAILED": "לא ניתן היה לגלות ולאמת את ההעברה הקיימת כרגע.",
        "DISCOVERY_INVALID": "מקור הגילוי החזיר תוצאה לא תקינה.",
        "INVALID_DISCOVERED_TX_HASH": "המערכת לא קיבלה TX hash תקין ממסלול הגילוי.",
        "NOT_FOUND": "לא נמצאה העברה קיימת מדויקת; לא לשלוח BNB חדש רק לצורך בדיקה.",
        "AMBIGUOUS": "נמצאו כמה מועמדים; נדרש לזהות את ה-TX המדויק. לא בוצע settlement.",
        "INVALID_TX_HASH": "פורמט TX hash לא תקין.",
        "BNB_CONFIGURATION_NOT_READY": "תצורת BNB/treasury אינה מוכנה.",
        "TX_NOT_VERIFIED": "העסקה לא אומתה ברשת BSC/לפי treasury הנוכחי.",
        "BNB_WALLET_NOT_VERIFIED": "אין ארנק BNB מאומת לבעלים.",
        "BNB_TX_SENDER_NOT_BOUND_WALLET": "השולח אינו הארנק המאומת של הבעלים.",
        "BNB_TX_RECEIVER_NOT_CANONICAL_TREASURY": "היעד אינו treasury הקנוני.",
        "INSUFFICIENT_CONFIRMATIONS": "עדיין אין מספיק confirmations.",
        "ALREADY_SETTLED": "ה־TX כבר קיים ב־ledger; הוא אינו הוכחת first-pass חדשה.",
        "ALREADY_COMPLETED": "כבר קיימת הוכחת BNB PASS.",
        "GATE_OPEN": "שער BNB כבר פתוח; מסלול reconciliation זה אינו רלוונטי.",
        "LEDGER_UNREADABLE": "ה־ledger אינו קריא; לא בוצע settlement.",
        "IN_PROGRESS": "כבר מתבצע reconcile; לא נוצרה פעולה נוספת.",
        "FORBIDDEN": "OWNER בלבד.",
        "STATE_UNREADABLE": "מצב המערכת אינו קריא.",
    }
    return f"⛔ BNB reconciliation חסום: {details.get(status, status)}"


def _confirm_reply(result):
    status = str((result or {}).get("status") or "BLOCKED")
    if status == "PASS":
        return (
            "✅ BNB existing-TX reconciliation PASS.\n"
            f"TX: {result.get('tx_hash', '')}\n"
            f"Credits שנוספו: {float(result.get('credits') or 0):.8f}\n"
            "העסקה אומתה, נרשם settlement יחיד, replay לא זיכה שוב.\n"
            "🔒 שער BNB הציבורי נשאר CLOSED; לא נשלחה עסקה חדשה."
        )
    if status == "EXPIRED":
        return "⌛ תצוגת ה־TX פגה. הכן תצוגה חדשה עם /bnb_reconcile <tx_hash>."
    if status == "ALREADY_HANDLED":
        return "⛔ הטיוטה כבר טופלה או אושרה; לא נוצר settlement נוסף."
    if status == "NOT_PENDING":
        return "⛔ אין TX ממתין לאישור. התחל עם /bnb_reconcile <tx_hash>."
    if status == "FORBIDDEN":
        return "⛔ OWNER בלבד."
    return (
        "⛔ ה־reconciliation לא אושר כ־PASS. לא לפתוח את שער BNB. "
        f"סיבה: {result.get('detail') or status}"
    )


def register(bot):
    @bot.message_handler(commands=["bnb_reconcile_auto"])
    def bnb_reconcile_auto(message):
        uid, denial = _private_owner_command(message)
        if denial:
            bot.reply_to(message, denial)
            return
        result = prepare_auto_existing_bnb_reconcile(uid)
        bot.reply_to(message, _auto_preview_reply(result), parse_mode=None)

    @bot.message_handler(commands=["bnb_reconcile"])
    def bnb_reconcile_preview(message):
        uid, denial = _private_owner_command(message)
        if denial:
            bot.reply_to(message, denial)
            return
        parts = (getattr(message, "text", "") or "").split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(
                message,
                "שימוש: /bnb_reconcile <tx_hash>\n"
                "בודק TX קיים בלבד; לא משדר עסקה ולא משנה יתרות עד לפקודת אישור נפרדת.",
            )
            return
        result = prepare_existing_bnb_reconcile(uid, parts[1].strip())
        bot.reply_to(message, _preview_reply(result), parse_mode=None)

    @bot.message_handler(commands=["bnb_reconcile_confirm"])
    def bnb_reconcile_confirm(message):
        uid, denial = _private_owner_command(message)
        if denial:
            bot.reply_to(message, denial)
            return
        parts = (getattr(message, "text", "") or "").split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(
                message,
                "שימוש: /bnb_reconcile_confirm <exact_tx_hash>\n"
                "האישור חייב לכלול בדיוק את ה־TX שהופיע בתצוגה המקדימה.",
            )
            return
        result = confirm_existing_bnb_reconcile(uid, tx_hash=parts[1].strip())
        bot.reply_to(message, _confirm_reply(result), parse_mode=None)

    @bot.message_handler(commands=["bnb_smoke", "bnbtest"])
    def bnb_smoke(message):
        uid = str(message.from_user.id)
        if not is_owner(uid):
            return

        public_url = os.getenv(
            "SLH_PUBLIC_URL",
            "https://slh-cloud-bot-production.up.railway.app",
        ).rstrip("/")
        url = public_url + "/bnb-smoke"

        try:
            from telebot import types

            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    "⚡️ שלח 0.01 BNB לבדיקה",
                    web_app=types.WebAppInfo(url=url),
                )
            )
            bot.reply_to(
                message,
                "🧪 BNB EMPIRICAL SMOKE\n\n"
                "בדיקה חד־פעמית לבעלים בלבד.\n"
                "• סכום: 0.01 BNB\n"
                "• רשת: BNB Smart Chain (56)\n"
                "• Settlement ציבורי: CLOSED\n"
                "• הארנק שלך בלבד מאשר את העסקה\n"
                "• השרת לא מחזיק מפתח ולא חותם\n\n"
                "לחץ על הכפתור. לאחר אישור הארנק המערכת תמתין ל־15 confirmations "
                "ותבצע settlement idempotent של +10 Credits.",
                reply_markup=markup,
            )
        except Exception as exc:
            bot.reply_to(message, f"❌ BNB smoke button failed: {type(exc).__name__}")

    @bot.message_handler(commands=["bnb_return", "bnb_return_smoke"])
    def bnb_return(message):
        uid = str(message.from_user.id)
        if not is_owner(uid):
            return

        public_url = os.getenv(
            "SLH_PUBLIC_URL",
            "https://slh-cloud-bot-production.up.railway.app",
        ).rstrip("/")
        url = public_url + "/bnb-browser-return"

        try:
            from telebot import types

            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton(
                    "↩️ החזר לצביקה 0.01 BNB",
                    web_app=types.WebAppInfo(url=url),
                )
            )
            bot.reply_to(
                message,
                "↩️ BNB RETURN SMOKE\n\n"
                "מסלול חד־פעמי לבעלים בלבד.\n"
                "• סכום נעול: 0.01 BNB\n"
                "• יעד: ארנק BNB המאומת הנוכחי של צביקה\n"
                "• רשת: BNB Smart Chain (56)\n"
                "• הארנק שלך בלבד חותם ומשדר\n"
                "• השרת אינו מחזיק מפתח ואינו משדר\n"
                "• אימות: sender + recipient + exact Wei + 15 confirmations\n\n"
                "לחץ על הכפתור, חבר את ה־Trezor דרך MetaMask ואשר רק את העסקה שמוצגת.\n"
                "Settlement ציבורי נשאר CLOSED.",
                reply_markup=markup,
            )
        except Exception as exc:
            bot.reply_to(message, f"❌ BNB return button failed: {type(exc).__name__}")
