import json
import math
from pathlib import Path
from datetime import datetime, timezone
import state_manager

DB_PATH = Path("state/db.json")




TREASURY_UID = "SLH_TREASURY"


def get_balance_safe(uid):
    db = state_manager.load_db()
    uid = str(uid)

    user = db.get("users", {}).get(uid)

    if not user:
        raise Exception("USER_NOT_FOUND")

    return user.get("wallet", {}).get("credits", 0)


def record_transaction(uid, amount, reason="unknown", meta=None, *, return_details=False):
    uid = str(uid)

    if not isinstance(amount, (int, float)):
        raise TypeError("amount must be numeric")
    if not math.isfinite(amount):
        raise ValueError("INVALID_AMOUNT")

    meta = meta or {}

    def mutate(db):
        users = db.setdefault("users", {})

        if uid not in users:
            raise Exception("USER_NOT_FOUND")

        ledger = db.setdefault("ledger", [])

        idempotency_key = meta.get("idempotency_key")
        if idempotency_key:
            for entry in ledger:
                existing_meta = entry.get("meta") or {}
                if existing_meta.get("idempotency_key") != idempotency_key:
                    continue

                if not return_details:
                    return entry["after"]

                conflict = (
                    str(entry.get("uid")) != uid
                    or str(entry.get("reason")) != str(reason)
                    or float(entry.get("amount", 0) or 0) != float(amount)
                )
                for field in ("tx_hash", "bnb_amount_wei", "from", "to"):
                    if field not in meta:
                        continue
                    if field not in existing_meta:
                        conflict = True
                        break
                    old_value, new_value = existing_meta.get(field), meta.get(field)
                    if field in {"tx_hash", "from", "to"}:
                        matches = str(old_value or "").lower() == str(new_value or "").lower()
                    else:
                        try:
                            matches = int(old_value) == int(new_value)
                        except (TypeError, ValueError):
                            matches = False
                    if not matches:
                        conflict = True
                        break

                wallet = users.get(uid, {}).get("wallet", {})
                return {
                    "status": "CONFLICT" if conflict else "DUPLICATE",
                    "balance_after": wallet.get("credits"),
                    "credits_applied": 0.0,
                    "existing_uid": str(entry.get("uid")),
                }

        user = users[uid]
        # Enforce the freeze at the atomic debit boundary as well as purchase
        # creation. An already-recorded idempotent debit returns above, so a
        # paid purchase can still recover safely after a crash.
        if (
            amount < 0
            and str(reason) == "store:purchase"
            and isinstance(user, dict)
            and user.get("frozen") is True
        ):
            raise ValueError("ACCOUNT_FROZEN")

        wallet = user.setdefault("wallet", {})

        before = wallet.get("credits", 0)
        after = before + amount

        if after < 0:
            raise ValueError("INSUFFICIENT_CREDITS")

        wallet["credits"] = after

        ledger.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": uid,
            "before": before,
            "amount": amount,
            "after": after,
            "reason": reason,
            "meta": meta,
        })

        if return_details:
            return {
                "status": "APPLIED",
                "balance_after": after,
                "credits_applied": amount,
                "existing_uid": uid,
            }
        return after

    return state_manager.atomic_update(mutate)


