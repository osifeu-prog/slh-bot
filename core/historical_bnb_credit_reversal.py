"""Forensic-only correction for a credited BNB self-transfer to a non-Treasury wallet.

This path is intentionally not wired to a Telegram command or HTTP route.
It appends an audited compensating ledger entry, preserves all historical rows,
and refuses to run unless the BNB gate remains closed. A draft release is not
authorization to execute any correction in production.
"""
from __future__ import annotations

import math
import os
import re
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import state_manager
from core.authority import is_owner
from core.bnb_gate import _effective_config, bnb_deposits_open
from core.bsc_address_policy import is_quarantined_bsc_address
from web3 import Web3


_TX_HASH_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")
_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_CORRECTION_REASON = "accounting:invalid_bnb_deposit_reversal"
_CORRECTION_EVENT = "INVALID_BNB_NON_TREASURY_SELF_TRANSFER_REVERSED"
_ADJUSTMENT_KIND = "verified_invalid_nontreasury_bnb_self_transfer"
_CREDITS_PER_BNB = Decimal("1000")
_WEI_PER_BNB = Decimal(10**18)
_TOLERANCE = 1e-9


def _decimal(value, error_code):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(error_code) from None
    if not result.is_finite():
        raise ValueError(error_code)
    return result


def _exact_int(value, error_code):
    if isinstance(value, bool):
        raise ValueError(error_code)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"-?[0-9]+", value):
        return int(value)
    raise ValueError(error_code)


def _normalise_hash(value):
    if value is None:
        return ""
    if hasattr(value, "hex") and not isinstance(value, str):
        value = value.hex()
    value = str(value).strip().lower()
    if value and not value.startswith("0x"):
        value = "0x" + value
    return value


def _require_operator_gate_flag_closed():
    # A historically blocked audit can mask an operator flag that is still "1".
    # Do not repair the last blocker and thereby accidentally make BNB effective-open.
    if os.getenv("BNB_DEPOSITS_OPEN", "0").strip() == "1":
        raise ValueError("BNB_OPERATOR_FLAG_MUST_BE_CLOSED")


def _treasury_context(db):
    if not isinstance(db, dict):
        raise ValueError("DB_UNREADABLE")
    cfg = _effective_config(db)
    try:
        chain_id = _exact_int(cfg.get("chain_id"), "BSC_CONFIGURED_CHAIN_ID_INVALID")
        required = _exact_int(cfg.get("confirmations") or 15, "BNB_CONFIRMATION_POLICY_INVALID")
    except ValueError:
        raise
    rpc = str(cfg.get("rpc") or "").strip()
    treasury = str(cfg.get("treasury_wallet") or "").strip()
    canonical = str(os.getenv("SLH_BSC_CANONICAL_TREASURY") or "").strip()
    if chain_id != 56:
        raise ValueError("BSC_CONFIGURED_CHAIN_ID_NOT_56")
    if not rpc:
        raise ValueError("BSC_RPC_MISSING")
    if not _ADDRESS_RE.fullmatch(treasury) or not _ADDRESS_RE.fullmatch(canonical):
        raise ValueError("BNB_CANONICAL_TREASURY_MISMATCH")
    if treasury.lower() != canonical.lower():
        raise ValueError("BNB_CANONICAL_TREASURY_MISMATCH")
    if is_quarantined_bsc_address(treasury):
        raise ValueError("BSC_TREASURY_QUARANTINED")
    if required < 1:
        raise ValueError("BNB_CONFIRMATION_POLICY_INVALID")
    return {
        "rpc": rpc,
        "chain_id": chain_id,
        "treasury": treasury,
        "canonical_treasury": canonical,
        "required_confirmations": required,
    }


