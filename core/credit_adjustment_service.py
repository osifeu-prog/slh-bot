"""Owner-only, fail-closed reversal for a verified invalid BNB self-transfer.

This module is intentionally not wired to a bot command or API route. It
revalidates the on-chain transaction, then appends a compensating ledger entry
without rewriting the original deposit record. Production use requires a
separate reviewed release and explicit operational authorization.
"""
from __future__ import annotations

import math
import os
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import state_manager
from core.authority import is_owner
from core.bnb_gate import _effective_config, bnb_deposits_open
from core.bsc_address_policy import is_quarantined_bsc_address
from web3 import Web3


_TX_HASH_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")
_CORRECTION_REASON = "accounting:invalid_bnb_deposit_reversal"
_CREDITS_PER_BNB = Decimal("1000")
_WEI_PER_BNB = Decimal(10**18)


def _decimal(value, error_code):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(error_code) from None
    if not result.is_finite():
        raise ValueError(error_code)
    return result


def _normalise_hash(value):
    if value is None:
        return ""
    if hasattr(value, "hex") and not isinstance(value, str):
        value = value.hex()
    result = str(value).strip().lower()
    if result and not result.startswith("0x"):
        result = "0x" + result
    return result


def _exact_nonnegative_int(value):
    """Parse persisted integer metadata without truncating floats or accepting booleans."""
    if isinstance(value, bool):
        raise ValueError("INVALID_INTEGER_METADATA")
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        return int(value)
    raise ValueError("INVALID_INTEGER_METADATA")


def _verify_self_transfer_for_reversal(tx_hash, db):
    """Read-only live BSC verification; only a confirmed treasury self-transfer qualifies."""
    cfg = _effective_config(db)
    rpc = str(cfg.get("rpc") or "").strip()
    treasury = str(cfg.get("treasury_wallet") or "").strip()
    canonical = str(os.getenv("SLH_BSC_CANONICAL_TREASURY", "")).strip()

    if int(cfg.get("chain_id") or 0) != 56:
        raise ValueError("BSC_CONFIGURED_CHAIN_ID_NOT_56")
    if not rpc:
        raise ValueError("BSC_RPC_MISSING")
    if not treasury or not canonical or treasury.lower() != canonical.lower():
        raise ValueError("BNB_CANONICAL_TREASURY_MISMATCH")
    if is_quarantined_bsc_address(treasury):
        raise ValueError("BSC_TREASURY_QUARANTINED")

    try:
        w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 5}))
        if int(w3.eth.chain_id) != 56:
            raise ValueError("BSC_CHAIN_ID_NOT_56")
        tx = w3.eth.get_transaction(tx_hash)
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        actual_hash = _normalise_hash(tx.get("hash"))
        if actual_hash != tx_hash.lower():
            raise ValueError("BNB_TX_HASH_MISMATCH")
        if not receipt or int(receipt.get("status", 0)) != 1:
            raise ValueError("BNB_TX_NOT_SUCCESSFUL")

        sender = str(tx.get("from") or "").strip()
        recipient = str(tx.get("to") or "").strip()
        if not sender or not recipient:
            raise ValueError("BNB_TX_ADDRESSES_MISSING")
        if sender.lower() != treasury.lower() or recipient.lower() != treasury.lower():
            raise ValueError("BNB_TX_NOT_TREASURY_SELF_TRANSFER")

        block = int(receipt.get("blockNumber") or 0)
        latest_block = int(w3.eth.block_number)
        confirmations = max(0, latest_block - block + 1)
        required = int(cfg.get("confirmations") or 15)
        if block <= 0 or required < 1 or confirmations < required:
            raise ValueError("BNB_TX_CONFIRMATIONS_INSUFFICIENT")

        amount_wei = int(tx.get("value") or 0)
        if amount_wei <= 0:
            raise ValueError("BNB_TX_AMOUNT_INVALID")
        return {
            "tx_hash": tx_hash.lower(),
            "chain_id": 56,
            "receipt_status": 1,
            "from": sender,
            "to": recipient,
            "treasury": treasury,
            "amount_wei": amount_wei,
            "block": block,
            "confirmations": confirmations,
            "required_confirmations": required,
        }
    except ValueError:
        raise
    except Exception:
        raise ValueError("BNB_FORENSIC_RPC_FAILED") from None