def record_ton_deposit(
    uid,
    credits,
    ton_amount,
    tx_hash,
    meta=None,
):
    """
    Atomic TON deposit authority.

    Guarantees:
    1. transaction hash can only be credited once
    2. wallet credit mutation and transaction registration happen atomically
    3. ledger entry is created
    """

    uid = str(uid)
    meta = meta or {}

    # P0 input validation: TON deposits may only create positive credits.
    if not isinstance(credits, (int, float)):
        raise TypeError("credits must be numeric")

    if credits <= 0:
        raise ValueError("INVALID_TON_CREDITS")

    if not isinstance(ton_amount, (int, float)):
        raise TypeError("ton_amount must be numeric")

    if ton_amount <= 0:
        raise ValueError("INVALID_TON_AMOUNT")

    if not isinstance(tx_hash, str) or not tx_hash.strip():
        raise ValueError("INVALID_TX_HASH")

    tx_hash = tx_hash.strip()

    def mutate(db):
        users = db.setdefault("users", {})

        if uid not in users:
            raise Exception("USER_NOT_FOUND")

        # A used transaction hash is an immutable settlement identity, not
        # enough evidence by itself to call every replay an exact duplicate.
        # Inspect all available canonical source rows before taking the no-op
        # path. Missing, duplicated or internally inconsistent evidence fails
        # closed and never reaches the Credits mutation.
        from decimal import Decimal, InvalidOperation

        def number(value):
            if isinstance(value, bool):
                raise ValueError("TON_DEPOSIT_IDENTITY_UNKNOWN")
            try:
                parsed = Decimal(str(value))
            except (InvalidOperation, TypeError, ValueError):
                raise ValueError("TON_DEPOSIT_IDENTITY_UNKNOWN") from None
            if not parsed.is_finite():
                raise ValueError("TON_DEPOSIT_IDENTITY_UNKNOWN")
            return parsed

        def normalized_hash(value):
            return str(value or "").strip().lower()

        used_txs = db.get("used_ton_txs", [])
        if not isinstance(used_txs, list):
            raise ValueError("TON_DEPOSIT_IDENTITY_UNKNOWN")

        transactions = db.get("transactions", [])
        ledger = db.get("ledger", [])
        if not isinstance(transactions, list) or not isinstance(ledger, list):
            raise ValueError("TON_DEPOSIT_IDENTITY_UNKNOWN")

        requested_hash = normalized_hash(tx_hash)
        matching_transactions = [
            row for row in transactions
            if isinstance(row, dict)
            and str(row.get("type") or "").lower() == "ton"
            and normalized_hash(row.get("tx_hash")) == requested_hash
        ]
        matching_ledger = [
            row for row in ledger
            if isinstance(row, dict)
            and str(row.get("reason") or "") == "ton:deposit"
            and normalized_hash(
                (row.get("meta") or {}).get("tx_hash")
                if isinstance(row.get("meta"), dict)
                else row.get("tx_hash")
            ) == requested_hash
        ]
        used_hash = any(normalized_hash(item) == requested_hash for item in used_txs)

        # Rows with this hash but no used-hash index, or a used hash without
        # its unique transaction + ledger pair, indicate incomplete evidence.
        evidence_exists = bool(used_hash or matching_transactions or matching_ledger)
        if evidence_exists:
            if (
                not used_hash
                or len(matching_transactions) != 1
                or len(matching_ledger) != 1
            ):
                raise ValueError("TON_DEPOSIT_IDENTITY_UNKNOWN")

            previous_tx = matching_transactions[0]
            previous_ledger = matching_ledger[0]
            previous_meta = previous_ledger.get("meta")
            if not isinstance(previous_meta, dict):
                raise ValueError("TON_DEPOSIT_IDENTITY_UNKNOWN")

            try:
                old_credits = number(previous_tx.get("credits"))
                old_ton_amount = number(previous_tx.get("ton_amount"))
                ledger_amount = number(previous_ledger.get("amount"))
                ledger_before = number(previous_ledger.get("before"))
                ledger_after = number(previous_ledger.get("after"))
                stored_ledger_ton = number(previous_meta.get("ton_amount"))
            except ValueError:
                raise ValueError("TON_DEPOSIT_IDENTITY_UNKNOWN") from None

            # First distinguish an evidenced identity conflict from missing
            # or contradictory historical data.
            if (
                str(previous_tx.get("uid") or "") != uid
                or str(previous_ledger.get("uid") or "") != str(previous_tx.get("uid") or "")
                or old_credits != number(previous_ledger.get("amount"))
                or old_ton_amount != stored_ledger_ton
                or old_credits != ledger_amount
                or ledger_before + ledger_amount != ledger_after
            ):
                raise ValueError("TON_DEPOSIT_IDENTITY_UNKNOWN")
            if (
                old_credits != number(credits)
                or old_ton_amount != number(ton_amount)
            ):
                raise ValueError("TON_DEPOSIT_IDENTITY_CONFLICT")

            # The ledger row is the canonical place where binding, treasury,
            # memo and transaction-specific chain evidence are retained.
            # If a requested immutable field is absent from one side, do not
            # guess that an old row represents the same settlement.
            identity_fields = (
                "idempotency_key",
                "source",
                "binding_address_raw",
                "treasury",
                "memo",
                "rate",
                "utime",
                "lt",
                "deposit_intent_id",
            )
            for field in identity_fields:
                requested_present = field in meta
                stored_present = field in previous_meta
                requested_value = meta.get(field)
                stored_value = previous_meta.get(field)

                # A completed payment may be replayed after its original
                # intent is already matched. In that case no new intent is
                # proposed, so None must not invalidate an otherwise exact
                # replay. A newly proposed intent, however, must match the
                # original intent identity exactly.
                if field == "deposit_intent_id" and requested_value in (None, ""):
                    continue
                if not requested_present or not stored_present:
                    raise ValueError("TON_DEPOSIT_IDENTITY_UNKNOWN")
                if field == "rate":
                    try:
                        matches = number(requested_value) == number(stored_value)
                    except ValueError:
                        raise ValueError("TON_DEPOSIT_IDENTITY_UNKNOWN") from None
                elif field in {"binding_address_raw", "treasury", "memo"}:
                    matches = str(requested_value or "").strip().lower() == str(stored_value or "").strip().lower()
                else:
                    matches = str(requested_value if requested_value is not None else "") == str(stored_value if stored_value is not None else "")
                if not matches:
                    raise ValueError("TON_DEPOSIT_IDENTITY_CONFLICT")

            return None

        # This is a new transaction only when neither the canonical used-hash
        # index nor a transaction/ledger source row has this hash.

        user = users[uid]
        wallet = user.setdefault("wallet", {})

        before = wallet.get("credits", 0)
        after = before + credits

        wallet["credits"] = after

        used_txs.append(tx_hash)

        db.setdefault("transactions", []).append({
            "uid": uid,
            "credits": credits,
            "type": "ton",
            "ton_amount": ton_amount,
            "tx_hash": tx_hash,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        ledger = db.setdefault("ledger", [])

        ledger.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": uid,
            "before": before,
            "amount": credits,
            "after": after,
            "reason": "ton:deposit",
            "meta": {
                **meta,
                "tx_hash": tx_hash,
                "ton_amount": ton_amount,
            },
        })

        return after

    return state_manager.atomic_update(mutate)