def _resolve_unique_user_bsc_wallet(uid, db, treasury):
    bindings = db.get("wallet_bindings")
    if not isinstance(bindings, dict):
        raise ValueError("BNB_WALLET_BINDINGS_UNVERIFIED")

    matching_user = []
    all_bsc_addresses = []
    for binding in bindings.values():
        if not isinstance(binding, dict):
            raise ValueError("BNB_WALLET_BINDINGS_UNVERIFIED")
        chain = str(binding.get("chain") or "").strip().lower()
        if not chain:
            raise ValueError("BNB_WALLET_BINDINGS_UNVERIFIED")
        if chain != "bsc":
            continue
        address = str(binding.get("address") or "").strip()
        if not _ADDRESS_RE.fullmatch(address) or is_quarantined_bsc_address(address):
            raise ValueError("BNB_WALLET_BINDINGS_UNVERIFIED")
        binding_uid = str(binding.get("uid") or "").strip()
        all_bsc_addresses.append((address.lower(), binding_uid))
        if binding_uid == str(uid):
            matching_user.append(address)

    if len(matching_user) != 1:
        raise ValueError("BNB_OWNER_WALLET_NOT_UNIQUE")
    wallet = matching_user[0]
    if wallet.lower() == str(treasury).lower():
        raise ValueError("BNB_WALLET_ALIASES_TREASURY_NOT_THIS_CASE")
    if sum(1 for address, _ in all_bsc_addresses if address == wallet.lower()) != 1:
        raise ValueError("BNB_WALLET_BINDING_ADDRESS_NOT_UNIQUE")
    return wallet


def _verify_non_treasury_self_transfer(uid, tx_hash, db):
    context = _treasury_context(db)
    wallet = _resolve_unique_user_bsc_wallet(uid, db, context["treasury"])

    try:
        w3 = Web3(Web3.HTTPProvider(context["rpc"], request_kwargs={"timeout": 5}))
        if int(w3.eth.chain_id) != 56:
            raise ValueError("BSC_CHAIN_ID_NOT_56")
        tx = w3.eth.get_transaction(tx_hash)
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        if _normalise_hash(tx.get("hash")) != tx_hash.lower():
            raise ValueError("BNB_TX_HASH_MISMATCH")
        if not receipt or int(receipt.get("status", 0)) != 1:
            raise ValueError("BNB_TX_NOT_SUCCESSFUL")
        sender = str(tx.get("from") or "").strip()
        recipient = str(tx.get("to") or "").strip()
        if not sender or not recipient:
            raise ValueError("BNB_TX_ADDRESSES_MISSING")
        if sender.lower() != wallet.lower() or recipient.lower() != wallet.lower():
            raise ValueError("BNB_TX_NOT_BOUND_WALLET_SELF_TRANSFER")
        if recipient.lower() == context["treasury"].lower():
            raise ValueError("BNB_TX_RECIPIENT_IS_TREASURY")
        block = int(receipt.get("blockNumber") or 0)
        latest_block = int(w3.eth.block_number)
        confirmations = max(0, latest_block - block + 1)
        amount_wei = _exact_int(tx.get("value"), "BNB_TX_AMOUNT_INVALID")
        if block <= 0 or amount_wei <= 0:
            raise ValueError("BNB_TX_AMOUNT_OR_BLOCK_INVALID")
        if confirmations < context["required_confirmations"]:
            raise ValueError("BNB_TX_CONFIRMATIONS_INSUFFICIENT")
    except ValueError:
        raise
    except Exception:
        raise ValueError("BNB_FORENSIC_RPC_FAILED") from None

    return {
        "tx_hash": tx_hash.lower(),
        "chain_id": 56,
        "receipt_status": 1,
        "from": sender,
        "to": recipient,
        "treasury": context["treasury"],
        "bound_wallet": wallet,
        "amount_wei": amount_wei,
        "block": block,
        "confirmations": confirmations,
        "required_confirmations": context["required_confirmations"],
    }


