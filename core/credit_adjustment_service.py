"""Owner-only, fail-closed reversal of an invalid BNB self-transfer credit.

This callable is deliberately not wired to Telegram or HTTP. It only appends an
audited compensating ledger row; it never rewrites the source transaction.
Unlike the legacy Treasury-alias-only flow, this version supports a self-transfer
to the currently bound wallet even after unrelated, fully reconciled account
activity. It requires the caller to supply the current expected balance.
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
_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
_CORRECTION_REASON = "accounting:invalid_bnb_deposit_reversal"
_CORRECTION_EVENT = "INVALID_BNB_SELF_TRANSFER_REVERSED"
_CREDITS_PER_BNB = Decimal("1000")
_WEI_PER_BNB = Decimal(10**18)
_EPSILON = Decimal("0.000000001")


def _decimal(value, error_code):
    if isinstance(value, bool):
        raise ValueError(error_code)
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


def _same(left, right):
    return str(left or "").strip().lower() == str(right or "").strip().lower()


def _resolve_owner_bsc_wallet(uid, db):
    """Resolve one unique, usable BSC binding without assuming it is Treasury."""
    if not isinstance(db, dict):
        raise ValueError("BNB_WALLET_BINDINGS_UNVERIFIED")
    bindings = db.get("wallet_bindings")
    if not isinstance(bindings, dict):
        raise ValueError("BNB_WALLET_BINDINGS_UNVERIFIED")

    uid = str(uid or "").strip()
    owner_wallets = []
    bsc_bindings = []
    for binding in bindings.values():
        if not isinstance(binding, dict):
            raise ValueError("BNB_WALLET_BINDINGS_UNVERIFIED")
        chain = str(binding.get("chain") or "").strip().lower()
        if not chain:
            raise ValueError("BNB_WALLET_BINDINGS_UNVERIFIED")
        if chain != "bsc":
            continue
        address = str(binding.get("address") or "").strip()
        if not _ADDRESS_RE.fullmatch(address) or not Web3.is_address(address):
            raise ValueError("BNB_WALLET_BINDINGS_UNVERIFIED")
        if is_quarantined_bsc_address(address):
            raise ValueError("BNB_WALLET_BINDINGS_UNVERIFIED")
        binding_uid = str(binding.get("uid") or "").strip()
        bsc_bindings.append((binding_uid, address))
        if binding_uid == uid:
            owner_wallets.append(address)

    if len(owner_wallets) != 1:
        raise ValueError("BNB_OWNER_WALLET_NOT_UNIQUE")
    owner_wallet = owner_wallets[0]
    aliases = [binding_uid for binding_uid, address in bsc_bindings
               if address.lower() == owner_wallet.lower()]
    if aliases != [uid]:
        raise ValueError("BNB_OWNER_WALLET_BINDING_NOT_UNIQUE")
    return owner_wallet


def _verify_self_transfer_for_reversal(uid, tx_hash, db):
    """Read-only live proof that a confirmed transfer sent value to itself."""
    cfg = _effective_config(db)
    rpc = str(cfg.get("rpc") or "").strip()
    treasury = str(cfg.get("treasury_wallet") or "").strip()
    canonical = str(os.getenv("SLH_BSC_CANONICAL_TREASURY", "")).strip()

    if int(cfg.get("chain_id") or 0) != 56:
        raise ValueError("BSC_CONFIGURED_CHAIN_ID_NOT_56")
    if not rpc:
        raise ValueError("BSC_RPC_MISSING")
    if (
        not treasury or not canonical
        or not Web3.is_address(treasury)
        or not Web3.is_address(canonical)
        or treasury.lower() != canonical.lower()
    ):
        raise ValueError("BNB_CANONICAL_TREASURY_MISMATCH")
    if is_quarantined_bsc_address(treasury):
        raise ValueError("BSC_TREASURY_QUARANTINED")

    owner_wallet = _resolve_owner_bsc_wallet(uid, db)
    try:
        w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 5}))
        chain_id = int(w3.eth.chain_id)
        if chain_id != 56:
            raise ValueError("BSC_CHAIN_ID_NOT_56")
        tx = w3.eth.get_transaction(tx_hash)
        receipt = w3.eth.get_transaction_receipt(tx_hash)
        actual_hash = _normalise_hash(tx.get("hash"))
        receipt_hash = _normalise_hash(receipt.get("transactionHash")) if receipt else ""
        if actual_hash != tx_hash.lower() or receipt_hash != tx_hash.lower():
            raise ValueError("BNB_TX_HASH_MISMATCH")
        if not receipt or int(receipt.get("status", 0)) != 1:
            raise ValueError("BNB_TX_NOT_SUCCESSFUL")

        sender = str(tx.get("from") or "").strip()
        recipient = str(tx.get("to") or "").strip()
        if not sender or not recipient:
            raise ValueError("BNB_TX_ADDRESSES_MISSING")
        if sender.lower() != owner_wallet.lower() or recipient.lower() != owner_wallet.lower():
            raise ValueError("BNB_TX_NOT_BOUND_WALLET_SELF_TRANSFER")

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
            "bound_wallet": owner_wallet,
            "amount_wei": amount_wei,
            "block": block,
            "confirmations": confirmations,
            "required_confirmations": required,
        }
    except ValueError:
        raise
    except Exception:
        raise ValueError("BNB_FORENSIC_RPC_FAILED") from None


def _find_source(db, uid, tx_hash):
    ledger = db.get("ledger")
    if not isinstance(ledger, list):
        raise ValueError("LEDGER_UNREADABLE")
    source_key = f"bnb:deposit:{tx_hash.lower()}"
    matches = [
        (index, row) for index, row in enumerate(ledger)
        if isinstance(row, dict)
        and row.get("reason") == "bnb:deposit"
        and isinstance(row.get("meta"), dict)
        and _same(row["meta"].get("tx_hash"), tx_hash)
    ]
    if len(matches) != 1:
        raise ValueError("SOURCE_DEPOSIT_NOT_UNIQUE")
    index, row = matches[0]
    meta = row["meta"]
    if str(row.get("uid") or "").strip() != uid:
        raise ValueError("SOURCE_DEPOSIT_UID_MISMATCH")
    if str(meta.get("idempotency_key") or "").lower() != source_key:
        raise ValueError("SOURCE_IDEMPOTENCY_KEY_INVALID")
    key_matches = [
        item for item in ledger
        if isinstance(item, dict)
        and isinstance(item.get("meta"), dict)
        and str(item["meta"].get("idempotency_key") or "").lower() == source_key
    ]
    if len(key_matches) != 1:
        raise ValueError("SOURCE_IDEMPOTENCY_KEY_NOT_UNIQUE")
    return index, row, meta, source_key


def _validate_source(row, meta, proof, uid, tx_hash):
    amount_wei = meta.get("bnb_amount_wei")
    if isinstance(amount_wei, bool) or not isinstance(amount_wei, int) or amount_wei <= 0:
        raise ValueError("SOURCE_AMOUNT_WEI_INVALID")
    if not _same(meta.get("tx_hash"), tx_hash) or proof.get("tx_hash") != tx_hash.lower():
        raise ValueError("SOURCE_TX_HASH_MISMATCH")
    if proof.get("receipt_status") != 1 or proof.get("chain_id") != 56:
        raise ValueError("SOURCE_CHAIN_PROOF_INVALID")
    if proof.get("amount_wei") != amount_wei:
        raise ValueError("SOURCE_AMOUNT_WEI_MISMATCH")
    bound = str(proof.get("bound_wallet") or "").strip()
    if not bound or not _same(proof.get("from"), bound) or not _same(proof.get("to"), bound):
        raise ValueError("SOURCE_NOT_BOUND_WALLET_SELF_TRANSFER")
    if not _same(meta.get("from"), proof.get("from")) or not _same(meta.get("to"), proof.get("to")):
        raise ValueError("SOURCE_CHAIN_ADDRESSES_MISMATCH")
    if not str(uid or "").strip():
        raise ValueError("SOURCE_UID_MISSING")

    amount = _decimal(row.get("amount"), "SOURCE_AMOUNT_INVALID")
    before = _decimal(row.get("before"), "SOURCE_BEFORE_INVALID")
    after = _decimal(row.get("after"), "SOURCE_AFTER_INVALID")
    expected = Decimal(str(float(Decimal(amount_wei) * _CREDITS_PER_BNB / _WEI_PER_BNB)))
    if amount <= 0 or abs(amount - expected) > _EPSILON:
        raise ValueError("SOURCE_CREDITS_DO_NOT_MATCH_ONCHAIN_AMOUNT")
    if abs((before + amount) - after) > _EPSILON:
        raise ValueError("SOURCE_LEDGER_ARITHMETIC_INVALID")
    return amount, amount_wei, before, after


def _replay_account_ledger(ledger, uid, source_index):
    """Check balance arithmetic from the source credit through the latest row."""
    source = ledger[source_index]
    running = _decimal(source.get("after"), "SOURCE_AFTER_INVALID")
    balances = {}
    for index in range(source_index + 1, len(ledger)):
        row = ledger[index]
        if not isinstance(row, dict) or str(row.get("uid") or "").strip() != uid:
            continue
        before = _decimal(row.get("before"), "ACCOUNT_LEDGER_BEFORE_INVALID")
        amount = _decimal(row.get("amount"), "ACCOUNT_LEDGER_AMOUNT_INVALID")
        after = _decimal(row.get("after"), "ACCOUNT_LEDGER_AFTER_INVALID")
        if abs(before - running) > _EPSILON or abs((before + amount) - after) > _EPSILON:
            raise ValueError("ACCOUNT_LEDGER_SEQUENCE_INVALID")
        balances[index] = (before, amount, after)
        running = after
    return running, balances


def _wallet_balance(db, uid):
    users = db.get("users")
    user = users.get(uid) if isinstance(users, dict) else None
    wallet = user.get("wallet") if isinstance(user, dict) else None
    if not isinstance(wallet, dict):
        raise ValueError("REVERSAL_WALLET_UNREADABLE")
    return _decimal(wallet.get("credits"), "REVERSAL_WALLET_INVALID")


def _existing_reversal_result(db, *, uid, tx_hash, source_index, source, source_meta,
                              source_key, source_amount, proof, correction_key):
    ledger = db.get("ledger", [])
    corrections = [
        (index, row) for index, row in enumerate(ledger)
        if isinstance(row, dict)
        and isinstance(row.get("meta"), dict)
        and row["meta"].get("idempotency_key") == correction_key
    ]
    if not corrections:
        return None
    if len(corrections) != 1:
        raise ValueError("REVERSAL_IDEMPOTENCY_CONFLICT")
    correction_index, correction = corrections[0]
    if correction_index <= source_index or str(correction.get("uid") or "") != uid:
        raise ValueError("REVERSAL_IDEMPOTENCY_CONFLICT")
    meta = correction.get("meta")
    if not isinstance(meta, dict):
        raise ValueError("REVERSAL_METADATA_INVALID")
    if (
        correction.get("reason") != _CORRECTION_REASON
        or meta.get("correction_version") != 2
        or meta.get("source_idempotency_key") != source_key
        or meta.get("source_reason") != "bnb:deposit"
        or meta.get("source_ledger_index") != source_index
        or not _same(meta.get("tx_hash"), tx_hash)
        or meta.get("gate_remained_closed") is not True
        or meta.get("chain_id") != 56
        or not _same(meta.get("from"), proof.get("bound_wallet"))
        or not _same(meta.get("to"), proof.get("bound_wallet"))
        or meta.get("amount_wei") != proof.get("amount_wei")
        or meta.get("block") != proof.get("block")
        or meta.get("confirmations") != proof.get("confirmations")
        or meta.get("required_confirmations") != proof.get("required_confirmations")
        or not _same(meta.get("current_treasury_at_correction"), meta.get("treasury"))
    ):
        raise ValueError("REVERSAL_IDEMPOTENCY_CONFLICT")

    audits = db.get("credit_adjustment_audit")
    if not isinstance(audits, list):
        raise ValueError("CREDIT_ADJUSTMENT_AUDIT_UNREADABLE")
    audit_matches = [
        item for item in audits if isinstance(item, dict)
        and item.get("correction_idempotency_key") == correction_key
    ]
    if len(audit_matches) != 1:
        raise ValueError("REVERSAL_AUDIT_NOT_UNIQUE")
    audit = audit_matches[0]

    correction_before = _decimal(correction.get("before"), "REVERSAL_BEFORE_INVALID")
    correction_amount = _decimal(correction.get("amount"), "REVERSAL_AMOUNT_INVALID")
    correction_after = _decimal(correction.get("after"), "REVERSAL_AFTER_INVALID")
    nominal = _decimal(meta.get("nominal_credits_reversed"), "REVERSAL_NOMINAL_INVALID")
    if (
        abs(nominal - source_amount) > _EPSILON
        or abs(correction_amount + source_amount) > _EPSILON
        or abs((correction_before + correction_amount) - correction_after) > _EPSILON
    ):
        raise ValueError("REVERSAL_AMOUNT_RECONCILIATION_FAILED")

    running, balances = _replay_account_ledger(ledger, uid, source_index)
    if correction_index not in balances:
        raise ValueError("REVERSAL_LEDGER_SEQUENCE_INVALID")
    if (
        abs(balances[correction_index][0] - correction_before) > _EPSILON
        or abs(balances[correction_index][1] - correction_amount) > _EPSILON
        or abs(balances[correction_index][2] - correction_after) > _EPSILON
        or abs(_wallet_balance(db, uid) - running) > _EPSILON
    ):
        raise ValueError("REVERSAL_LEDGER_SEQUENCE_INVALID")

    expected_audit = (
        audit.get("event") == _CORRECTION_EVENT
        and str(audit.get("uid") or "") == uid
        and str(audit.get("actor_uid") or "") == str(meta.get("actor_uid") or "")
        and _same(audit.get("tx_hash"), tx_hash)
        and audit.get("source_idempotency_key") == source_key
        and audit.get("correction_idempotency_key") == correction_key
        and audit.get("chain_id") == 56
        and audit.get("block") == proof.get("block")
        and audit.get("confirmations") == proof.get("confirmations")
        and audit.get("required_confirmations") == proof.get("required_confirmations")
        and audit.get("gate_remained_closed") is True
        and abs(_decimal(audit.get("balance_before"), "REVERSAL_AUDIT_INVALID") - correction_before) <= _EPSILON
        and abs(_decimal(audit.get("amount"), "REVERSAL_AUDIT_INVALID") - correction_amount) <= _EPSILON
        and abs(_decimal(audit.get("balance_after"), "REVERSAL_AUDIT_INVALID") - correction_after) <= _EPSILON
        and abs(_decimal(audit.get("nominal_credits_reversed"), "REVERSAL_AUDIT_INVALID") - nominal) <= _EPSILON
    )
    if not expected_audit:
        raise ValueError("REVERSAL_AUDIT_RECONCILIATION_FAILED")

    try:
        from core.authority import is_owner as owner_check
        actor_uid = str(meta.get("actor_uid") or "")
        if not actor_uid or not owner_check(actor_uid):
            raise ValueError("REVERSAL_ACTOR_NOT_OWNER")
    except Exception:
        raise ValueError("REVERSAL_ACTOR_NOT_OWNER") from None
    return {
        "status": "ALREADY_REVERSED",
        "uid": uid,
        "tx_hash": tx_hash,
        "amount_reversed": float(source_amount),
        "balance_after": float(correction_after),
        "correction_idempotency_key": correction_key,
        "gate_remained_closed": True,
    }


def reverse_invalid_bnb_deposit(*, actor_uid, uid, tx_hash,
                                expected_current_balance, now=None):
    """Append one audited compensating entry after live proof and full reconciliation.

    Unlike the legacy flow, this does not reset the balance to its historical
    pre-deposit value. It debits the invalid source amount from the supplied,
    currently reconciled balance and preserves every later ledger entry.
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

    def mutate(db):
        if not isinstance(db, dict) or not isinstance(db.get("ledger"), list):
            raise ValueError("LEDGER_UNREADABLE")
        if bnb_deposits_open():
            raise ValueError("BNB_GATE_MUST_REMAIN_CLOSED")

        source_index, source, source_meta, source_key = _find_source(db, uid, tx_hash)
        proof = _verify_self_transfer_for_reversal(uid, tx_hash, db)
        source_amount, amount_wei, _source_before, _source_after = _validate_source(
            source, source_meta, proof, uid, tx_hash
        )
        correction_key = f"accounting:reversal:{tx_hash.lower()}"
        existing = _existing_reversal_result(
            db, uid=uid, tx_hash=tx_hash.lower(), source_index=source_index,
            source=source, source_meta=source_meta, source_key=source_key,
            source_amount=source_amount, proof=proof, correction_key=correction_key,
        )
        if existing is not None:
            return existing

        correction_collisions = [
            row for row in db["ledger"]
            if isinstance(row, dict) and isinstance(row.get("meta"), dict)
            and row["meta"].get("idempotency_key") == correction_key
        ]
        if correction_collisions:
            raise ValueError("REVERSAL_IDEMPOTENCY_CONFLICT")

        current_balance = _wallet_balance(db, uid)
        if abs(current_balance - expected_balance) > _EPSILON:
            raise ValueError("CURRENT_BALANCE_MISMATCH")
        running, _balances = _replay_account_ledger(db["ledger"], uid, source_index)
        if abs(running - current_balance) > _EPSILON:
            raise ValueError("CURRENT_BALANCE_LEDGER_MISMATCH")
        if current_balance < source_amount:
            raise ValueError("INSUFFICIENT_CREDITS_FOR_REVERSAL")

        cfg = _effective_config(db)
        treasury = str(cfg.get("treasury_wallet") or "").strip()
        canonical = str(os.getenv("SLH_BSC_CANONICAL_TREASURY", "")).strip()
        if not treasury or not canonical or treasury.lower() != canonical.lower():
            raise ValueError("BNB_CANONICAL_TREASURY_MISMATCH")
        if not Web3.is_address(treasury) or is_quarantined_bsc_address(treasury):
            raise ValueError("BNB_TREASURY_UNUSABLE")

        before = float(current_balance)
        reversal_amount = -float(source_amount)
        after = float(current_balance + reversal_amount)
        if abs((before + reversal_amount) - after) > 1e-9:
            raise ValueError("REVERSAL_FLOAT_ARITHMETIC_INVALID")

        stamp = now if isinstance(now, datetime) else datetime.now(timezone.utc)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        timestamp = stamp.isoformat()
        ledger = db["ledger"]
        audits = db.get("credit_adjustment_audit", [])
        if not isinstance(audits, list):
            raise ValueError("CREDIT_ADJUSTMENT_AUDIT_UNREADABLE")
        if any(isinstance(item, dict) and item.get("correction_idempotency_key") == correction_key
               for item in audits):
            raise ValueError("CREDIT_ADJUSTMENT_AUDIT_IDEMPOTENCY_CONFLICT")

        correction = {
            "time": timestamp,
            "uid": uid,
            "before": before,
            "amount": reversal_amount,
            "after": after,
            "reason": _CORRECTION_REASON,
            "meta": {
                "idempotency_key": correction_key,
                "correction_version": 2,
                "source_idempotency_key": source_key,
                "source_reason": "bnb:deposit",
                "source_ledger_index": source_index,
                "tx_hash": tx_hash.lower(),
                "actor_uid": actor_uid,
                "nominal_credits_reversed": float(source_amount),
                "chain_id": 56,
                "block": proof["block"],
                "confirmations": proof["confirmations"],
                "required_confirmations": proof["required_confirmations"],
                "amount_wei": amount_wei,
                "treasury": treasury,
                "current_treasury_at_correction": treasury,
                "from": proof["from"],
                "to": proof["to"],
                "gate_remained_closed": True,
            },
        }
        audit = {
            "event": _CORRECTION_EVENT,
            "time": timestamp,
            "uid": uid,
            "actor_uid": actor_uid,
            "tx_hash": tx_hash.lower(),
            "source_idempotency_key": source_key,
            "correction_idempotency_key": correction_key,
            "amount": reversal_amount,
            "nominal_credits_reversed": float(source_amount),
            "balance_before": before,
            "balance_after": after,
            "chain_id": 56,
            "block": proof["block"],
            "confirmations": proof["confirmations"],
            "required_confirmations": proof["required_confirmations"],
            "gate_remained_closed": True,
        }
        # Preserve the original and every later row; append a compensation only.
        ledger.append(correction)
        audits.append(audit)
        db["credit_adjustment_audit"] = audits
        db["users"][uid]["wallet"]["credits"] = after
        return {
            "status": "APPLIED",
            "uid": uid,
            "tx_hash": tx_hash.lower(),
            "amount_reversed": float(source_amount),
            "balance_before": before,
            "balance_after": after,
            "correction_idempotency_key": correction_key,
            "gate_remained_closed": True,
        }

    return state_manager.atomic_update(mutate)