def stake_credits(uid, amount, meta=None):
    """Deprecated legacy staking mutation.

    The canonical staking authority is core.staking_service.stake_locked().
    Keeping this API disabled prevents wallet[\"staked\"] from changing without
    a matching stake_positions entry and lock metadata.
    """
    raise RuntimeError(
        "stake_credits is deprecated and unsafe: use "
        "staking_service.stake_locked(uid, amount, lock_days=30, meta=meta)."
    )


def unstake_credits(uid, amount, meta=None):
    """Deprecated legacy staking mutation.

    The canonical staking authority is core.staking_service.unstake_locked(),
    which requires the position id and updates wallet + position atomically.
    """
    raise RuntimeError(
        "unstake_credits is deprecated and unsafe: use "
        "staking_service.unstake_locked(uid, position_id, meta=meta)."
    )

def purchase_item(
    uid,
    item,
    price,
    referrer_uid=None,
    commission_rate=0.10,
    meta=None,
):
    """
    Atomic purchase authority.

    One DB transaction performs:
    - buyer debit
    - entitlement mutation
    - optional referral commission
    - immutable ledger entries
    """

    uid = str(uid)
    price = float(price)
    meta = meta or {}

    if price <= 0:
        raise ValueError("INVALID_PRICE")

    def mutate(db):
        users = db.setdefault("users", {})

        buyer = users.get(uid)
        if buyer is None:
            raise Exception("USER_NOT_FOUND")

        buyer_wallet = buyer.setdefault("wallet", {})
        buyer_before = buyer_wallet.get("credits", 0)

        if buyer_before < price:
            raise ValueError("INSUFFICIENT_CREDITS")

        buyer_after = buyer_before - price
        buyer_wallet["credits"] = buyer_after

        if item == "ask_credit":
            buyer["ask_credits"] = buyer.get("ask_credits", 0) + 1

        elif item == "premium_agent":
            buyer["premium"] = True

        else:
            raise ValueError("UNKNOWN_ITEM")

        ledger = db.setdefault("ledger", [])

        ledger.append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": uid,
            "before": buyer_before,
            "amount": -price,
            "after": buyer_after,
            "reason": f"purchase:{item}",
            "meta": dict(meta),
        })

        commission = 0

        referrer_uid = (
                db.get("users", {})
                  .get(uid, {})
                  .get("referral", {})
                  .get("referred_by")
            )
        if referrer_uid:
            referrer_uid = str(referrer_uid)

            if referrer_uid != uid and referrer_uid in users:
                commission = round(
                    price * float(commission_rate),
                    2
                )

                if commission > 0:
                    ref_user = users[referrer_uid]
                    ref_wallet_value = ref_user.get("wallet")
                    ref_wallet_is_valid = (
                        ref_wallet_value is None or isinstance(ref_wallet_value, dict)
                    )
                    ref_wallet = ref_wallet_value if isinstance(ref_wallet_value, dict) else {}

                    ref_before = ref_wallet.get("credits", 0)
                    treasury = users.get(TREASURY_UID)
                    treasury_wallet = (
                        treasury.get("wallet")
                        if isinstance(treasury, dict)
                        and isinstance(treasury.get("wallet"), dict)
                        else {}
                    )
                    try:
                        treasury_before = float(treasury_wallet.get("credits", 0) or 0)
                    except (TypeError, ValueError, OverflowError):
                        treasury_before = 0.0

                    # Fail closed: an unfunded referral commission creates no
                    # recipient ledger row and no synthetic Treasury account.
                    if (
                        not ref_wallet_is_valid
                        or not math.isfinite(treasury_before)
                        or treasury_before < commission
                    ):
                        commission = 0
                    else:
                        if not isinstance(ref_wallet_value, dict):
                            ref_wallet = {}
                            ref_user["wallet"] = ref_wallet
                        ref_after = ref_before + commission
                        treasury_after = round(treasury_before - commission, 2)
                        treasury_wallet["credits"] = treasury_after
                        ledger.append({
                            "time": datetime.now(timezone.utc).isoformat(),
                            "uid": TREASURY_UID,
                            "before": treasury_before,
                            "amount": -commission,
                            "after": treasury_after,
                            "reason": "referral:commission:debit",
                            "meta": {"to_uid": referrer_uid, "source_uid": uid},
                        })
                        ref_wallet["credits"] = ref_after
                        ledger.append({
                            "time": datetime.now(timezone.utc).isoformat(),
                            "uid": referrer_uid,
                            "before": ref_before,
                            "amount": commission,
                            "after": ref_after,
                            "reason": "referral:commission",
                            "meta": {
                                **meta,
                                "source_uid": uid,
                                "purchase_item": item,
                            },
                        })

                        commissions = db.setdefault("commissions", {})
                        commissions[referrer_uid] = (
                            commissions.get(referrer_uid, 0)
                            + commission
                        )

        return {
            "item": item,
            "uid": uid,
            "credits": buyer_after,
            "commission": commission,
        }

    return state_manager.atomic_update(mutate)