def _source_and_history(db, uid, tx_hash):
    ledger = db.get("ledger")
    if not isinstance(ledger, list):
        raise ValueError("LEDGER_UNREADABLE")
    source_key = f"bnb:deposit:{tx_hash.lower()}"
    source_matches = [
        (i, row) for i, row in enumerate(ledger)
        if isinstance(row, dict)
        and str(row.get("uid") or "") == str(uid)
        and row.get("reason") == "bnb:deposit"
        and isinstance(row.get("meta"), dict)
        and _normalise_hash(row["meta"].get("tx_hash")) == tx_hash.lower()
        and str(row["meta"].get("idempotency_key") or "") == source_key
    ]
    tx_deposit_matches = [
        i for i, row in enumerate(ledger)
        if isinstance(row, dict)
        and row.get("reason") == "bnb:deposit"
        and isinstance(row.get("meta"), dict)
        and _normalise_hash(row["meta"].get("tx_hash")) == tx_hash.lower()
    ]
    source_key_matches = [
        i for i, row in enumerate(ledger)
        if isinstance(row, dict)
        and isinstance(row.get("meta"), dict)
        and str(row["meta"].get("idempotency_key") or "") == source_key
    ]
    if len(source_matches) != 1 or len(tx_deposit_matches) != 1 or len(source_key_matches) != 1:
        raise ValueError("SOURCE_DEPOSIT_NOT_UNIQUE")
    source_index, source = source_matches[0]
    meta = source["meta"]

    try:
        source_amount = _decimal(source.get("amount"), "SOURCE_AMOUNT_INVALID")
        source_before = _decimal(source.get("before"), "SOURCE_BEFORE_INVALID")
        source_after = _decimal(source.get("after"), "SOURCE_AFTER_INVALID")
        source_wei = _exact_int(meta.get("bnb_amount_wei"), "SOURCE_AMOUNT_WEI_INVALID")
    except ValueError:
        raise ValueError("SOURCE_DEPOSIT_INVALID") from None
    if source_wei <= 0:
        raise ValueError("SOURCE_DEPOSIT_INVALID")
    expected_credits = Decimal(source_wei) * _CREDITS_PER_BNB / _WEI_PER_BNB
    expected_credits = Decimal(str(float(expected_credits)))
    if source_amount != expected_credits:
        raise ValueError("SOURCE_CREDITS_DO_NOT_MATCH_ONCHAIN_AMOUNT")
    if not math.isclose(float(source_before) + float(source_amount), float(source_after),
                        rel_tol=0, abs_tol=_TOLERANCE):
        raise ValueError("SOURCE_LEDGER_ARITHMETIC_INVALID")

    account_rows = [
        (i, row) for i, row in enumerate(ledger)
        if isinstance(row, dict) and str(row.get("uid") or "") == str(uid)
    ]
    source_positions = [pos for pos, (i, _) in enumerate(account_rows) if i == source_index]
    if len(source_positions) != 1:
        raise ValueError("SOURCE_ACCOUNT_ROW_NOT_UNIQUE")
    source_position = source_positions[0]
    if source_position > 0:
        previous = account_rows[source_position - 1][1]
        try:
            previous_after = float(previous["after"])
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ValueError("PREVIOUS_ACCOUNT_LEDGER_ROW_INVALID") from None
        if not math.isclose(previous_after, float(source_before), rel_tol=0, abs_tol=_TOLERANCE):
            raise ValueError("SOURCE_LEDGER_PREDECESSOR_MISMATCH")

    prior_after = float(source_before)
    for index, row in account_rows[source_position:]:
        try:
            before = float(row["before"])
            amount = float(row["amount"])
            after = float(row["after"])
            if not all(math.isfinite(v) for v in (before, amount, after)):
                raise ValueError
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ValueError(f"ACCOUNT_LEDGER_ROW_INVALID:{index}") from None
        if not math.isclose(before, prior_after, rel_tol=0, abs_tol=_TOLERANCE):
            raise ValueError(f"ACCOUNT_LEDGER_CONTINUITY_FAILED:{index}")
        if not math.isclose(before + amount, after, rel_tol=0, abs_tol=_TOLERANCE):
            raise ValueError(f"ACCOUNT_LEDGER_ARITHMETIC_FAILED:{index}")
        prior_after = after

    users = db.get("users")
    user = users.get(str(uid)) if isinstance(users, dict) else None
    wallet = user.get("wallet") if isinstance(user, dict) else None
    if not isinstance(wallet, dict):
        raise ValueError("WALLET_NOT_FOUND")
    try:
        current_balance = _decimal(wallet.get("credits"), "CURRENT_BALANCE_INVALID")
    except ValueError:
        raise ValueError("CURRENT_BALANCE_INVALID") from None
    if not math.isclose(float(current_balance), prior_after, rel_tol=0, abs_tol=_TOLERANCE):
        raise ValueError("CURRENT_BALANCE_DOES_NOT_MATCH_LEDGER_TAIL")

    return {
        "ledger": ledger,
        "source_index": source_index,
        "source": source,
        "source_key": source_key,
        "source_amount": source_amount,
        "source_before": source_before,
        "source_after": source_after,
        "source_wei": source_wei,
        "account_rows": account_rows,
        "source_position": source_position,
        "current_balance": current_balance,
        "last_ledger_after": prior_after,
    }


