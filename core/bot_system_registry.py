"""Unified read-only SLH bot/system inventory.

This module joins:
- Bot Factory runtime metadata in state/db.json
- BotFather declarations
- non-secret Railway target registry
- encrypted Vault metadata (never decrypted here)
- BNB/TON effective deposit gate state

It is a read model only: it never enables trading or settlement and never
returns a Telegram token.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import state_manager

from core import bot_catalog, bot_registry, telegram_token_registry


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _key(username: str) -> str:
    value = str(username or "").strip().lstrip("@")
    return value.lower()


def _declared() -> dict[str, str]:
    out: dict[str, str] = {}
    for username in bot_catalog.BOTFATHER_DECLARED:
        clean = str(username).strip().lstrip("@")
        if clean:
            out[_key(clean)] = clean
    return out


def _static_targets() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for item in telegram_token_registry.list_bots():
        username = str(item.get("username") or "").strip().lstrip("@")
        if not username:
            continue
        out[_key(username)] = deepcopy(item.get("targets") or [])
    return out


def _vault_index() -> dict[str, dict]:
    db = state_manager.load_db()
    raw = db.get("bot_vault") or {}
    if not isinstance(raw, dict):
        return {}
    out = {}
    for username, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        # Deliberately omit token_enc. The read model exposes metadata only.
        item = dict(entry)
        item.pop("token_enc", None)
        item["encrypted"] = bool(entry.get("token_enc"))
        item["open_exposures"] = len(
            [x for x in (entry.get("exposures") or []) if isinstance(x, dict) and not x.get("resolved_at")]
        )
        item.pop("exposures", None)
        out[_key(username)] = item
    return out


def _finance() -> dict:
    try:
        from core.bnb_gate import bnb_deposits_open
        bnb_flag = bnb_deposits_open()
    except Exception as exc:
        bnb_flag = False
        bnb_error = type(exc).__name__
    else:
        bnb_error = None

    try:
        from core.ton_deposit_service import deposits_are_open
        ton_ready = deposits_are_open()
    except Exception as exc:
        ton_ready = False
        ton_error = type(exc).__name__
    else:
        ton_error = None

    return {
        "bnb": {
            "gate": "OPEN" if bnb_flag else "CLOSED",
            "settlement_policy": "BOUND_WALLET + ONCHAIN_TX + CONFIRMATIONS",
            "error": bnb_error,
        },
        "ton": {
            "gate": "OPEN" if ton_ready else "CLOSED",
            "settlement_policy": "BOUND_WALLET + TREASURY + MEMO + IDEMPOTENCY",
            "error": ton_error,
        },
        "live_trading": {
            "status": "NOT_ENABLED_BY_THIS_READ_MODEL",
            "note": "Inventory visibility does not enable exchange execution or external-asset trading.",
        },
    }


def snapshot(owner_id=None) -> dict:
    declarations = _declared()
    targets = _static_targets()
    vault = _vault_index()
    runtime = bot_registry.list_bots(owner_id=owner_id)

    by_key: dict[str, dict] = {}

    for username in declarations.values():
        key = _key(username)
        by_key.setdefault(key, {
            "username": "@" + username,
            "declared": True,
            "sources": [],
        })
        by_key[key]["sources"].append("botfather")

    for record in runtime:
        username = str(record.get("telegram_username") or "").strip().lstrip("@")
        key = _key(username)
        if not key:
            # A factory-only bot still belongs in the inventory via bot id.
            key = _key(record.get("id"))
        row = by_key.setdefault(key, {
            "username": "@" + username if username else "",
            "declared": False,
            "sources": [],
        })
        row["factory"] = {
            "id": record.get("id"),
            "name": record.get("name"),
            "role": record.get("role"),
            "template": record.get("template"),
            "status": record.get("status"),
            "health": record.get("health"),
            "telemetry_status": record.get("telemetry_status"),
            "lifecycle": record.get("lifecycle"),
            "last_heartbeat_at": record.get("last_heartbeat_at"),
            "last_heartbeat_status": record.get("last_heartbeat_status"),
            "railway_project_id": record.get("railway_project_id"),
            "railway_service_id": record.get("railway_service_id"),
            "railway_environment_id": record.get("railway_environment_id"),
        }
        if "bot_factory" not in row["sources"]:
            row["sources"].append("bot_factory")
        if username:
            row["username"] = "@" + username

    for key, item in vault.items():
        username = str(item.get("username") or key).lstrip("@")
        row = by_key.setdefault(key, {
            "username": "@" + username,
            "declared": False,
            "sources": [],
        })
        row["vault"] = {
            "encrypted": bool(item.get("encrypted")),
            "token_tail": item.get("token_tail", ""),
            "module": item.get("module", "home"),
            "role": item.get("role", "redirect"),
            "open_exposures": item.get("open_exposures", 0),
            "updated_at": item.get("updated_at"),
            "rotated_at": item.get("rotated_at"),
        }
        if "vault" not in row["sources"]:
            row["sources"].append("vault")

    for key, item_targets in targets.items():
        row = by_key.setdefault(key, {
            "username": "@" + key,
            "declared": False,
            "sources": [],
        })
        row["railway_targets"] = [
            {
                "project": t.get("project"),
                "project_id": t.get("project_id"),
                "environment": t.get("environment"),
                "environment_id": t.get("environment_id"),
                "service": t.get("service"),
                "service_id": t.get("service_id"),
                "variable": t.get("variable"),
            }
            for t in item_targets
        ]
        if "telegram_registry" not in row["sources"]:
            row["sources"].append("telegram_registry")

    rows = sorted(
        by_key.values(),
        key=lambda item: str(item.get("username") or "").lower(),
    )
    return {
        "updated_at": _now(),
        "count": len(rows),
        "bots": rows,
        "finance": _finance(),
        "security": {
            "raw_tokens_in_read_model": False,
            "raw_tokens_in_db_registry": False,
            "vault_decryption_performed": False,
        },
    }


def report(owner_id=None, max_chars: int = 3800) -> str:
    data = snapshot(owner_id=owner_id)
    lines = [
        "🤖 SLH CENTRAL BOT CONTROL",
        "",
        f"Bots indexed: {data['count']}",
        "Sources: BotFather · Bot Factory · Vault · Telegram/Railway registry",
        "",
    ]
    for row in data["bots"]:
        username = row.get("username") or "(factory-only)"
        factory = row.get("factory") or {}
        vault = row.get("vault") or {}
        targets = row.get("railway_targets") or []
        state = factory.get("health") or factory.get("status") or "UNKNOWN"
        token_state = (
            f"vault=🔐{vault.get('token_tail','')}:{vault.get('module','home')}"
            if vault else "vault=—"
        )
        server_state = (
            "server=" + ",".join(str(t.get("service") or "?") for t in targets)
            if targets else "server=—"
        )
        lines.append(f"• {username} | {state} | {token_state} | {server_state}")

    lines += [
        "",
        f"BNB gate: {data['finance']['bnb']['gate']}",
        f"TON gate: {data['finance']['ton']['gate']}",
        "Trading execution: not enabled by this inventory layer.",
        "",
        "🔒 Tokens are never displayed; Vault shows only encrypted metadata and tail.",
    ]
    text = "\n".join(lines)
    return text[:max_chars]
