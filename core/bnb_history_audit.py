"""Read-only audit of every historical native BNB deposit credit.

A passing empirical smoke proves one transaction, not every historical ledger row.
This audit intentionally fails closed when any credited BNB row cannot be tied
back to a successful, sufficiently-confirmed BSC transfer and its persisted
metadata. It never writes DB state or changes balances/gates.
"""
from __future__ import annotations

import math
import re
from typing import Any

from web3 import Web3
from core.binance_connector import get_bsc_config
from core.bsc_address_policy import is_quarantined_bsc_address

TX_HASH_RE = re.compile(r"^0x[0-9a-fA-F]{64}$")
CREDITS_PER_BNB = 1000
MAX_AUDIT_ROWS = 25
EPSILON = 1e-9


def _same_address(left: Any, right: Any) -> bool:
    return bool(
        isinstance(left, str) and left.strip()
        and isinstance(right, str) and right.strip()
        and left.strip().lower() == right.strip().lower()
    )


def _normalized_tx_hash(value: Any) -> str:
    if hasattr(value, "hex") and not isinstance(value, str):
        value = value.hex()
    result = str(value or "").strip().lower()
    if result and not result.startswith("0x"):
        result = "0x" + result
    return result


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _exact_nonnegative_int(value: Any) -> int | None:
    """Parse persisted integer metadata without truncating floats or accepting booleans."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        return int(value)
    return None


def _binding_for_uid(db: dict, uid: str) -> tuple[str | None, str | None]:
    registry = db.get("wallet_bindings")
    if not isinstance(registry, dict):
        return None, "WALLET_BINDINGS_UNVERIFIED"
    matches = [
        value for value in registry.values()
        if isinstance(value, dict)
        and str(value.get("uid") or "") == uid
        and str(value.get("chain") or "").strip().lower() == "bsc"
    ]
    if len(matches) != 1:
        return None, "CURRENT_WALLET_BINDING_MISSING_OR_AMBIGUOUS"
    address = str(matches[0].get("address") or "").strip()
    if not address or is_quarantined_bsc_address(address):
        return None, "CURRENT_WALLET_BINDING_UNUSABLE"
    return address, None


def _valid_audited_reversal(
    db: dict,
    ledger: list,
    source_index: int,
    source: dict,
    tx_hash: str,
    sender: str,
    destination: str,
    amount_wei: int,
    block_number: int,
    confirmations_required: int,
    observed_confirmations: int,
    bound_wallet: str,
) -> bool:
    """Recognize only the exact, persisted reversal contract from credit_adjustment_service."""
    correction_key = f"accounting:reversal:{tx_hash.lower()}"
    source_key = f"bnb:deposit:{tx_hash.lower()}"
    correction_matches = [
        (index, row) for index, row in enumerate(ledger)
        if isinstance(row, dict)
        and isinstance(row.get("meta"), dict)
        and row["meta"].get("idempotency_key") == correction_key
    ]
    if len(correction_matches) != 1:
        return False
    correction_index, correction = correction_matches[0]
    if correction_index <= source_index:
        return False

    # The original reversal callable is intentionally limited to accounts with
    # no ledger activity between the source credit and its compensation.
    source_uid = str(source.get("uid") or "")
    for row in ledger[source_index + 1:correction_index]:
        if isinstance(row, dict) and str(row.get("uid") or "") == source_uid:
            return False

    meta = correction.get("meta")
    if not isinstance(meta, dict):
        return False
    audits = db.get("credit_adjustment_audit")
    if not isinstance(audits, list):
        return False
    matching_audits = [
        row for row in audits
        if isinstance(row, dict) and row.get("correction_idempotency_key") == correction_key
    ]
    if len(matching_audits) != 1:
        return False
    audit = matching_audits[0]

    source_meta = source.get("meta")
    if not isinstance(source_meta, dict):
        return False
    source_before = _finite_number(source.get("before"))
    source_amount = _finite_number(source.get("amount"))
    source_after = _finite_number(source.get("after"))
    reversal_before = _finite_number(correction.get("before"))
    reversal_amount = _finite_number(correction.get("amount"))
    reversal_after = _finite_number(correction.get("after"))
    nominal = _finite_number(meta.get("nominal_credits_reversed"))
    audit_before = _finite_number(audit.get("balance_before"))
    audit_amount = _finite_number(audit.get("amount"))
    audit_after = _finite_number(audit.get("balance_after"))
    audit_nominal = _finite_number(audit.get("nominal_credits_reversed"))
    source_wei = _exact_nonnegative_int(source_meta.get("bnb_amount_wei"))
    reversal_wei = _exact_nonnegative_int(meta.get("amount_wei"))
    reversal_block = _exact_nonnegative_int(meta.get("block"))
    audit_block = _exact_nonnegative_int(audit.get("block"))
    reversal_confirms = _exact_nonnegative_int(meta.get("confirmations"))
    audit_confirms = _exact_nonnegative_int(audit.get("confirmations"))
    reversal_required = _exact_nonnegative_int(meta.get("required_confirmations"))
    audit_required = _exact_nonnegative_int(audit.get("required_confirmations"))
    reversal_chain = _exact_nonnegative_int(meta.get("chain_id"))
    audit_chain = _exact_nonnegative_int(audit.get("chain_id"))
    audit_source_index = _exact_nonnegative_int(meta.get("source_ledger_index"))
    if any(value is None for value in (
        source_wei, reversal_wei, reversal_block, audit_block,
        reversal_confirms, audit_confirms, reversal_required,
        audit_required, reversal_chain, audit_chain, audit_source_index,
    )):
        return False

    if any(value is None for value in (
        source_before, source_amount, source_after, reversal_before,
        reversal_amount, reversal_after, nominal, audit_before,
        audit_amount, audit_after, audit_nominal,
    )):
        return False

    historical_treasury = str(meta.get("treasury") or "").strip()
    actor_uid = str(meta.get("actor_uid") or "").strip()
    try:
        from core.authority import is_owner

        authorized_actor = bool(actor_uid and is_owner(actor_uid))
    except Exception:
        authorized_actor = False
    return bool(
        authorized_actor
        and audit.get("actor_uid") == actor_uid
        and correction.get("reason") == "accounting:invalid_bnb_deposit_reversal"
        and str(correction.get("uid") or "") == source_uid
        and source_uid
        and str(meta.get("tx_hash") or "").lower() == tx_hash.lower()
        and meta.get("source_idempotency_key") == source_key
        and meta.get("source_reason") == "bnb:deposit"
        and audit_source_index == source_index
        and meta.get("gate_remained_closed") is True
        and reversal_chain == 56
        and audit_chain == 56
        and _same_address(historical_treasury, sender)
        and _same_address(historical_treasury, destination)
        and _same_address(meta.get("from"), bound_wallet)
        and _same_address(meta.get("to"), bound_wallet)
        and _same_address(sender, bound_wallet)
        and _same_address(destination, bound_wallet)
        and _same_address(source_meta.get("from"), sender)
        and _same_address(source_meta.get("to"), destination)
        and source_wei == amount_wei == reversal_wei
        and reversal_block == audit_block == block_number
        and reversal_confirms >= reversal_required >= 1
        and reversal_confirms <= observed_confirmations
        and reversal_required == audit_required == confirmations_required
        and reversal_confirms == audit_confirms
        and correction_index > source_index
        and source_before is not None and source_amount is not None and source_after is not None
        and reversal_before is not None and reversal_amount is not None and reversal_after is not None
        and abs((source_before + source_amount) - source_after) <= EPSILON
        and abs(reversal_before - source_after) <= EPSILON
        and abs(reversal_after - source_before) <= EPSILON
        and abs(reversal_amount - (reversal_after - reversal_before)) <= EPSILON
        and abs(nominal - source_amount) <= EPSILON
        and abs(audit_before - reversal_before) <= EPSILON
        and abs(audit_amount - reversal_amount) <= EPSILON
        and abs(audit_after - reversal_after) <= EPSILON
        and abs(audit_nominal - nominal) <= EPSILON
        and audit.get("event") == "INVALID_BNB_SELF_TRANSFER_REVERSED"
        and str(audit.get("uid") or "") == source_uid
        and str(audit.get("tx_hash") or "").lower() == tx_hash.lower()
        and audit.get("source_idempotency_key") == source_key
        and audit.get("gate_remained_closed") is True
    )


def audit_bnb_deposit_history(db: dict | None) -> dict:
    """Audit all ledger entries with reason=bnb:deposit against BSC RPC.

    Historic entries whose destination differs from the current configured
    Treasury are unresolved: without a persisted historical-Treasury authority,
    they are not silently grandfathered. Output omits full addresses and TX IDs.
    """
    if not isinstance(db, dict):
        return {
            "scope": "read_only", "status": "BLOCKED",
            "rows_found": 0, "rows_checked": 0, "failed_rows": 0,
            "blockers": ["DB_UNREADABLE"], "findings": [],
        }

    ledger = db.get("ledger")
    if not isinstance(ledger, list):
        return {
            "scope": "read_only", "status": "BLOCKED",
            "rows_found": 0, "rows_checked": 0, "failed_rows": 0,
            "blockers": ["LEDGER_UNREADABLE"], "findings": [],
        }

    indexed_rows = [
        (index, item) for index, item in enumerate(ledger)
        if isinstance(item, dict) and item.get("reason") == "bnb:deposit"
    ]
    rows = [item for _index, item in indexed_rows]
    if len(rows) > MAX_AUDIT_ROWS:
        return {
            "scope": "read_only", "status": "BLOCKED",
            "rows_found": len(rows), "rows_checked": 0,
            "failed_rows": len(rows),
            "blockers": ["AUDIT_ROW_LIMIT_EXCEEDED"],
            "findings": [],
        }

    # A well-formed database with no BNB credit rows has nothing to reconcile.
    if not rows:
        return {
            "scope": "read_only", "status": "PASS",
            "rows_found": 0, "rows_checked": 0, "failed_rows": 0,
            "blockers": [], "findings": [],
        }

    cfg = get_bsc_config()
    cfg = dict(cfg) if isinstance(cfg, dict) else {}
    overrides = db.get("bsc_settings")
    if isinstance(overrides, dict):
        cfg.update(overrides)

    rpc = str(cfg.get("rpc") or "").strip()
    treasury = str(cfg.get("treasury_wallet") or "").strip()
    try:
        chain_id_expected = int(cfg.get("chain_id") or 0)
        confirmations_required = int(cfg.get("confirmations") or 15)
    except (TypeError, ValueError, OverflowError):
        chain_id_expected, confirmations_required = 0, 0

    if not rpc or not treasury or chain_id_expected != 56 or confirmations_required < 1:
        return {
            "scope": "read_only", "status": "BLOCKED",
            "rows_found": len(rows), "rows_checked": 0,
            "failed_rows": len(rows),
            "blockers": ["BSC_AUDIT_CONFIGURATION_INVALID"],
            "findings": [],
        }

    try:
        w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 5}))
        live_chain_id = int(w3.eth.chain_id)
        latest_block = int(w3.eth.block_number)
    except Exception as exc:
        return {
            "scope": "read_only", "status": "BLOCKED",
            "rows_found": len(rows), "rows_checked": 0,
            "failed_rows": len(rows),
            "blockers": ["BSC_RPC_UNAVAILABLE", type(exc).__name__],
            "findings": [],
        }

    if live_chain_id != 56:
        return {
            "scope": "read_only", "status": "BLOCKED",
            "rows_found": len(rows), "rows_checked": 0,
            "failed_rows": len(rows),
            "blockers": ["LIVE_BSC_CHAIN_ID_NOT_56"],
            "findings": [],
        }

    hash_counts: dict[str, int] = {}
    key_counts: dict[str, int] = {}
    for item in ledger:
        if not isinstance(item, dict):
            continue
        meta = item.get("meta")
        if not isinstance(meta, dict):
            continue
        value = str(meta.get("tx_hash") or "").strip().lower()
        # A legitimate reversal intentionally refers to the source TX hash.
        # Count hashes among deposit credits only; correction records are
        # separately validated against their own idempotency/audit keys.
        if value and item.get("reason") == "bnb:deposit":
            hash_counts[value] = hash_counts.get(value, 0) + 1
        key = str(meta.get("idempotency_key") or "")
        if key:
            key_counts[key] = key_counts.get(key, 0) + 1

    findings = []
    blockers: set[str] = set()
    checked = 0

    for source_index, row in indexed_rows:
        checked += 1
        meta = row.get("meta")
        meta = meta if isinstance(meta, dict) else {}
        tx_hash = str(meta.get("tx_hash") or "").strip()
        suffix = tx_hash[-8:] if len(tx_hash) >= 8 else "MISSING"
        issues: list[str] = []
        uid = str(row.get("uid") or "").strip()

        if not uid:
            issues.append("LEDGER_UID_MISSING")
        if not TX_HASH_RE.fullmatch(tx_hash):
            issues.append("TX_HASH_INVALID")
            findings.append({
                "time": str(row.get("time") or "")[:40],
                "tx_suffix": suffix, "status": "BLOCKED",
                "issues": issues,
            })
            blockers.update(issues)
            continue

        expected_key = f"bnb:deposit:{tx_hash.lower()}"
        if str(meta.get("idempotency_key") or "") != expected_key:
            issues.append("IDEMPOTENCY_KEY_INVALID")
        if key_counts.get(expected_key, 0) != 1:
            issues.append("IDEMPOTENCY_KEY_NOT_UNIQUE")
        if hash_counts.get(tx_hash.lower(), 0) != 1:
            issues.append("TX_HASH_NOT_UNIQUE")

        try:
            tx = w3.eth.get_transaction(tx_hash)
            receipt = w3.eth.get_transaction_receipt(tx_hash)
            sender = str(tx.get("from") or "").strip()
            destination = str(tx.get("to") or "").strip()
            amount_wei = int(tx.get("value") or 0)
            receipt_status = int(receipt.get("status") or 0)
            block_number = int(receipt.get("blockNumber") or 0)
            returned_tx_hash = _normalized_tx_hash(tx.get("hash"))
            receipt_tx_hash = _normalized_tx_hash(receipt.get("transactionHash"))
            confirmations = max(0, latest_block - block_number + 1)
        except Exception:
            issues.append("TX_LOOKUP_FAILED")
            findings.append({
                "time": str(row.get("time") or "")[:40],
                "tx_suffix": suffix, "status": "BLOCKED",
                "issues": issues,
            })
            blockers.update(issues)
            # A failed RPC lookup is an unresolved financial record. Stop the
            # sweep rather than making many more slow requests to a bad node.
            blockers.add("HISTORICAL_AUDIT_INCOMPLETE")
            return {
                "scope": "read_only",
                "status": "BLOCKED",
                "rows_found": len(rows),
                "rows_checked": checked,
                "failed_rows": sum(1 for item in findings if item.get("status") != "PASS")
                + (len(rows) - checked),
                "blockers": sorted(blockers),
                "findings": findings,
            }

        if receipt_status != 1:
            issues.append("TX_RECEIPT_NOT_SUCCESSFUL")
        if returned_tx_hash != tx_hash.lower() or receipt_tx_hash != tx_hash.lower():
            issues.append("TX_HASH_MISMATCH")
        if block_number <= 0:
            issues.append("TX_BLOCK_NUMBER_INVALID")
        if not destination:
            issues.append("TX_DESTINATION_MISSING")
        if sender and destination and sender.lower() == destination.lower():
            issues.append("SELF_TRANSFER_NOT_A_DEPOSIT")
        if amount_wei <= 0:
            issues.append("TX_AMOUNT_INVALID")
        if confirmations < confirmations_required:
            issues.append("TX_CONFIRMATIONS_INSUFFICIENT")

        if not _same_address(meta.get("from"), sender):
            issues.append("STORED_SENDER_MISMATCH")
        if not _same_address(meta.get("to"), destination):
            issues.append("STORED_DESTINATION_MISMATCH")
        if not _same_address(destination, treasury):
            issues.append("HISTORICAL_DESTINATION_NOT_CURRENT_TREASURY")
        if is_quarantined_bsc_address(sender) or is_quarantined_bsc_address(destination):
            issues.append("QUARANTINED_ADDRESS_IN_DEPOSIT")

        stored_amount_wei = _exact_nonnegative_int(meta.get("bnb_amount_wei")) or 0
        if stored_amount_wei <= 0 or stored_amount_wei != amount_wei:
            issues.append("STORED_AMOUNT_WEI_MISMATCH")

        posted = _finite_number(row.get("amount"))
        before = _finite_number(row.get("before"))
        after = _finite_number(row.get("after"))
        expected_credits = amount_wei / (10**18) * CREDITS_PER_BNB if amount_wei > 0 else None
        if posted is None or expected_credits is None or abs(posted - expected_credits) > max(EPSILON, abs(expected_credits) * 1e-9):
            issues.append("LEDGER_CREDITS_MISMATCH")
        if before is None or after is None or posted is None or abs((before + posted) - after) > EPSILON:
            issues.append("LEDGER_BALANCE_DELTA_MISMATCH")

        bound, binding_issue = _binding_for_uid(db, uid)
        if binding_issue:
            issues.append(binding_issue)
        elif not _same_address(sender, bound):
            issues.append("TX_SENDER_NOT_CURRENTLY_BOUND")

        unique_issues = sorted(set(issues))
        reported_issues = list(unique_issues)
        reversible_issues = set(unique_issues)
        if (
            "SELF_TRANSFER_NOT_A_DEPOSIT" in reversible_issues
            and reversible_issues <= {
                "SELF_TRANSFER_NOT_A_DEPOSIT",
                "HISTORICAL_DESTINATION_NOT_CURRENT_TREASURY",
            }
            and bound
            and _valid_audited_reversal(
                db, ledger, source_index, row, tx_hash, sender, destination,
                amount_wei, block_number, confirmations_required, confirmations, bound,
            )
        ):
            status = "RESOLVED_BY_AUDITED_REVERSAL"
            reported_issues = [
                "SELF_TRANSFER_NOT_A_DEPOSIT",
                "RESOLVED_BY_AUDITED_REVERSAL",
            ]
        elif unique_issues:
            status = "BLOCKED"
            blockers.update(unique_issues)
        else:
            status = "PASS"

        findings.append({
            "time": str(row.get("time") or "")[:40],
            "tx_suffix": suffix,
            "status": status,
            "issues": reported_issues,
            "confirmations": confirmations,
            "credits_match_chain": posted is not None and expected_credits is not None
            and abs(posted - expected_credits) <= max(EPSILON, abs(expected_credits) * 1e-9),
            "sender_equals_destination": bool(sender and destination and sender.lower() == destination.lower()),
        })

    failed = sum(1 for item in findings if item.get("status") == "BLOCKED")
    return {
        "scope": "read_only",
        "status": "BLOCKED" if failed or blockers else "PASS",
        "rows_found": len(rows),
        "rows_checked": checked,
        "failed_rows": failed,
        "blockers": sorted(blockers),
        "findings": findings,
    }