def _validate_proof_matches_source(record, proof):
    source = record["source"]
    meta = source["meta"]
    if record["source_wei"] != proof["amount_wei"]:
        raise ValueError("SOURCE_AMOUNT_DOES_NOT_MATCH_ONCHAIN")
    if str(meta.get("from") or "").lower() != proof["from"].lower():
        raise ValueError("SOURCE_SENDER_DOES_NOT_MATCH_ONCHAIN")
    if str(meta.get("to") or "").lower() != proof["to"].lower():
        raise ValueError("SOURCE_RECEIVER_DOES_NOT_MATCH_ONCHAIN")
    if proof["from"].lower() != proof["to"].lower():
        raise ValueError("BNB_TX_NOT_SELF_TRANSFER")
    if proof["to"].lower() == proof["treasury"].lower():
        raise ValueError("BNB_TX_RECIPIENT_IS_TREASURY")


def _existing_reversal(db, record, proof, correction_key):
    ledger = record["ledger"]
    corrections = [
        row for row in ledger
        if isinstance(row, dict)
        and isinstance(row.get("meta"), dict)
        and row["meta"].get("idempotency_key") == correction_key
    ]
    audits = db.get("credit_adjustment_audit", [])
    if not isinstance(audits, list):
        raise ValueError("CREDIT_ADJUSTMENT_AUDIT_UNREADABLE")
    matching_audits = [
        row for row in audits if isinstance(row, dict)
        and row.get("correction_idempotency_key") == correction_key
    ]
    if not corrections:
        if matching_audits:
            raise ValueError("CREDIT_ADJUSTMENT_IDEMPOTENCY_CONFLICT")
        return None
    if len(corrections) != 1 or len(matching_audits) != 1:
        raise ValueError("CREDIT_ADJUSTMENT_IDEMPOTENCY_CONFLICT")

    correction = corrections[0]
    meta = correction["meta"]
    audit = matching_audits[0]
    try:
        before = _decimal(correction.get("before"), "CORRECTION_BEFORE_INVALID")
        amount = _decimal(correction.get("amount"), "CORRECTION_AMOUNT_INVALID")
        after = _decimal(correction.get("after"), "CORRECTION_AFTER_INVALID")
        audit_before = _decimal(audit.get("balance_before"), "AUDIT_BEFORE_INVALID")
        audit_amount = _decimal(audit.get("amount"), "AUDIT_AMOUNT_INVALID")
        audit_after = _decimal(audit.get("balance_after"), "AUDIT_AFTER_INVALID")
    except ValueError:
        raise ValueError("CREDIT_ADJUSTMENT_IDEMPOTENCY_CONFLICT") from None

    expected_after = float(before) - float(record["source_amount"])
    ok = (
        str(correction.get("uid")) == str(record["source"].get("uid"))
        and correction.get("reason") == _CORRECTION_REASON
        and meta.get("adjustment_kind") == _ADJUSTMENT_KIND
        and meta.get("source_idempotency_key") == record["source_key"]
        and meta.get("source_reason") == "bnb:deposit"
        and meta.get("source_ledger_index") == record["source_index"]
        and _normalise_hash(meta.get("tx_hash")) == proof["tx_hash"]
        and meta.get("gate_remained_closed") is True
        and meta.get("source_ledger_rows_preserved") is True
        and meta.get("later_account_activity_preserved") is True
        and str(meta.get("actor_uid") or "") == str(audit.get("actor_uid") or "")
        and bool(str(meta.get("actor_uid") or "").strip())
        and meta.get("nominal_credits_reversed") == float(record["source_amount"])
        and amount == Decimal(str(-float(record["source_amount"])))
        and math.isclose(float(after), expected_after, rel_tol=0, abs_tol=_TOLERANCE)
        and math.isclose(float(before) + float(amount), float(after), rel_tol=0, abs_tol=_TOLERANCE)
        and audit.get("event") == _CORRECTION_EVENT
        and str(audit.get("uid")) == str(record["source"].get("uid"))
        and _normalise_hash(audit.get("tx_hash")) == proof["tx_hash"]
        and audit.get("source_idempotency_key") == record["source_key"]
        and audit_before == before and audit_amount == amount and audit_after == after
        and audit.get("gate_remained_closed") is True
        and audit.get("nominal_credits_reversed") == float(record["source_amount"])
        and audit.get("chain_id") == proof["chain_id"]
        and audit.get("block") == proof["block"]
        and audit.get("confirmations") == proof["confirmations"]
        and audit.get("required_confirmations") == proof["required_confirmations"]
        and meta.get("chain_id") == proof["chain_id"]
        and meta.get("amount_wei") == proof["amount_wei"]
        and meta.get("block") == proof["block"]
        and meta.get("confirmations") == proof["confirmations"]
        and meta.get("required_confirmations") == proof["required_confirmations"]
        and str(meta.get("from") or "").lower() == proof["from"].lower()
        and str(meta.get("to") or "").lower() == proof["to"].lower()
        and str(meta.get("treasury") or "").lower() == proof["treasury"].lower()
    )
    if not ok:
        raise ValueError("CREDIT_ADJUSTMENT_IDEMPOTENCY_CONFLICT")
    return {
        "status": "ALREADY_REVERSED",
        "uid": str(record["source"].get("uid")),
        "tx_hash": proof["tx_hash"],
        "correction_idempotency_key": correction_key,
        "balance_after": float(after),
        "current_balance": float(record["current_balance"]),
        "gate_remained_closed": True,
    }


