"""Owner-only read-only system snapshot.

The snapshot is designed for operator/AI context. It never mutates state and
never returns secret values.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from io import BytesIO

import state_manager
from core.authority import is_owner


def _load_db() -> dict:
    try:
        return state_manager.load_db()
    except Exception:
        return {}


def _git_info() -> dict:
    return {
        "commit": os.getenv("RAILWAY_GIT_COMMIT_SHA", "unknown")[:12],
        "branch": os.getenv("RAILWAY_GIT_BRANCH", "main")[:80],
        "message": (os.getenv("RAILWAY_GIT_COMMIT_MESSAGE", "") or "")[:120],
        "deployment_id": os.getenv("RAILWAY_DEPLOYMENT_ID", "unknown")[:12],
        "environment": os.getenv("RAILWAY_ENVIRONMENT_NAME", "unknown")[:80],
    }


def _db_stats(db: dict) -> dict:
    users = db.get("users", {}) or {}
    stakes = db.get("stake_positions", {}) or {}
    locked = sum(
        1
        for position in stakes.values()
        if isinstance(position, dict) and str(position.get("status", "")).lower() == "locked"
    )

    now = int(time.time())
    vip_active = sum(
        1
        for user in users.values()
        if isinstance(user, dict)
        and int(user.get("vip_access_until", 0) or 0) > now
    )

    return {
        "users": len(users),
        "ledger": len(db.get("ledger", []) or []),
        "stakes_total": len(stakes),
        "stakes_locked": locked,
        "stakes_unlocked": max(0, len(stakes) - locked),
        "bnb_bindings": len(db.get("wallet_bindings", {}) or {}),
        "ton_bindings": len(db.get("ton_wallet_bindings", {}) or {}),
        "star_orders": len(db.get("star_item_orders", {}) or {}),
        "vip_active": vip_active,
        "vip_subscriptions": len(db.get("vip_subscriptions", {}) or {}),
    }


def _revenue_stats(db: dict) -> dict:
    rows = db.get("revenue_ledger", [])
    if not isinstance(rows, list):
        rows = []

    canonical = [
        row
        for row in rows
        if isinstance(row, dict)
        and str(row.get("currency", "")).upper() == "XTR"
        and float(row.get("amount", 0) or 0) > 0
        and str(row.get("reference", "")).strip()
    ]

    customers = {
        str(row.get("uid"))
        for row in canonical
        if row.get("uid") not in (None, "")
    }

    return {
        "stars_total": sum(float(row.get("amount", 0) or 0) for row in canonical),
        "customers": len(customers),
        "events": len(canonical),
    }


def _ton_stats(db: dict) -> dict:
    settings = db.get("ton_settings", {}) or {}
    rate_raw = os.getenv("TON_CREDITS_PER_TON", "").strip() or settings.get("credits_per_ton")
    if rate_raw in (None, "", 0):
        rate_raw = settings.get("rate")

    wallet = os.getenv("TON_WALLET", "").strip() or settings.get("wallet") or ""
    try:
        rate = float(rate_raw)
    except (TypeError, ValueError):
        rate = None

    try:
        from core.ton_deposit_service import deposits_are_open

        open_now = bool(deposits_are_open())
    except Exception:
        open_now = False

    return {
        "rate": rate,
        "wallet_prefix": (str(wallet)[:20] + "...") if wallet else "",
        "open": open_now,
        "in_safety_band": bool(rate is not None and 100 <= rate <= 110),
    }


def _bsc_stats(db: dict) -> dict:
    try:
        from core.binance_connector import get_bsc_config

        cfg = get_bsc_config() or {}
    except Exception:
        cfg = {}

    override = db.get("bsc_settings", {}) or {}
    cfg = {**cfg, **override}

    treasury = str(cfg.get("treasury_wallet") or "")
    return {
        "network": cfg.get("network", "bsc"),
        "chain_id": cfg.get("chain_id"),
        "treasury_prefix": (treasury[:20] + "...") if treasury else "",
        "confirmations": int(cfg.get("confirmations") or 15),
    }


def _bridge_stats() -> dict:
    try:
        from core.device_read_model import get_device_status

        pc = get_device_status("PC_Osif2", ttl_seconds=120)
        age = pc.get("age_seconds")
        return {
            "status": pc.get("status", "unknown"),
            "icon": pc.get("status_icon", "⚪️"),
            "age_seconds": int(age) if age is not None else None,
        }
    except Exception as exc:
        return {"status": "error", "error": type(exc).__name__}


def build_snapshot() -> dict:
    db = _load_db()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git": _git_info(),
        "db": _db_stats(db),
        "revenue": _revenue_stats(db),
        "ton": _ton_stats(db),
        "bsc": _bsc_stats(db),
        "bridge": _bridge_stats(),
    }


def _format(snapshot: dict) -> str:
    git = snapshot["git"]
    db = snapshot["db"]
    revenue = snapshot["revenue"]
    ton = snapshot["ton"]
    bsc = snapshot["bsc"]
    bridge = snapshot["bridge"]

    return "\n".join(
        [
            "📸 SLH OS — SNAPSHOT",
            f"🕒 {snapshot['generated_at']}",
            "",
            "🔀 GIT",
            f"  commit: {git['commit']} ({git['branch']})",
            f"  deploy: {git['deployment_id']}",
            f"  env:    {git['environment']}",
            "",
            "📊 DB",
            f"  users:        {db['users']}",
            f"  ledger:       {db['ledger']}",
            f"  stakes:       {db['stakes_locked']} locked / {db['stakes_total']} total",
            f"  bnb bindings: {db['bnb_bindings']}",
            f"  ton bindings: {db['ton_bindings']}",
            f"  star orders:  {db['star_orders']}",
            f"  vip active:   {db['vip_active']}",
            f"  vip subs:     {db['vip_subscriptions']}",
            "",
            "💰 REVENUE",
            f"  stars:     {revenue['stars_total']:g}",
            f"  customers: {revenue['customers']}",
            f"  events:    {revenue['events']}",
            "",
            "💎 TON",
            f"  rate:    {ton['rate']}",
            f"  open:    {ton['open']}",
            f"  in band: {ton['in_safety_band']}",
            "",
            "🪙 BSC",
            f"  network:       {bsc['network']}",
            f"  chain_id:      {bsc['chain_id']}",
            f"  confirmations: {bsc['confirmations']}",
            "",
            "🔗 BRIDGE",
            f"  PC_Osif2: {bridge.get('icon')} {bridge.get('status')} ({bridge.get('age_seconds')}s)",
        ]
    )


def register(bot, context=None) -> None:
    @bot.message_handler(commands=["snapshot"])
    def snapshot_cmd(message):
        if not is_owner(message):
            bot.reply_to(message, "⛔️ OWNER only")
            return

        try:
            snapshot = build_snapshot()
            parts = (message.text or "").split(maxsplit=1)
            mode = parts[1].strip().lower() if len(parts) > 1 else ""

            if mode == "json":
                payload = json.dumps(snapshot, ensure_ascii=False, indent=2)
                bot.reply_to(message, payload[:3900])
                return

            bot.reply_to(message, _format(snapshot))

            if mode == "file":
                data = json.dumps(snapshot, ensure_ascii=False, indent=2).encode("utf-8")
                document = BytesIO(data)
                document.name = f"snapshot_{int(time.time())}.json"
                bot.send_document(message.chat.id, document)

        except Exception:
            bot.reply_to(message, "❌ snapshot failed safely")


print("✅ snapshot_handler registered")
