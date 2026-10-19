"""Read-only forensic inventory for historical SLH Exchange release blockers.

This tool inspects the current canonical DB and candidate JSON DB snapshots.
It never writes, repairs, deletes, replays, or changes balances/orders/gates.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Running this file as `python3 tools/exchange_source_forensics.py` puts
# tools/ (not the repository root) on sys.path. Keep repo-root imports reliable.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

TARGET_ORDER_IDS = frozenset({
    "O0000000001", "O0000000003", "O0000000006",
    "O0000000009", "O0000000010", "O0000000011", "O0000000012",
})
MAX_BACKUP_FILES = 120
MAX_BACKUP_BYTES = 30_000_000


def _meta(row: dict) -> dict:
    value = row.get("meta")
    return value if isinstance(value, dict) else {}


def _records(value: Any) -> list[tuple[str, dict]]:
    if isinstance(value, dict):
        return [(str(k), v) for k, v in value.items() if isinstance(v, dict)]
    if isinstance(value, list):
        return [(str(i), v) for i, v in enumerate(value) if isinstance(v, dict)]
    return []


def _uid_suffix(value: Any) -> str | None:
    text = str(value or "")
    return text[-4:] if text else None


def _order_id(row: dict) -> str:
    meta = _meta(row)
    value = row.get("order_id") or meta.get("order_id")
    if value:
        return str(value)
    search = " ".join(
        str(row.get(key) or meta.get(key) or "")
        for key in ("event_id", "correction_id", "idempotency_key")
    )
    return next((oid for oid in TARGET_ORDER_IDS if oid in search), "")


def _order_summary(key: str, row: dict, source: str) -> dict:
    return {
        "source": source,
        "id": str(row.get("order_id") or row.get("id") or key),
        "uid_suffix": _uid_suffix(row.get("uid") or row.get("user_id")),
        "side": row.get("side"),
        "status": row.get("status"),
        "amount": row.get("original_amount"),
        "remaining": row.get("remaining_amount"),
        "price": row.get("limit_price"),
        "reserve_slh": row.get("reserved_slh"),
        "reserve_credits": row.get("reserved_credits"),
        "created": row.get("created_at") or row.get("created"),
        "cancelled": row.get("cancelled_at"),
        "archive_reason": row.get("archive_reason"),
        "archived_at": row.get("archived_at"),
    }


def _event_summary(index: str, row: dict, ledger_name: str) -> dict:
    meta = _meta(row)
    return {
        "ledger": ledger_name,
        "index": index,
        "time": row.get("time") or row.get("timestamp") or row.get("created_at"),
        "order_id": _order_id(row) or None,
        "uid_suffix": _uid_suffix(row.get("uid") or row.get("user_id")),
        "reason": row.get("reason"),
        "kind": row.get("kind"),
        "before": row.get("before"),
        "amount": row.get("amount"),
        "after": row.get("after"),
        "event_id": row.get("event_id") or meta.get("event_id"),
        "correction_id": meta.get("correction_id"),
        "asset": meta.get("asset"),
        "ledger_domain": meta.get("ledger_domain"),
        "source": meta.get("source"),
    }


def _linked_trades(db: dict) -> list[dict]:
    result = []
    for name in ("exchange_trades", "exchange_trade_archive"):
        for key, row in _records(db.get(name, [])):
            buy_id = str(row.get("buy_order_id") or "")
            sell_id = str(row.get("sell_order_id") or "")
            if buy_id not in TARGET_ORDER_IDS and sell_id not in TARGET_ORDER_IDS:
                continue
            result.append({
                "source": name,
                "trade_id": row.get("trade_id") or row.get("id") or key,
                "buy_order_id": buy_id,
                "sell_order_id": sell_id,
                "buyer_uid_suffix": _uid_suffix(row.get("buyer_uid")),
                "seller_uid_suffix": _uid_suffix(row.get("seller_uid")),
                "amount": row.get("slh_amount"),
                "price": row.get("price"),
                "credits_value": row.get("credits_value"),
                "time": row.get("time") or row.get("timestamp") or row.get("created_at"),
            })
    return result


def summarize_db(db: dict, label: str, include_rows: bool = True) -> dict:
    orders = []
    for name in ("exchange_orders", "exchange_order_archive"):
        for key, row in _records(db.get(name, {})):
            order_id = str(row.get("order_id") or row.get("id") or key)
            if order_id in TARGET_ORDER_IDS:
                orders.append(_order_summary(key, row, name))

    events = []
    for name in ("ledger", "slh_token_ledger"):
        for index, row in _records(db.get(name, [])):
            event_id = str(row.get("event_id") or _meta(row).get("event_id") or "")
            evidence_text = " ".join((
                str(row.get("reason") or ""),
                str(_meta(row).get("correction_id") or ""),
                event_id,
            ))
            if (
                _order_id(row) in TARGET_ORDER_IDS
                or any(order_id in evidence_text for order_id in TARGET_ORDER_IDS)
                or "correction:missed_release" in evidence_text
            ):
                events.append(_event_summary(index, row, name))

    trades = _linked_trades(db)
    report = {
        "label": label,
        "order_count": len(orders),
        "event_count": len(events),
        "linked_trade_count": len(trades),
    }
    if include_rows:
        report.update({"orders": orders, "events": events, "trades": trades})
    return report


def backup_inventory(roots: tuple[Path, ...]) -> dict:
    files: dict[Path, tuple[float, int]] = {}
    for root in roots:
        if not root.exists():
            continue
        try:
            for path in root.rglob("*db*.json"):
                if not path.is_file() or path in files:
                    continue
                text = str(path)
                if any(part in text for part in ("/.git/", "/.venv/", "/site-packages/")):
                    continue
                if len(files) >= MAX_BACKUP_FILES:
                    break
                try:
                    stat = path.stat()
                    if stat.st_size <= MAX_BACKUP_BYTES:
                        files[path] = (stat.st_mtime, stat.st_size)
                except OSError:
                    continue
        except OSError:
            continue

    candidates = []
    live_path = Path("/app/state/db.json")
    for path, (modified, size) in files.items():
        if path == live_path:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            summary = summarize_db(data, str(path), include_rows=False)
            if summary["order_count"] or summary["event_count"]:
                candidates.append((modified, size, path, summary, data))
        except (OSError, ValueError, UnicodeError):
            continue

    candidates.sort(key=lambda item: item[0], reverse=True)
    compact = []
    for modified, size, path, summary, _data in candidates[:8]:
        compact.append({
            "path": str(path),
            "mtime_utc": datetime.fromtimestamp(modified, timezone.utc).isoformat(),
            "bytes": size,
            "orders": summary["order_count"],
            "events": summary["event_count"],
            "trades": summary["linked_trade_count"],
        })

    detailed = []
    if candidates:
        selected = [candidates[0]]
        # Prefer a second snapshot with the same order/event shape and a distinct timestamp.
        for candidate in candidates[1:]:
            if candidate[2] != selected[0][2]:
                selected.append(candidate)
                break
        focus_ids = {"O0000000006", "O0000000009", "O0000000010", "O0000000011", "O0000000012"}
        for modified, size, path, _summary, data in selected:
            details = summarize_db(data, str(path), include_rows=True)
            details["mtime_utc"] = datetime.fromtimestamp(modified, timezone.utc).isoformat()
            details["orders"] = [{k: v for k, v in row.items() if v is not None} for row in details["orders"]]
            details["events"] = [{k: v for k, v in row.items() if v is not None} for row in details["events"] if row.get("order_id") in focus_ids][:24]
            details["trades"] = [{k: v for k, v in row.items() if v is not None} for row in details["trades"]]
            detailed.append(details)
    return {
        "files_scanned": len(files),
        "matching_snapshots": len(candidates),
        "candidates": compact,
        "details": detailed,
    }


def main() -> int:
    import state_manager
    from core.account_ledger_audit import audit_account_ledger
    from core.slh_exchange_reconciliation import audit_db
    from core.system_checks import check_bnb, check_exchange, check_money, check_ton

    uid = "8789977826"
    db = state_manager.load_db()
    audit = audit_db(db)
    audit_summary = {
        key: audit.get(key) for key in (
            "status", "operational_status", "release_readiness_status",
            "blocking_finding_count", "historical_finding_count",
            "checked_cancelled_sell_orders", "finding_count",
            "release_blocking_finding_count",
        ) if key in audit
    }
    gate_names = (
        "SLH_EXCHANGE_PUBLIC_OPEN", "BNB_DEPOSITS_OPEN",
        "TON_DEPOSITS_OPEN", "SLH_BSC_EXECUTION_ENABLED",
        "SLH_BSC_BROADCAST_ENABLED",
    )
    gates = {}
    for key in gate_names:
        value = os.getenv(key)
        gates[key] = value if value in {"0", "1"} else ("UNSET" if value is None else "SET_NON_BOOLEAN")

    exchange = check_exchange(db)
    exchange_summary = {
        key: exchange.get(key) for key in (
            "ok", "public_gate", "public_ready", "verdict", "open_orders",
            "test_seed_open", "recent_trades", "test_seed_trades",
            "order_book_integrity", "trade_integrity", "money_invariants", "detail",
        )
    }
    ledger = audit_account_ledger(db, uid)
    ledger_summary = {
        key: ledger.get(key) for key in (
            "status", "rows_checked", "credits_sequence_rows_checked",
            "non_credits_rows_skipped", "continuity_break_count",
            "arithmetic_error_count", "malformed_global_rows",
            "current_wallet_credits", "ledger_tail_after",
            "current_balance_matches_tail", "blockers", "findings",
        )
    }
    bnb = check_bnb()
    bnb_summary = {
        key: bnb.get(key) for key in (
            "ok", "public_open", "flag_open", "ready", "launch_ready",
            "empirical_status", "evidence_status", "historical_deposits_status",
            "historical_deposits_found", "historical_deposits_failed",
            "live_rpc_status", "confirmations_required", "gate_reasons",
            "blockers", "warnings", "next_action",
        )
    }
    ton = check_ton(uid)
    ton_summary = {
        key: ton.get(key) for key in (
            "ok", "public_open", "flag_open", "ready", "rate",
            "replay_evidence", "blockers", "warnings", "next_action",
        ) if key in ton
    }
    money = check_money(uid)
    money_summary = {
        "ok": money.get("ok"), "detail": money.get("detail"),
        "checks": money.get("checks"),
    }

    print("EXCHANGE_RELEASE_AUDIT", json.dumps(audit_summary, ensure_ascii=False, default=str))
    print("EFFECTIVE_ENV_FLAGS", json.dumps(gates, ensure_ascii=False))
    print("CURRENT_EXCHANGE_CHECK", json.dumps(exchange_summary, ensure_ascii=False, default=str))
    print("OWNER_CREDITS_AUDIT", json.dumps(ledger_summary, ensure_ascii=False, default=str))
    print("BNB_READINESS_LIVE_RPC_READ_ONLY", json.dumps(bnb_summary, ensure_ascii=False, default=str))
    print("TON_READINESS", json.dumps(ton_summary, ensure_ascii=False, default=str))
    print("MONEY_INVARIANTS", json.dumps(money_summary, ensure_ascii=False, default=str))
    print("LIVE_SOURCE_ROWS", json.dumps(summarize_db(db, "LIVE"), ensure_ascii=False, default=str))
    roots = (
        Path("/app/state"), Path("/app/_slh_audit"),
        Path("/app/backups"), Path("/app/backup"),
    )
    print("BACKUP_SOURCE_INVENTORY", json.dumps(backup_inventory(roots), ensure_ascii=False, default=str))
    print("READ_ONLY=TRUE NO_DB_WRITES=TRUE NO_LEDGER_WRITES=TRUE NO_BALANCE_CHANGES=TRUE NO_GATE_CHANGES=TRUE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