def is_reconciled_invalid_historical_deposit(db, ledger_index, entry, config=None):
    """Read-only validation that a failed historical deposit has a valid compensation.

    Returns True only for an exact, unique non-Treasury self-transfer whose
    original credited row is still present and whose compensating ledger + audit
    rows fully reconcile. Every uncertainty fails closed.
    """
    # A valid compensating entry is not, by itself, permission to treat the
    # historical audit blocker as cleared. Require a separate explicit operator
    # approval flag, distinct from BNB_DEPOSITS_OPEN. This prevents an old "1"
    # operator flag from making deposits effective-open as a side effect of a
    # ledger correction. This flag is read-only here and is never changed by code.
    if os.getenv("SLH_BNB_RECONCILED_HISTORY_APPROVED", "0").strip() != "1":
        return False
    try:
        if not isinstance(db, dict) or not isinstance(entry, dict):
            return False
        index = _exact_int(ledger_index, "SOURCE_LEDGER_INDEX_INVALID")
        uid = str(entry.get("uid") or "").strip()
        meta = entry.get("meta")
        if (
            index < 0
            or entry.get("reason") != "bnb:deposit"
            or not uid
            or not isinstance(meta, dict)
        ):
            return False
        tx_hash = str(meta.get("tx_hash") or "").strip().lower()
        if not _TX_HASH_RE.fullmatch(tx_hash):
            return False
        ledger = db.get("ledger")
        if not isinstance(ledger, list) or index >= len(ledger) or ledger[index] != entry:
            return False

        record = _source_and_history(db, uid, tx_hash)
        if record["source_index"] != index or record["source"] != entry:
            return False
        proof = _verify_non_treasury_self_transfer(uid, tx_hash, db)
        _validate_proof_matches_source(record, proof)
        correction_key = f"accounting:reversal:{tx_hash}"
        existing = _existing_reversal(db, record, proof, correction_key)
        return bool(existing and existing.get("status") == "ALREADY_REVERSED")
    except Exception:
        return False


