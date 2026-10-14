"""Read-only reconciliation of historical internal SLH supply provenance.

This audit distinguishes internal token-balance history from live SLH on BSC.
It never modifies the database, approves historical issuance, or infers that a
ledger entry is backed merely because a current wallet balance exists.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation


def _number(value):
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return number if number.is_finite() else None


def _text(value):
    return str(value or "").strip()


def _suffix(value):
    value = _text(value)
    return value[-4:] if value else None


def _meta(row):
    value = row.get("meta")
    return value if isinstance(value, dict) else {}


def audit_db(db) -> dict:
    """Return evidence gaps and balance continuity findings without mutating db.

    A historical "mint" row is not automatically a valid issuance record. Until
    its provenance and resulting balance path are reconciled, it remains a
    launch blocker. Credits-ledger rows are not counted as SLH token supply.
    """
    if not isinstance(db, dict):
        return {
            "status": "FAIL",
            "finding_count": 1,
            "blocker_count": 1,
            "mint_event_count": 0,
            "mint_recorded_total": "0",
            "tracked_account_count": 0,
            "findings": [{"code": "SLH_PROVENANCE_DB_UNREADABLE"}],
        }

    users = db.get("users", {})
    users = users if isinstance(users, dict) else {}
    token_rows = db.get("slh_token_ledger", [])
    findings = []
    if not isinstance(token_rows, list):
        token_rows = []
        findings.append({"code": "SLH_TOKEN_LEDGER_MALFORMED"})

    general_rows = db.get("ledger", [])
    if not isinstance(general_rows, list):
        general_rows = []
        findings.append({"code": "SLH_GENERAL_LEDGER_MALFORMED"})

    observations = defaultdict(list)
    seen = set()
    mint_event_count = 0
    mint_total = Decimal(0)

    def add_observation(uid, row, *, before, after, mode="snapshot", amount=None,
                        source="slh_token_ledger", identity=None):
        uid = _text(uid)
        if uid not in users or not isinstance(users.get(uid), dict):
            return
        event_id = _text(row.get("event_id") or _meta(row).get("event_id"))
        key = identity or event_id or "|".join((
            source, uid, _text(row.get("timestamp") or row.get("time")),
            _text(row.get("reason")), _text(_meta(row).get("order_id")),
        ))
        dedupe = (uid, key)
        if dedupe in seen:
            return
        seen.add(dedupe)
        observations[uid].append({
            "timestamp": _text(row.get("timestamp") or row.get("time")),
            "event_id": event_id or None,
            "reason": _text(row.get("reason")),
            "before": before,
            "after": after,
            "mode": mode,
            "amount": amount,
            "source": source,
        })

    for index, row in enumerate(token_rows):
        if not isinstance(row, dict):
            findings.append({"code": "SLH_TOKEN_LEDGER_ROW_MALFORMED", "row_index": index})
            continue

        reason = _text(row.get("reason")).lower()
        event_id = _text(row.get("event_id"))
        from_uid = _text(row.get("from_uid"))
        to_uid = _text(row.get("to_uid"))
        amount = _number(row.get("amount"))
        before_from = _number(row.get("before_from"))
        after_from = _number(row.get("after_from"))
        before_to = _number(row.get("before_to"))
        after_to = _number(row.get("after_to"))

        if from_uid.lower() == "mint":
            mint_event_count += 1
            if amount is not None:
                mint_total += amount
            findings.append({
                "code": "MINT_SOURCE_REQUIRES_RECONCILIATION",
                "event_id": event_id or None,
                "to_uid_suffix": _suffix(to_uid),
                "amount": str(amount) if amount is not None else None,
            })
            if amount is None or amount <= 0:
                findings.append({
                    "code": "MINT_AMOUNT_INVALID",
                    "event_id": event_id or None,
                    "to_uid_suffix": _suffix(to_uid),
                })
            if before_to is None or after_to is None:
                findings.append({
                    "code": "MINT_BALANCE_SNAPSHOT_MISSING",
                    "event_id": event_id or None,
                    "to_uid_suffix": _suffix(to_uid),
                })
                add_observation(
                    to_uid, row, before=before_to, after=after_to,
                    mode="mint", amount=amount, identity=event_id or f"mint-row-{index}",
                )
            else:
                add_observation(to_uid, row, before=before_to, after=after_to)
            if to_uid not in users:
                findings.append({
                    "code": "MINT_RECIPIENT_ACCOUNT_MISSING",
                    "event_id": event_id or None,
                    "to_uid_suffix": _suffix(to_uid),
                })
            continue

        for uid, before, after, role in (
            (from_uid, before_from, after_from, "from"),
            (to_uid, before_to, after_to, "to"),
        ):
            if uid not in users or not isinstance(users.get(uid), dict):
                continue
            if before is not None or after is not None:
                add_observation(uid, row, before=before, after=after)
                continue

            if reason == "onchain:deposit:slh" and role == "to" and amount is not None and amount > 0:
                add_observation(uid, row, before=None, after=None, mode="delta", amount=amount)
            elif any(marker in reason for marker in (
                "distribution", "genesis", "bootstrap", "onchain:deposit:slh",
                "exchange:settlement_slh",
            )):
                findings.append({
                    "code": "SLH_EVENT_BALANCE_SNAPSHOT_MISSING",
                    "event_id": _text(row.get("event_id")) or None,
                    "uid_suffix": _suffix(uid),
                    "reason": reason[:72],
                })

        if "unbacked_test_distribution" in reason:
            findings.append({
                "code": "UNBACKED_TEST_DISTRIBUTION_REQUIRES_REVIEW",
                "event_id": event_id or None,
                "to_uid_suffix": _suffix(to_uid),
                "amount": str(amount) if amount is not None else None,
            })
            recipient = users.get(to_uid, {})
            wallet = recipient.get("wallet", {}) if isinstance(recipient, dict) else {}
            wallet = wallet if isinstance(wallet, dict) else {}
            total = _number(wallet.get("token_balance")) or Decimal(0)
            live = _number(wallet.get("live_token_balance")) or Decimal(0)
            if total > live:
                findings.append({
                    "code": "UNBACKED_TEST_BALANCE_OUTSTANDING",
                    "to_uid_suffix": _suffix(to_uid),
                    "outstanding_internal_slh": str(total - live),
                    "live_balance_is_backing_evidence": False,
                })

    # The older exchange recorded SLH reserves/corrections in the general ledger.
    # Include only these known SLH wallet-balance events; do not mix Credits rows
    # such as genesis_credits_allocation into SLH supply accounting.
    for row in general_rows:
        if not isinstance(row, dict):
            continue
        reason = _text(row.get("reason")).lower()
        if reason not in {"exchange:sell_reserve", "exchange:missed_release_correction"}:
            continue
        uid = _text(row.get("uid"))
        if uid not in users or not isinstance(users.get(uid), dict):
            continue
        meta = _meta(row)
        identity = _text(meta.get("event_id") or row.get("event_id"))
        if identity and (uid, identity) in seen:
            continue
        before = _number(row.get("before"))
        after = _number(row.get("after"))
        if before is None or after is None:
            findings.append({
                "code": "SLH_LEGACY_BALANCE_SNAPSHOT_MISSING",
                "event_id": identity or None,
                "uid_suffix": _suffix(uid),
                "reason": reason,
            })
            continue
        fallback_identity = identity or "|".join((
            "legacy-ledger", reason, uid, _text(meta.get("order_id")),
            _text(row.get("time")),
        ))
        add_observation(
            uid, row, before=before, after=after, source="ledger",
            identity=fallback_identity,
        )

    # Walk chronological observations. Gaps are reported, never silently netted.
    for uid, rows in observations.items():
        rows.sort(key=lambda item: item["timestamp"])
        last_after = None
        last_event_id = None
        for row in rows:
            mode = row["mode"]
            before = row["before"]
            after = row["after"]
            amount = row["amount"]

            if mode == "mint":
                if amount is None or amount <= 0:
                    continue
                inferred_before = last_after if last_after is not None else Decimal(0)
                if before is not None:
                    inferred_before = before
                inferred_after = after if after is not None else inferred_before + amount
                if last_after is not None and inferred_before != last_after:
                    findings.append({
                        "code": "TOKEN_BALANCE_SEQUENCE_GAP",
                        "uid_suffix": _suffix(uid),
                        "event_id": row["event_id"],
                        "prior_event_id": last_event_id,
                        "prior_after": str(last_after),
                        "observed_before": str(inferred_before),
                        "gap": str(inferred_before - last_after),
                    })
                last_after = inferred_after
                last_event_id = row["event_id"]
                continue

            if mode == "delta":
                before = last_after if last_after is not None else Decimal(0)
                after = before + amount
            if before is not None and last_after is not None and before != last_after:
                findings.append({
                    "code": "TOKEN_BALANCE_SEQUENCE_GAP",
                    "uid_suffix": _suffix(uid),
                    "event_id": row["event_id"],
                    "prior_event_id": last_event_id,
                    "prior_after": str(last_after),
                    "observed_before": str(before),
                    "gap": str(before - last_after),
                })
            if after is not None:
                last_after = after
                last_event_id = row["event_id"]

        user = users.get(uid, {})
        wallet = user.get("wallet", {}) if isinstance(user, dict) else {}
        wallet = wallet if isinstance(wallet, dict) else {}
        current = _number(wallet.get("token_balance"))
        if current is None:
            current = Decimal(0)
        if last_after is not None and current != last_after:
            findings.append({
                "code": "TOKEN_BALANCE_CURRENT_MISMATCH",
                "uid_suffix": _suffix(uid),
                "last_event_id": last_event_id,
                "ledger_expected_balance": str(last_after),
                "current_wallet_balance": str(current),
                "delta": str(current - last_after),
            })

    blocker_count = len(findings)
    return {
        "status": "PASS" if blocker_count == 0 else "FAIL",
        "finding_count": blocker_count,
        "blocker_count": blocker_count,
        "mint_event_count": mint_event_count,
        "mint_recorded_total": str(mint_total),
        "tracked_account_count": len(observations),
        "findings": findings,
    }
