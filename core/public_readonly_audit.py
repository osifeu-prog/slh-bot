"""Safe read-only operational snapshots for authenticated Telegram users.

This module intentionally exposes only sanitized readiness/health fields. It never
runs shell commands, returns secrets, or changes system state.
"""
from __future__ import annotations


def health_snapshot() -> dict:
    from core.system_check import run_system_checks

    raw = run_system_checks()
    checks = []
    for item in raw.get("checks", []):
        checks.append({
            "name": str(item.get("name", "")),
            "status": str(item.get("status", "")),
        })
    return {
        "status": str(raw.get("status", "FAIL")),
        "passed": int(raw.get("passed", 0) or 0),
        "failed": int(raw.get("failed", 0) or 0),
        "total": int(raw.get("total", 0) or 0),
        "checks": checks,
        "scope": "public_read_only",
    }


def bnb_snapshot() -> dict:
    from core.bnb_gate import bnb_readiness, bnb_opening_evidence

    gate = bnb_readiness()
    evidence = bnb_opening_evidence()
    checks = evidence.get("checks", {})
    pending = [
        name
        for name, item in checks.items()
        if isinstance(item, dict) and item.get("status") == "PENDING_EMPIRICAL"
    ]
    return {
        "flag_open": bool(gate.get("flag_open")),
        "ready": bool(gate.get("ready")),
        "effective_open": bool(gate.get("effective_open")),
        "chain_id": int(gate.get("chain_id") or 0),
        "network": str(gate.get("network") or ""),
        "confirmations_required": int(gate.get("confirmations_required") or 0),
        "reasons": list(gate.get("reasons") or []),
        "opening_status": str(evidence.get("status") or "BLOCKED"),
        "empirical_pending": pending,
        "scope": "public_read_only",
    }


def ton_snapshot() -> dict:
    from core.ton_deposit_service import deposits_are_open, _settings

    treasury, rate = _settings()
    rate_value = float(rate) if rate is not None else None
    return {
        "deposits_open": bool(deposits_are_open()),
        "wallet_configured": bool(str(treasury or "").strip()),
        "credits_per_ton": str(rate) if rate is not None else None,
        "rate_valid": rate_value is not None and 100 <= rate_value <= 110,
        "scope": "public_read_only",
    }


def snapshot() -> dict:
    return {
        "health": health_snapshot(),
        "bnb": bnb_snapshot(),
        "ton": ton_snapshot(),
        "scope": "public_read_only",
    }


def render(command: str) -> str:
    command = str(command or "").strip().lower()
    if command == "health":
        s = health_snapshot()
        lines = [
            "🔎 SLH HEALTH — READ ONLY",
            f"• Status: {s['status']}",
            f"• Checks: {s['passed']}/{s['total']} passed",
        ]
        for item in s["checks"]:
            icon = "🟢" if item["status"] == "PASS" else "🔴"
            lines.append(f"{icon} {item['name']}: {item['status']}")
        return "\n".join(lines)

    if command == "bnb_readiness":
        s = bnb_snapshot()
        lines = [
            "🔐 BNB READINESS — READ ONLY",
            f"• Config ready: {s['ready']}",
            f"• Settlement open: {s['effective_open']}",
            f"• Chain: BSC / {s['chain_id']}",
            f"• Confirmations: {s['confirmations_required']}",
            f"• Opening evidence: {s['opening_status']}",
        ]
        if s["reasons"]:
            lines.append("• Reasons: " + ", ".join(s["reasons"]))
        if s["empirical_pending"]:
            lines.append("• Empirical pending: " + ", ".join(s["empirical_pending"]))
        return "\n".join(lines)

    if command == "ton_readiness":
        s = ton_snapshot()
        return "\n".join([
            "💎 TON READINESS — READ ONLY",
            f"• Deposit settlement open: {s['deposits_open']}",
            f"• Treasury configured: {s['wallet_configured']}",
            f"• Rate: {s['credits_per_ton'] or 'unset'} Credits / TON",
            f"• Rate safety band: {'PASS' if s['rate_valid'] else 'FAIL'}",
        ])

    raise ValueError("PUBLIC_READONLY_COMMAND_UNSUPPORTED")