def record_stars_payment(
    uid,
    credits,
    stars_paid,
    currency,
    telegram_payment_charge_id,
    provider_payment_charge_id=None,
    referrer_uid=None,
    commission_rate=0.10,
    meta=None,
    provider_payment_charge_id_unavailable=False,
):
    """
    Atomic Telegram Stars payment authority.

    Idempotency key:
        telegram_payment_charge_id
    """

    uid = str(uid)
    credits = float(credits)
    stars_paid = int(stars_paid)
    currency = str(currency)
    charge_id = str(telegram_payment_charge_id or "").strip()
    provider_charge_id = (
        str(provider_payment_charge_id).strip()
        if provider_payment_charge_id
        else None
    )
    meta = meta or {}

    if credits <= 0:
        raise ValueError("INVALID_CREDITS")

    if stars_paid <= 0:
        raise ValueError("INVALID_STARS_AMOUNT")

    if not charge_id:
        raise ValueError("INVALID_CHARGE_ID")

    def mutate(db):
        from core import revenue_ledger

        users = db.get("users", {})
        transactions = db.get("transactions", [])
        if not isinstance(users, dict) or not isinstance(transactions, list):
            return {
                "status": "conflict",
                "uid": uid,
                "credits": 0,
                "credits_applied": 0,
                "charge_id": charge_id,
                "conflicting_fields": ["payment_state_shape"],
            }

        revenue_meta = {
            "kind": "telegram_stars_gross",
            "payment_meta": dict(meta or {}),
            "provider_charge_id": provider_charge_id,
        }
        revenue_conflicts = revenue_ledger.conflicting_fields_in_db(
            db,
            source="telegram_stars",
            amount=stars_paid,
            currency=currency,
            reference=charge_id,
            uid=uid,
            meta=revenue_meta,
        )
        if revenue_conflicts:
            return {
                "status": "conflict",
                "uid": uid,
                "credits": 0,
                "credits_applied": 0,
                "charge_id": charge_id,
                "conflicting_fields": [f"revenue.{field}" for field in revenue_conflicts],
            }

        # A charge ID is immutable. Exact replays are no-ops; conflicting
        # immutable payment fields must stop before any wallet/ledger change.
        for tx in transactions:
            if not isinstance(tx, dict):
                continue
            if str(tx.get("telegram_payment_charge_id", "")) != charge_id:
                continue

            expected = {
                "uid": uid,
                "credits": credits,
                "stars_paid": stars_paid,
                "currency": currency,
            }
            # Telegram getStarTransactions does not expose
            # provider_payment_charge_id. Ignore this comparison only when the
            # caller explicitly marks the field unavailable; direct payment
            # callbacks retain strict comparison by default.
            if not provider_payment_charge_id_unavailable:
                expected["provider_payment_charge_id"] = provider_charge_id
            conflicting_fields = []
            for field, expected_value in expected.items():
                actual = tx.get(field)
                if field == "uid":
                    matches = actual is not None and str(actual) == str(expected_value)
                elif field == "credits":
                    try:
                        actual_number = float(actual)
                        expected_number = float(expected_value)
                        matches = (
                            math.isfinite(actual_number)
                            and actual_number == expected_number
                        )
                    except (TypeError, ValueError, OverflowError):
                        matches = False
                elif field == "stars_paid":
                    try:
                        matches = (
                            not isinstance(actual, bool)
                            and int(actual) == int(expected_value)
                        )
                    except (TypeError, ValueError, OverflowError):
                        matches = False
                elif field == "provider_payment_charge_id":
                    actual_provider = (
                        str(actual).strip() if actual not in (None, "") else None
                    )
                    expected_provider = (
                        str(expected_value).strip()
                        if expected_value not in (None, "")
                        else None
                    )
                    matches = actual_provider == expected_provider
                else:
                    matches = (
                        actual is not None
                        and str(actual) == str(expected_value)
                    )

                if not matches:
                    conflicting_fields.append(field)

            if conflicting_fields:
                return {
                    "status": "conflict",
                    "uid": uid,
                    "credits": 0,
                    "credits_applied": 0,
                    "charge_id": charge_id,
                    "conflicting_fields": conflicting_fields,
                }

            revenue_result = revenue_ledger.record_in_db(
                db,
                source="telegram_stars",
                amount=stars_paid,
                currency=currency,
                reference=charge_id,
                uid=uid,
                meta=revenue_meta,
            )
            if revenue_result.get("status") == "conflict":
                return {
                    "status": "conflict",
                    "uid": uid,
                    "credits": 0,
                    "credits_applied": 0,
                    "charge_id": charge_id,
                    "conflicting_fields": [
                        f"revenue.{field}"
                        for field in revenue_result.get("conflicting_fields", [])
                    ],
                }

            return {
                "status": "duplicate",
                "uid": uid,
                "credits": 0,
                "credits_applied": 0,
                "charge_id": charge_id,
            }

        if uid not in users:
            raise Exception("USER_NOT_FOUND")

        revenue_result = revenue_ledger.record_in_db(
            db,
            source="telegram_stars",
            amount=stars_paid,
            currency=currency,
            reference=charge_id,
            uid=uid,
            meta=revenue_meta,
        )
        if revenue_result.get("status") == "conflict":
            return {
                "status": "conflict",
                "uid": uid,
                "credits": 0,
                "credits_applied": 0,
                "charge_id": charge_id,
                "conflicting_fields": [
                    f"revenue.{field}"
                    for field in revenue_result.get("conflicting_fields", [])
                ],
            }

        transactions = db.setdefault("transactions", [])
        user = users[uid]
        wallet = user.setdefault("wallet", {})

        before = wallet.get("credits", 0)
        after = before + credits
        wallet["credits"] = after

        now = datetime.now(timezone.utc).isoformat()

        transactions.append({
            "uid": uid,
            "credits": credits,
            "stars_paid": stars_paid,
            "currency": currency,
            "telegram_payment_charge_id": charge_id,
            "provider_payment_charge_id": provider_charge_id,
            "timestamp": now,
        })

        ledger = db.setdefault("ledger", [])

        ledger.append({
            "time": now,
            "uid": uid,
            "before": before,
            "amount": credits,
            "after": after,
            "reason": "payment:telegram_stars",
            "meta": {
                **meta,
                "charge_id": charge_id,
                "stars_paid": stars_paid,
                "currency": currency,
            },
        })

        commission = 0

        referrer_uid = (
                db.get("users", {})
                  .get(uid, {})
                  .get("referral", {})
                  .get("referred_by")
            )
        if referrer_uid:
            referrer_uid = str(referrer_uid)

            if referrer_uid != uid and referrer_uid in users:
                commission = round(
                    credits * float(commission_rate),
                    2
                )

                if commission > 0:
                    ref_user = users[referrer_uid]
                    ref_wallet_value = ref_user.get("wallet")
                    ref_wallet_is_valid = (
                        ref_wallet_value is None or isinstance(ref_wallet_value, dict)
                    )
                    ref_wallet = ref_wallet_value if isinstance(ref_wallet_value, dict) else {}

                    ref_before = ref_wallet.get("credits", 0)
                    treasury = users.get(TREASURY_UID)
                    treasury_wallet = (
                        treasury.get("wallet")
                        if isinstance(treasury, dict)
                        and isinstance(treasury.get("wallet"), dict)
                        else {}
                    )
                    try:
                        treasury_before = float(treasury_wallet.get("credits", 0) or 0)
                    except (TypeError, ValueError, OverflowError):
                        treasury_before = 0.0

                    # A Stars payment remains recorded, but an unfunded referral
                    # commission must not invent a recipient ledger balance.
                    if (
                        not ref_wallet_is_valid
                        or not math.isfinite(treasury_before)
                        or treasury_before < commission
                    ):
                        commission = 0
                    else:
                        if not isinstance(ref_wallet_value, dict):
                            ref_wallet = {}
                            ref_user["wallet"] = ref_wallet
                        ref_after = ref_before + commission
                        treasury_after = round(treasury_before - commission, 2)
                        treasury_wallet["credits"] = treasury_after
                        ledger.append({
                            "time": datetime.now(timezone.utc).isoformat(),
                            "uid": TREASURY_UID,
                            "before": treasury_before,
                            "amount": -commission,
                            "after": treasury_after,
                            "reason": "referral:commission:debit",
                            "meta": {"to_uid": referrer_uid, "source_uid": uid},
                        })
                        ref_wallet["credits"] = ref_after
                        ledger.append({
                            "time": now,
                            "uid": referrer_uid,
                            "before": ref_before,
                            "amount": commission,
                            "after": ref_after,
                            "reason": "referral:commission",
                            "meta": {
                                "source_uid": uid,
                                "charge_id": charge_id,
                            },
                        })

                        commissions = db.setdefault("commissions", {})
                        commissions[referrer_uid] = (
                            commissions.get(referrer_uid, 0)
                            + commission
                        )

        return {
            "status": "applied",
            "uid": uid,
            "credits": after,
            "commission": commission,
            "charge_id": charge_id,
        }

    return state_manager.atomic_update(mutate)