def reverse_invalid_nontreasury_bnb_self_transfer(
    *, actor_uid, uid, tx_hash, expected_current_balance, now=None
):
    """Append a single audited -source-amount entry while preserving later activity.

    The original ledger entry and all subsequent transactions remain unchanged.
    This function is not reachable from a bot command or HTTP route.
    """
    actor_uid = str(actor_uid or "").strip()
    uid = str(uid or "").strip()
    tx_hash = str(tx_hash or "").strip().lower()
    if not is_owner(actor_uid):
        raise PermissionError("OWNER_ONLY")
    if not uid:
        raise ValueError("INVALID_UID")
    if not _TX_HASH_RE.fullmatch(tx_hash):
        raise ValueError("INVALID_TX_HASH")
    _require_operator_gate_flag_closed()
    if bnb_deposits_open():
        raise ValueError("BNB_GATE_MUST_REMAIN_CLOSED")

    expected_balance = _decimal(expected_current_balance, "INVALID_EXPECTED_BALANCE")
    initial_db = state_manager.load_db()
    initial_context = _treasury_context(initial_db)
    record = _source_and_history(initial_db, uid, tx_hash)
    proof = _verify_non_treasury_self_transfer(uid, tx_hash, initial_db)
    _validate_proof_matches_source(record, proof)
    correction_key = f"accounting:reversal:{tx_hash}"

    # Check an already-persisted correction before comparing the caller's
    # original expected balance: retries after a committed write must be safe.
    existing = _existing_reversal(initial_db, record, proof, correction_key)
    if existing is not None:
        return existing
    if record["current_balance"] != expected_balance:
        raise ValueError("CURRENT_BALANCE_MISMATCH")

    initial_source = deepcopy(record["source"])
    initial_account_rows = deepcopy(record["account_rows"])
    initial_bindings = deepcopy(initial_db.get("wallet_bindings"))
    initial_balance = record["current_balance"]
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
        _require_operator_gate_flag_closed()
        if bnb_deposits_open():
            raise ValueError("BNB_GATE_MUST_REMAIN_CLOSED")
        context = _treasury_context(db)
        current_wallet = _resolve_unique_user_bsc_wallet(uid, db, context["treasury"])
        if (
            context["chain_id"] != proof["chain_id"]
            or context["rpc"] != initial_context["rpc"]
            or context["treasury"].lower() != proof["treasury"].lower()
            or context["required_confirmations"] != proof["required_confirmations"]
            or current_wallet.lower() != proof["bound_wallet"].lower()
            or db.get("wallet_bindings") != initial_bindings
        ):
            raise ValueError("BNB_CONFIG_OR_BINDING_CHANGED_DURING_VERIFICATION")

        live = _source_and_history(db, uid, tx_hash)
        if live["source_index"] != record["source_index"] or live["source"] != initial_source:
            raise ValueError("SOURCE_DEPOSIT_CHANGED_DURING_VERIFICATION")
        if live["account_rows"] != initial_account_rows:
            raise ValueError("OWNER_LEDGER_CHANGED_DURING_VERIFICATION")
        if live["current_balance"] != initial_balance or live["current_balance"] != expected_balance:
            raise ValueError("CURRENT_BALANCE_MISMATCH")

        prior_result = _existing_reversal(db, live, proof, correction_key)
        if prior_result is not None:
            return prior_result

        audits = db.get("credit_adjustment_audit", [])
        if not isinstance(audits, list):
            raise ValueError("CREDIT_ADJUSTMENT_AUDIT_UNREADABLE")
        if any(isinstance(row, dict) and row.get("correction_idempotency_key") == correction_key
               for row in audits):
            raise ValueError("CREDIT_ADJUSTMENT_AUDIT_IDEMPOTENCY_CONFLICT")

        current_balance = float(live["current_balance"])
        reversal_amount = -float(live["source_amount"])
        after = current_balance + reversal_amount
        if after < 0 or not math.isfinite(after):
            raise ValueError("INSUFFICIENT_CREDITS_FOR_REVERSAL")
        if not math.isclose(current_balance + reversal_amount, after,
                            rel_tol=0, abs_tol=_TOLERANCE):
            raise ValueError("REVERSAL_FLOAT_ARITHMETIC_INVALID")

        users = db.get("users")
        user = users.get(uid) if isinstance(users, dict) else None
        wallet = user.get("wallet") if isinstance(user, dict) else None
        if not isinstance(wallet, dict):
            raise ValueError("WALLET_NOT_FOUND")

        correction = {
            "time": timestamp,
            "uid": uid,
            "before": current_balance,
            "amount": reversal_amount,
            "after": after,
            "reason": _CORRECTION_REASON,
            "meta": {
                "idempotency_key": correction_key,
                "source_idempotency_key": live["source_key"],
                "source_reason": "bnb:deposit",
                "source_ledger_index": live["source_index"],
                "tx_hash": tx_hash,
                "actor_uid": actor_uid,
                "adjustment_kind": _ADJUSTMENT_KIND,
                "nominal_credits_reversed": float(live["source_amount"]),
                "chain_id": proof["chain_id"],
                "block": proof["block"],
                "confirmations": proof["confirmations"],
                "required_confirmations": proof["required_confirmations"],
                "amount_wei": proof["amount_wei"],
                "treasury": proof["treasury"],
                "from": proof["from"],
                "to": proof["to"],
                "source_ledger_rows_preserved": True,
                "later_account_activity_preserved": True,
                "gate_remained_closed": True,
            },
        }
        audit = {
            "event": _CORRECTION_EVENT,
            "time": timestamp,
            "actor_uid": actor_uid,
            "uid": uid,
            "tx_hash": tx_hash,
            "source_idempotency_key": live["source_key"],
            "correction_idempotency_key": correction_key,
            "amount": reversal_amount,
            "nominal_credits_reversed": float(live["source_amount"]),
            "balance_before": current_balance,
            "balance_after": after,
            "chain_id": proof["chain_id"],
            "block": proof["block"],
            "confirmations": proof["confirmations"],
            "required_confirmations": proof["required_confirmations"],
            "gate_remained_closed": True,
        }

        wallet["credits"] = after
        live["ledger"].append(correction)
        audits.append(audit)
        db["credit_adjustment_audit"] = audits
        return {
            "status": "APPLIED",
            "uid": uid,
            "tx_hash": tx_hash,
            "amount_reversed": float(live["source_amount"]),
            "balance_before": current_balance,
            "balance_after": after,
            "correction_idempotency_key": correction_key,
            "source_ledger_index": live["source_index"],
            "later_account_rows_preserved": len(live["account_rows"]) - live["source_position"] - 1,
            "gate_remained_closed": True,
        }

    return state_manager.atomic_update(mutate)
