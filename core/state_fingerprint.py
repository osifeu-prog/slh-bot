"""Read-only, non-PII fingerprints for SLH JSON state files.

This module never writes to the database and never returns row-level values.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import state_manager


MAX_STATE_BYTES = 128 * 1024 * 1024
FINGERPRINT_COLLECTIONS = (
    "users",
    "ledger",
    "slh_token_ledger",
    "transactions",
    "exchange_orders",
    "exchange_trades",
    "purchases",
    "processed_transfers",
    "used_ton_txs",
    "used_bnb_txs",
    "ton_deposit_intents",
    "bnb_deposits",
    "slh_deposit_intents",
    "withdrawals",
    "withdrawal_requests",
    "staking_requests",
    "stake_positions",
    "stars_payments",
    "stars_invoices",
    "credit_ledger",
    "revenue_ledger",
)


def _file_identity(stat_result: Any) -> tuple[int, int, int, int, int]:
    return (
        int(stat_result.st_dev),
        int(stat_result.st_ino),
        int(stat_result.st_size),
        int(stat_result.st_mtime_ns),
        int(stat_result.st_ctime_ns),
    )


def build_local_state_fingerprint() -> dict[str, Any]:
    """Hash the exact local JSON file under the shared state lock.

    The response contains only hashes, file metadata, root-key names and
    aggregate collection types/counts. It never emits user IDs, balances,
    transactions, ledger rows, wallet addresses, credentials or raw exceptions.
    """
    configured_path = Path(str(state_manager.DB_FILE)).expanduser()
    path = configured_path if configured_path.is_absolute() else Path.cwd() / configured_path

    with state_manager._db_lock():
        before = path.stat()
        if before.st_size < 0 or before.st_size > MAX_STATE_BYTES:
            raise ValueError("STATE_FILE_SIZE_OUT_OF_RANGE")
        raw = path.read_bytes()
        after = path.stat()

    if _file_identity(before) != _file_identity(after):
        raise ValueError("STATE_FILE_CHANGED_DURING_READ")

    try:
        database = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("STATE_FILE_INVALID_JSON") from exc
    if not isinstance(database, dict) or not isinstance(database.get("users"), dict):
        raise ValueError("STATE_ROOT_INVALID")

    collections: dict[str, dict[str, Any]] = {}
    for key in FINGERPRINT_COLLECTIONS:
        if key not in database:
            collections[key] = {"type": "missing", "count": None}
            continue
        value = database[key]
        if isinstance(value, dict):
            collections[key] = {"type": "object", "count": len(value)}
        elif isinstance(value, list):
            collections[key] = {"type": "array", "count": len(value)}
        else:
            # Do not serialize or return the value itself.
            collections[key] = {"type": type(value).__name__, "count": None}

    root_keys = sorted(str(key) for key in database.keys())
    schema_descriptor = {
        "root_keys": root_keys,
        "collections": {
            key: value["type"] for key, value in sorted(collections.items())
        },
    }
    schema_bytes = json.dumps(
        schema_descriptor, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")

    return {
        "ok": True,
        "status": "PASS",
        "source": "state_manager_json",
        "read_only": True,
        "runtime": {
            "railway_project_id": os.getenv("RAILWAY_PROJECT_ID") or None,
            "railway_environment_id": os.getenv("RAILWAY_ENVIRONMENT_ID") or None,
            "railway_service_id": os.getenv("RAILWAY_SERVICE_ID") or None,
            "run_bot": os.getenv("RUN_BOT", "unset"),
        },
        "snapshot": {
            "file_name": path.name,
            "path_kind": "absolute" if configured_path.is_absolute() else "relative",
            "size_bytes": len(raw),
            "mtime_ns": int(after.st_mtime_ns),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "schema_sha256": hashlib.sha256(schema_bytes).hexdigest(),
            "root_key_count": len(root_keys),
            "root_keys": root_keys,
            "collections": collections,
        },
    }