def submit_agent(uid, agent_name, reward=10, meta=None):
    """
    Atomic agent submission.

    One DB transaction:
    - creates submission
    - grants creator reward
    - writes immutable ledger entry
    """
    uid = str(uid)
    agent_name = str(agent_name).strip()
    reward = float(reward)
    meta = meta or {}

    if not agent_name:
        raise ValueError("INVALID_AGENT_NAME")

    if reward <= 0:
        raise ValueError("INVALID_REWARD")

    def mutate(db):
        users = db.setdefault("users", {})

        if uid not in users:
            raise ValueError("USER_NOT_FOUND")

        submissions = db.setdefault("agent_submissions", [])

        user = users[uid]
        wallet = user.setdefault("wallet", {})

        before = wallet.get("credits", 0)
        after = before + reward
        wallet["credits"] = after

        submission = {
            "uid": uid,
            "agent_name": agent_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        submissions.append(submission)

        db.setdefault("ledger", []).append({
            "time": datetime.now(timezone.utc).isoformat(),
            "uid": uid,
            "before": before,
            "amount": reward,
            "after": after,
            "reason": "agent:submission_reward",
            "meta": {
                **meta,
                "agent_name": agent_name,
            },
        })

        return {
            "submission": submission,
            "credits": after,
            "reward": reward,
        }

    return state_manager.atomic_update(mutate)


def approve_agent_submission(
    submission_id,
    reward=40,
    meta=None,
):
    """
    Atomic agent approval.

    One DB transaction:
    - verifies submission
    - adds marketplace entry
    - removes submission
    - rewards creator
    - writes immutable ledger
    """
    reward = float(reward)
    meta = meta or {}

    if reward <= 0:
        raise ValueError("INVALID_REWARD")

    def mutate(db):
        submissions = db.setdefault("agent_submissions", [])

        if (
            submission_id < 0
            or submission_id >= len(submissions)
        ):
            raise ValueError("SUBMISSION_NOT_FOUND")

        submission = submissions[submission_id]
        creator_uid = str(submission.get("uid"))
        agent_name = str(
            submission.get("agent_name", "")
        ).strip()

        if not creator_uid or not agent_name:
            raise ValueError("INVALID_SUBMISSION")

        users = db.setdefault("users", {})

        if creator_uid not in users:
            raise ValueError("USER_NOT_FOUND")

        marketplace = db.setdefault(
            "marketplace",
            []
        )

        now = datetime.now(timezone.utc).isoformat()

        marketplace.append({
            "name": agent_name,
            "creator": creator_uid,
            "approved_at": now,
        })

        user = users[creator_uid]
        wallet = user.setdefault("wallet", {})

        before = wallet.get("credits", 0)
        after = before + reward
        wallet["credits"] = after

        del submissions[submission_id]

        db.setdefault("ledger", []).append({
            "time": now,
            "uid": creator_uid,
            "before": before,
            "amount": reward,
            "after": after,
            "reason": "agent:approval_reward",
            "meta": {
                **meta,
                "agent_name": agent_name,
                "submission_id": submission_id,
            },
        })

        return {
            "creator_uid": creator_uid,
            "agent_name": agent_name,
            "credits": after,
            "reward": reward,
        }

    return state_manager.atomic_update(mutate)


def complete_task(
    uid,
    task_id,
    meta=None,
):
    """
    Atomic task completion authority.

    One DB transaction:
    - validates task
    - prevents duplicate completion
    - marks task completed by user
    - grants reward
    - records immutable ledger entry
    """

    uid = uid
    task_id = str(task_id)
    meta = meta or {}

    def mutate(db):
        tasks = db.setdefault("tasks", {})

        if task_id not in tasks:
            raise ValueError("TASK_NOT_FOUND")

        users = db.setdefault("users", {})

        if str(uid) not in users:
            raise ValueError("USER_NOT_FOUND")

        task = tasks[task_id]
        done_by = task.setdefault("done_by", [])

        if uid in done_by or str(uid) in [str(x) for x in done_by]:
            raise ValueError("TASK_ALREADY_COMPLETED")

        reward = task.get("reward", 0)

        if not isinstance(reward, (int, float)):
            raise ValueError("INVALID_TASK_REWARD")

        if reward < 0:
            raise ValueError("INVALID_TASK_REWARD")

        done_by.append(uid)

        task["status"] = "completed"
        task["progress"] = 100
        task["completed_at"] = datetime.now(timezone.utc).isoformat()
        task["completed_by"] = str(uid)

        result = {
            "status": "completed",
            "task_id": task_id,
            "uid": str(uid),
            "reward": reward,
        }

        if reward > 0:
            user = users[str(uid)]
            wallet = user.setdefault("wallet", {})

            before = wallet.get("credits", 0)
            after = before + reward
            wallet["credits"] = after

            now = datetime.now(timezone.utc).isoformat()

            db.setdefault("ledger", []).append({
                "time": now,
                "uid": str(uid),
                "before": before,
                "amount": reward,
                "after": after,
                "reason": "task:completion_reward",
                "meta": {
                    **meta,
                    "task_id": task_id,
                },
            })

            result["credits"] = after

        return result

    return state_manager.atomic_update(mutate)


def get_staked_safe(uid):
    import json
    from pathlib import Path
    db = json.loads(Path("state/db.json").read_text(encoding="utf-8"))
    user = db.get("users", {}).get(str(uid))
    if not user:
        return 0
    return user.get("wallet", {}).get("staked", 0)


def transfer_credits(
    sender_uid,
    recipient_uid,
    amount,
    idempotency_key=None,
    meta=None,
):
    """
    P2P credit transfer between registered users.

    Atomic, validated, and idempotent.
    """
    import json
    from datetime import datetime, timezone

    import state_manager

    sender_uid = str(sender_uid)
    recipient_uid = str(recipient_uid)
    amount = float(amount)

    if not math.isfinite(amount):
        raise ValueError("INVALID_TRANSFER_AMOUNT")
    if sender_uid == recipient_uid:
        raise ValueError("SELF_TRANSFER")
    if amount <= 0:
        raise ValueError("INVALID_TRANSFER_AMOUNT")
    if not idempotency_key:
        raise ValueError("INVALID_IDEMPOTENCY_KEY")

    def mutate(db):
        users = db.setdefault("users", {})

        sender = users.get(sender_uid)
        if not sender:
            raise ValueError("SENDER_NOT_FOUND")
        if isinstance(sender, dict) and sender.get("frozen") is True:
            raise ValueError("ACCOUNT_FROZEN")
        recipient = users.get(recipient_uid)
        if not recipient:
            raise ValueError("RECIPIENT_NOT_FOUND")

        sender_wallet = sender.setdefault("wallet", {})
        recipient_wallet = recipient.setdefault("wallet", {})

        sender_balance = float(sender_wallet.get("credits", 0))
        processed = db.setdefault("processed_transfers", {})
        if idempotency_key in processed:
            stored = processed[idempotency_key]
            if isinstance(stored, dict):
                old_transfer_id = str(stored.get("transfer_id") or "").strip()
                old_sender_uid = str(stored.get("sender_uid") or "").strip()
                old_recipient_uid = str(stored.get("recipient_uid") or "").strip()
                try:
                    old_amount = float(stored.get("amount"))
                except (TypeError, ValueError, OverflowError):
                    old_amount = float("nan")
            elif isinstance(stored, str) and stored.strip():
                # Backward compatibility for historical key -> transfer_id
                # records: reconstruct identity only from a consistent pair
                # of persisted ledger rows. Never guess from the new request.
                old_transfer_id = stored.strip()
                rows = [
                    row for row in db.get("ledger", [])
                    if isinstance(row, dict)
                    and isinstance(row.get("meta"), dict)
                    and str(row["meta"].get("transfer_id") or "") == old_transfer_id
                ]
                sent_rows = [row for row in rows if row.get("reason") == "p2p:transfer_sent"]
                received_rows = [row for row in rows if row.get("reason") == "p2p:transfer_received"]
                if len(sent_rows) != 1 or len(received_rows) != 1:
                    raise ValueError("LEGACY_TRANSFER_IDENTITY_UNKNOWN")
                sent, received = sent_rows[0], received_rows[0]
                sent_meta, received_meta = sent["meta"], received["meta"]
                old_sender_uid = str(sent.get("uid") or "")
                old_recipient_uid = str(sent_meta.get("recipient_uid") or "")
                try:
                    sent_amount = float(sent.get("amount"))
                    received_amount = float(received.get("amount"))
                    sent_before = float(sent.get("before"))
                    sent_after = float(sent.get("after"))
                    received_before = float(received.get("before"))
                    received_after = float(received.get("after"))
                    old_amount = abs(sent_amount)
                    old_recipient_uid_row = str(received.get("uid") or "")
                    old_sender_uid_receipt = str(received_meta.get("sender_uid") or "")
                except (TypeError, ValueError, OverflowError):
                    raise ValueError("LEGACY_TRANSFER_IDENTITY_UNKNOWN") from None
                if (
                    not old_sender_uid
                    or not old_recipient_uid
                    or old_recipient_uid_row != old_recipient_uid
                    or old_sender_uid_receipt != old_sender_uid
                    or sent_amount >= 0
                    or received_amount <= 0
                    or not all(math.isfinite(x) for x in (
                        sent_amount, received_amount, sent_before, sent_after,
                        received_before, received_after,
                    ))
                    or abs(received_amount - old_amount) > 1e-9
                    or abs((sent_before + sent_amount) - sent_after) > 1e-9
                    or abs((received_before + received_amount) - received_after) > 1e-9
                ):
                    raise ValueError("LEGACY_TRANSFER_IDENTITY_UNKNOWN")
            else:
                raise ValueError("LEGACY_TRANSFER_IDENTITY_UNKNOWN")

            if (
                not old_transfer_id
                or not old_sender_uid
                or not old_recipient_uid
                or not math.isfinite(old_amount)
                or old_amount <= 0
            ):
                raise ValueError("LEGACY_TRANSFER_IDENTITY_UNKNOWN")
            if (
                old_sender_uid != sender_uid
                or old_recipient_uid != recipient_uid
                or old_amount != amount
            ):
                raise ValueError("IDEMPOTENCY_KEY_CONFLICT")
            return {
                "status": "duplicate",
                "transfer_id": old_transfer_id,
                "amount": old_amount,
                "recipient_uid": old_recipient_uid,
                "sender_balance": sender_balance,
            }

        if sender_balance < amount:
            raise ValueError("INSUFFICIENT_CREDITS")

        transfer_id = f"TRANSFER-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"

        sender_wallet["credits"] = sender_balance - amount
        recipient_balance = float(recipient_wallet.get("credits", 0))
        recipient_wallet["credits"] = recipient_balance + amount

        now = datetime.now(timezone.utc).isoformat()

        sender_meta = dict(meta or {})
        sender_meta.update({
            "transfer_id": transfer_id,
            "recipient_uid": recipient_uid,
        })

        recipient_meta = dict(meta or {})
        recipient_meta.update({
            "transfer_id": transfer_id,
            "sender_uid": sender_uid,
        })

        ledger = db.setdefault("ledger", [])
        ledger.append({
            "time": now,
            "uid": sender_uid,
            "before": sender_balance,
            "amount": -amount,
            "after": sender_balance - amount,
            "reason": "p2p:transfer_sent",
            "meta": sender_meta,
        })
        ledger.append({
            "time": now,
            "uid": recipient_uid,
            "before": recipient_balance,
            "amount": amount,
            "after": recipient_balance + amount,
            "reason": "p2p:transfer_received",
            "meta": recipient_meta,
        })

        processed[idempotency_key] = {
            "transfer_id": transfer_id,
            "sender_uid": sender_uid,
            "recipient_uid": recipient_uid,
            "amount": amount,
        }

        return {
            "status": "completed",
            "transfer_id": transfer_id,
            "amount": amount,
            "recipient_uid": recipient_uid,
            "sender_balance": sender_balance - amount,
        }

    return state_manager.atomic_update(mutate)