def _existing_reversal_result(db, *, uid, tx_hash, correction_key, source_key):
    """Return an idempotent result only when ledger, wallet, and audit agree."""
    ledger = db.get("ledger", [])
    if not isinstance(ledger, list):
        raise ValueError("LEDGER_UNREADABLE")

    corrections = [
        row for row in ledger
        if isinstance(row, dict)
        and isinstance(row.get("meta"), dict)
        and row["meta"].get("idempotency_key") == correction_key
    ]
    if not corrections:
        return None
    if len(corrections) != 1:
        raise ValueError("CREDIT_ADJUSTMENT_IDEMPOTENCY_CONFLICT")

    prior = corrections[0]
    meta = prior.get("meta")
    source_matches = [
        (index, row) for index, row in enumerate(ledger)
        if isinstance(row, dict)
        and str(row.get("uid")) == uid
        and row.get("reason") == "bnb:deposit"
        and isinstance(row.get("meta"), dict)
        and str(row["meta"].get("tx_hash") or "").lower() == tx_hash.lower()
        and row["meta"].get("idempotency_key") == source_key
    ]
    if len(source_matches) != 1:
        raise ValueError("CREDIT_ADJUSTMENT_IDEMPOTENCY_CONFLICT")
    source_index, source = source_matches[0]
    source_meta = source["meta"]

    # A repeated call must independently re-check the recorded treasury identity
    # and the original credit calculation; matching two mutable ledger fields is
    # not sufficient proof of a valid reversal.
    cfg = _effective_config(db)
    configured_treasury = str(cfg.get("treasury_wallet") or "").strip().lower()
    canonical_treasury = str(os.getenv("SLH_BSC_CANONICAL_TREASURY", "")).strip().lower()
    if (
        not canonical_treasury
        or configured_treasury != canonical_treasury
        or str(source_meta.get("from") or "").strip().lower() != canonical_treasury
        or str(source_meta.get("to") or "").strip().lower() != canonical_treasury
    ):
        raise ValueError("CREDIT_ADJUSTMENT_IDEMPOTENCY_CONFLICT")

    audits = db.get("credit_adjustment_audit", [])
    if not isinstance(audits, list):
        raise ValueError("CREDIT_ADJUSTMENT_AUDIT_UNREADABLE")
    matching_audits = [
        row for row in audits
        if isinstance(row, dict)
        and row.get("correction_idempotency_key") == correction_key
    ]
    if len(matching_audits) != 1:
        raise ValueError("CREDIT_ADJUSTMENT_IDEMPOTENCY_CONFLICT")
    audit = matching_audits[0]

    try:
        amount_wei = _exact_nonnegative_int(meta.get("amount_wei"))
        source_amount_wei = _exact_nonnegative_int(source_meta.get("bnb_amount_wei"))
        meta_block = _exact_nonnegative_int(meta.get("block"))
        audit_block = _exact_nonnegative_int(audit.get("block"))
        meta_confirmations = _exact_nonnegative_int(meta.get("confirmations"))
        audit_confirmations = _exact_nonnegative_int(audit.get("confirmations"))
        meta_required_confirmations = _exact_nonnegative_int(meta.get("required_confirmations"))
        audit_required_confirmations = _exact_nonnegative_int(audit.get("required_confirmations"))
        source_amount = _decimal(source.get("amount"), "SOURCE_AMOUNT_INVALID")
        source_before = _decimal(source.get("before"), "SOURCE_BALANCE_INVALID")
        source_after = _decimal(source.get("after"), "SOURCE_BALANCE_INVALID")
        expected_source_amount = Decimal(source_amount_wei) * _CREDITS_PER_BNB / _WEI_PER_BNB
        expected_source_amount = Decimal(str(float(expected_source_amount)))
        if (
            source_amount_wei <= 0
            or source_amount != expected_source_amount
            or float(source_before) + float(source_amount) != float(source_after)
        ):
            raise ValueError("SOURCE_CREDITS_DO_NOT_MATCH_ONCHAIN_AMOUNT")
        correction_before = _decimal(prior.get("before"), "REVERSAL_BEFORE_INVALID")
        correction_amount = _decimal(prior.get("amount"), "REVERSAL_AMOUNT_INVALID")
        correction_after = _decimal(prior.get("after"), "REVERSAL_AFTER_INVALID")
        nominal = _decimal(meta.get("nominal_credits_reversed"), "REVERSAL_NOMINAL_INVALID")
        audit_before = _decimal(audit.get("balance_before"), "REVERSAL_AUDIT_INVALID")
        audit_after = _decimal(audit.get("balance_after"), "REVERSAL_AUDIT_INVALID")
        audit_amount = _decimal(audit.get("amount"), "REVERSAL_AUDIT_INVALID")
        audit_nominal = _decimal(audit.get("nominal_credits_reversed"), "REVERSAL_AUDIT_INVALID")
        balance = _decimal(
            db.get("users", {}).get(uid, {}).get("wallet", {}).get("credits"),
            "REVERSAL_WALLET_INVALID",
        )
    except (AttributeError, TypeError, ValueError):
        raise ValueError("CREDIT_ADJUSTMENT_IDEMPOTENCY_CONFLICT") from None

    expected_meta = (
        str(prior.get("uid")) == uid
        and prior.get("reason") == _CORRECTION_REASON
        and str(meta.get("tx_hash") or "").lower() == tx_hash.lower()
        and meta.get("source_idempotency_key") == source_key
        and meta.get("source_reason") == "bnb:deposit"
        and meta.get("source_ledger_index") == source_index
        and meta.get("gate_remained_closed") is True
        and meta.get("chain_id") == 56
        and str(meta.get("treasury") or "").strip().lower() == canonical_treasury
        and str(meta.get("from") or "").strip().lower() == canonical_treasury
        and str(meta.get("to") or "").strip().lower() == canonical_treasury
        and amount_wei > 0
        and amount_wei == source_amount_wei
        and meta_block > 0
        and meta_block == audit_block
        and meta_confirmations > 0
        and meta_confirmations == audit_confirmations
        and meta_required_confirmations > 0
        and meta_required_confirmations == audit_required_confirmations
        and meta_confirmations >= meta_required_confirmations
        and str(meta.get("from") or "").lower() == str(source_meta.get("from") or "").lower()
        and str(meta.get("to") or "").lower() == str(source_meta.get("to") or "").lower()
    )
    expected_audit = (
        audit.get("event") == "INVALID_BNB_SELF_TRANSFER_REVERSED"
        and str(audit.get("uid")) == uid
        and str(audit.get("tx_hash") or "").lower() == tx_hash.lower()
        and audit.get("source_idempotency_key") == source_key
        and audit.get("gate_remained_closed") is True
        and audit.get("chain_id") == 56
        and audit.get("block") == meta_block
        and audit.get("confirmations") == meta_confirmations
        and audit.get("required_confirmations") == meta_required_confirmations
        and audit_before == correction_before
        and audit_after == correction_after
        and audit_amount == correction_amount
        and audit_nominal == nominal
    )
    if not (
        expected_meta
        and expected_audit
        and correction_before == source_after
        and correction_after == source_before
        and nominal == source_amount
        and correction_amount == Decimal(str(float(source_before) - float(source_after)))
        and balance == correction_after
        and abs(float(correction_before) + float(correction_amount) - float(correction_after)) <= 1e-9
    ):
        raise ValueError("CREDIT_ADJUSTMENT_IDEMPOTENCY_CONFLICT")

    return {
        "status": "ALREADY_REVERSED",
        "uid": uid,
        "tx_hash": tx_hash.lower(),
        "correction_idempotency_key": correction_key,
        "balance_after": prior.get("after"),
    }

def reverse_invalid_bnb_deposit(
    *,
    actor_uid,
    uid,
    tx_hash,
    expected_current_balance,
    now=None,
):
    """Append one audited credit reversal after live proof and strict stale-state checks.

    No original ledger row is deleted or edited. This callable is deliberately
    not exposed through a command/API handler. Every failure is fail-closed.
    """
    actor_uid = str(actor_uid or "").strip()
    uid = str(uid or "").strip()
    tx_hash = str(tx_hash or "").strip()
    if not is_owner(actor_uid):
        raise PermissionError("OWNER_ONLY")
    if not uid:
        raise ValueError("INVALID_UID")
    if not _TX_HASH_RE.fullmatch(tx_hash):
        raise ValueError("INVALID_TX_HASH")
    if bnb_deposits_open():
        raise ValueError("BNB_GATE_MUST_REMAIN_CLOSED")

    expected_balance = _decimal(expected_current_balance, "INVALID_EXPECTED_BALANCE")
    initial_db = state_manager.load_db()
    if not isinstance(initial_db, dict):
        raise ValueError("DB_UNREADABLE")

    correction_key = f"accounting:reversal:{tx_hash.lower()}"
    source_key = f"bnb:deposit:{tx_hash.lower()}"

    initial_ledger = initial_db.get("ledger", [])
    if not isinstance(initial_ledger, list):
        raise ValueError("LEDGER_UNREADABLE")
    existing_result = _existing_reversal_result(
        initial_db,
        uid=uid,
        tx_hash=tx_hash,
        correction_key=correction_key,
        source_key=source_key,
    )
    if existing_result is not None:
        return existing_result

    # Chain proof is obtained independently of any caller-supplied evidence.
    proof = _verify_self_transfer_for_reversal(tx_hash, initial_db)
    if bnb_deposits_open():
        raise ValueError("BNB_GATE_MUST_REMAIN_CLOSED")

    source_matches = [
        (index, row) for index, row in enumerate(initial_ledger)
        if isinstance(row, dict)
        and str(row.get("uid")) == uid
        and row.get("reason") == "bnb:deposit"
        and isinstance(row.get("meta"), dict)
        and str(row["meta"].get("tx_hash") or "").lower() == tx_hash.lower()
        and row["meta"].get("idempotency_key") == source_key
    ]
    if len(source_matches) != 1:
        raise ValueError("SOURCE_DEPOSIT_NOT_UNIQUE")
    source_index, source = source_matches[0]
    meta = source["meta"]

    try:
        source_amount = _decimal(source.get("amount"), "SOURCE_AMOUNT_INVALID")
        source_before = _decimal(source.get("before"), "SOURCE_BALANCE_INVALID")
        source_after = _decimal(source.get("after"), "SOURCE_BALANCE_INVALID")
        source_wei = int(meta.get("bnb_amount_wei") or 0)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("SOURCE_DEPOSIT_INVALID") from None

    expected_credits = Decimal(source_wei) * _CREDITS_PER_BNB / _WEI_PER_BNB
    # The canonical deposit service intentionally crosses the existing float
    # ledger boundary. Compare with that exact conversion, including its
    # documented binary-float rounding, rather than rejecting valid deposits
    # whose wei amount produces a non-terminating decimal Credits display.
    if source_wei <= 0 or source_amount != Decimal(str(float(expected_credits))):
        raise ValueError("SOURCE_CREDITS_DO_NOT_MATCH_ONCHAIN_AMOUNT")
    if source_wei != int(proof["amount_wei"]):
        raise ValueError("SOURCE_AMOUNT_DOES_NOT_MATCH_ONCHAIN")
    if str(meta.get("from") or "").lower() != proof["from"].lower():
        raise ValueError("SOURCE_SENDER_DOES_NOT_MATCH_ONCHAIN")
    if str(meta.get("to") or "").lower() != proof["to"].lower():
        raise ValueError("SOURCE_RECEIVER_DOES_NOT_MATCH_ONCHAIN")
    # Match the canonical float-backed ledger arithmetic exactly; Decimal
    # string addition can differ from a valid stored float by a few ULPs.
    if float(source_before) + float(source_amount) != float(source_after):
        raise ValueError("SOURCE_LEDGER_ARITHMETIC_INVALID")

    timestamp = (
        now.astimezone(timezone.utc).isoformat()
        if isinstance(now, datetime) and now.tzinfo
        else now.replace(tzinfo=timezone.utc).isoformat()
        if isinstance(now, datetime)
        else datetime.now(timezone.utc).isoformat()
    )

    def mutate(db):
        if not isinstance(db, dict):
            raise ValueError("DB_UNREADABLE")
        if bnb_deposits_open():
            raise ValueError("BNB_GATE_MUST_REMAIN_CLOSED")
        ledger = db.get("ledger", [])
        if not isinstance(ledger, list):
            raise ValueError("LEDGER_UNREADABLE")

        existing_result = _existing_reversal_result(
            db,
            uid=uid,
            tx_hash=tx_hash,
            correction_key=correction_key,
            source_key=source_key,
        )
        if existing_result is not None:
            return existing_result

        live_matches = [
            (index, row) for index, row in enumerate(ledger)
            if isinstance(row, dict)
            and str(row.get("uid")) == uid
            and row.get("reason") == "bnb:deposit"
            and isinstance(row.get("meta"), dict)
            and str(row["meta"].get("tx_hash") or "").lower() == tx_hash.lower()
            and row["meta"].get("idempotency_key") == source_key
        ]
        if len(live_matches) != 1:
            raise ValueError("SOURCE_DEPOSIT_NOT_UNIQUE")
        live_index, live_source = live_matches[0]
        if live_index != source_index or live_source != source:
            raise ValueError("SOURCE_DEPOSIT_CHANGED_DURING_VERIFICATION")

        # No new ledger activity for this account is permitted between preview
        # and application. This intentionally refuses to guess at stale balances.
        later_owner_rows = [
            row for row in ledger[live_index + 1:]
            if isinstance(row, dict) and str(row.get("uid")) == uid
        ]
        if later_owner_rows:
            raise ValueError("OWNER_LEDGER_CHANGED_AFTER_SOURCE_DEPOSIT")

        users = db.get("users", {})
        user = users.get(uid) if isinstance(users, dict) else None
        wallet = user.get("wallet") if isinstance(user, dict) else None
        if not isinstance(wallet, dict):
            raise ValueError("WALLET_NOT_FOUND")
        current_balance = _decimal(wallet.get("credits", 0), "CURRENT_BALANCE_INVALID")
        if current_balance != expected_balance or current_balance != source_after:
            raise ValueError("CURRENT_BALANCE_MISMATCH")
        if current_balance < source_amount:
            raise ValueError("INSUFFICIENT_CREDITS_FOR_REVERSAL")

        audits = db.get("credit_adjustment_audit", [])
        if not isinstance(audits, list):
            raise ValueError("CREDIT_ADJUSTMENT_AUDIT_UNREADABLE")
        if any(
            isinstance(row, dict)
            and row.get("correction_idempotency_key") == correction_key
            for row in audits
        ):
            raise ValueError("CREDIT_ADJUSTMENT_AUDIT_IDEMPOTENCY_CONFLICT")

        # Restore the exact recorded pre-credit balance. Because the legacy
        # ledger uses floats, derive its numeric delta from the two stored
        # balances so before + amount == after remains exact in binary float.
        after = source_before
        reversal_amount = float(after) - float(current_balance)
        # Legacy Credits are stored as binary floats; require ledger arithmetic
        # to reconcile within a sub-nanocredit tolerance, not bitwise equality.
        if abs((float(current_balance) + reversal_amount) - float(after)) > 1e-9:
            raise ValueError("REVERSAL_FLOAT_ARITHMETIC_INVALID")
        audits = db.setdefault("credit_adjustment_audit", [])
        wallet["credits"] = float(after)
        reversal = {
            "time": timestamp,
            "uid": uid,
            "before": float(current_balance),
            "amount": reversal_amount,
            "after": float(after),
            "reason": _CORRECTION_REASON,
            "meta": {
                "idempotency_key": correction_key,
                "source_idempotency_key": source_key,
                "source_reason": "bnb:deposit",
                "source_ledger_index": live_index,
                "tx_hash": tx_hash.lower(),
                "actor_uid": actor_uid,
                "adjustment_basis": "verified BSC transaction sender and receiver both equal canonical treasury",
                "nominal_credits_reversed": float(source_amount),
                "chain_id": proof["chain_id"],
                "block": proof["block"],
                "confirmations": proof["confirmations"],
                "required_confirmations": proof["required_confirmations"],
                "amount_wei": proof["amount_wei"],
                "treasury": proof["treasury"],
                "from": proof["from"],
                "to": proof["to"],
                "gate_remained_closed": True,
            },
        }
        ledger.append(reversal)
        audits.append({
            "event": "INVALID_BNB_SELF_TRANSFER_REVERSED",
            "time": timestamp,
            "actor_uid": actor_uid,
            "uid": uid,
            "tx_hash": tx_hash.lower(),
            "source_idempotency_key": source_key,
            "correction_idempotency_key": correction_key,
            "amount": reversal_amount,
            "nominal_credits_reversed": float(source_amount),
            "balance_before": float(current_balance),
            "balance_after": float(after),
            "chain_id": proof["chain_id"],
            "block": proof["block"],
            "confirmations": proof["confirmations"],
            "required_confirmations": proof["required_confirmations"],
            "gate_remained_closed": True,
        })
        return {
            "status": "APPLIED",
            "uid": uid,
            "tx_hash": tx_hash.lower(),
            "amount_reversed": float(source_amount),
            "balance_before": float(current_balance),
            "balance_after": float(after),
            "correction_idempotency_key": correction_key,
            "source_ledger_index": live_index,
            "gate_remained_closed": True,
        }

    return state_manager.atomic_update(mutate)
