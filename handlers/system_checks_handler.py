"""Owner/admin/developer read-only system checks for SLH OS."""

from __future__ import annotations

from core.authority import get_role, is_owner
from core.release_readiness import build_release_report
from core.system_checks import (
    check_bnb,
    check_commands,
    check_exchange,
    check_exchange_for_execution,
    check_db,
    check_money,
    check_ton,
    check_ux,
)


_ALLOWED_ROLES = {"OWNER", "ADMIN", "DEVELOPER"}


def _allowed(message) -> bool:
    role = get_role(str(message.from_user.id))
    if role not in _ALLOWED_ROLES:
        message._slh_check_denied_role = role
        return False
    return True


def _send_denied(bot, message) -> None:
    role = getattr(message, "_slh_check_denied_role", "UNKNOWN")
    bot.reply_to(message, f"⛔ System checks require OWNER/ADMIN/DEVELOPER. Role: {role}")


def _icon(ok: bool) -> str:
    return "✅" if ok else "⛔️"


def _fmt_check(name: str, result: dict) -> str:
    return f"{_icon(bool(result.get('ok')))} {name}: {result.get('detail', 'no detail')}"

def _safe_report_fragment(value, limit=100):
    """Keep audit display fields single-line and bounded."""
    return " ".join(str(value if value is not None else "").split())[:limit] or "—"


def _exchange_reserves_output(report):
    """Render a bounded read-only reserve report, failing closed on malformed results."""
    is_dict = isinstance(report, dict)
    report = report if is_dict else {}
    status = str(report.get("release_readiness_status") or "").upper()

    raw_findings = report.get("release_blocking_findings")
    findings_is_list = isinstance(raw_findings, list)
    findings = raw_findings if findings_is_list else []
    findings_are_dicts = all(isinstance(item, dict) for item in findings)

    raw_count = report.get("release_blocking_finding_count")
    count_is_int = isinstance(raw_count, int) and not isinstance(raw_count, bool) and raw_count >= 0
    count_matches = count_is_int and raw_count == len(findings)
    count = max(raw_count if count_is_int else 0, len(findings))
    status_matches_count = (
        (status == "PASS" and count_is_int and raw_count == 0 and not findings)
        or (status == "BLOCKED" and count_is_int and raw_count > 0)
    )

    valid_report = (
        is_dict
        and report.get("read_only") is True
        and status in {"PASS", "BLOCKED"}
        and findings_is_list
        and findings_are_dicts
        and count_matches
        and status_matches_count
    )
    release_pass = valid_report and status == "PASS" and count == 0 and not findings

    checked = report.get("checked_cancelled_sell_orders", 0)
    try:
        checked = max(0, int(checked))
    except (TypeError, ValueError, OverflowError):
        checked = 0

    lines = [
        "🧾 SLH EXCHANGE RESERVE AUDIT — READ ONLY",
        "",
        f"Release readiness: {'PASS' if release_pass else 'BLOCKED'}",
        f"Audit integrity: {'PASS' if valid_report else 'BLOCKED'}",
        f"Operational status: {_safe_report_fragment(report.get('operational_status'), 30)}",
        f"Cancelled sell reserve orders checked: {checked}",
        f"All findings: {_safe_report_fragment(report.get('finding_count', 'UNKNOWN'), 30)}",
        f"Findings requiring release review: {count}",
    ]

    if not valid_report:
        lines.append("Blocker: RESERVE_AUDIT_RESULT_INVALID")
        if count_is_int and raw_count != len(findings):
            lines.append("Blocker: RESERVE_AUDIT_COUNT_MISMATCH")
        elif status not in {"PASS", "BLOCKED"} or not status_matches_count:
            lines.append("Blocker: RESERVE_AUDIT_STATUS_COUNT_MISMATCH")

    shown = 0
    for item in findings[:12]:
        if not isinstance(item, dict):
            lines.append("• MALFORMED_FINDING")
            shown += 1
            continue
        parts = [
            _safe_report_fragment(item.get("code"), 90),
            f"order={_safe_report_fragment(item.get('order_id'), 60)}",
            f"ledger={_safe_report_fragment(item.get('ledger'), 30)}",
        ]
        classification = item.get("operational_classification")
        if classification:
            parts.append(f"class={_safe_report_fragment(classification, 45)}")
        for key, label in (
            ("reserve_delta", "reserve"),
            ("normal_release_delta", "normal_release"),
            ("correction_delta", "correction"),
        ):
            if key in item:
                parts.append(f"{label}={_safe_report_fragment(item.get(key), 45)}")
        event_ids = item.get("event_ids")
        if isinstance(event_ids, list) and event_ids:
            parts.append("events=" + ",".join(_safe_report_fragment(v, 45) for v in event_ids[:2]))
        elif item.get("event_id"):
            parts.append(f"event={_safe_report_fragment(item.get('event_id'), 60)}")
        lines.append("• " + " | ".join(parts))
        note = _safe_report_fragment(item.get("note"), 150)
        if note != "—":
            lines.append("  " + note)
        shown += 1

    if count > shown:
        lines.append(f"… {count - shown} additional release findings omitted; inspect the full audit.")
    elif len(findings) > 12:
        lines.append(f"… {len(findings) - 12} more findings omitted.")
    lines += [
        "",
        "🔒 No balances, orders, ledgers, wallets, or gates were changed.",
    ]
    return "\n".join(lines)[:3900]

def _check_output(uid: str) -> str:
    db = check_db()
    commands = check_commands()
    ux = check_ux()
    money = check_money(uid)
    bnb = check_bnb()
    ton = check_ton(uid)
    exchange = check_exchange()

    lines = [
        "🧪 SLH SYSTEM CHECK — READ ONLY",
        "",
        _fmt_check("DB", db),
        _fmt_check("Commands", commands),
        _fmt_check("Mini App UX", ux),
        _fmt_check("Money / invariants", money),
        _fmt_check("BNB", bnb),
        _fmt_check("TON", ton),
        _fmt_check("Internal Exchange", exchange),
        "",
        "🔒 אין שינוי DB / balances / wallets / settlement / gates.",
        "🧭 לדוח Go-Live מאוחד: /go_live_report\n"
        "ℹ️ לפירוט: /check_ux · /check_money · /check_bnb · /check_ton · /check_exchange",
    ]
    return "\n".join(lines)[:3900]



def _release_icon(status: str) -> str:
    return {
        "GREEN": "✅",
        "DEGRADED": "🟡",
        "BLOCKED": "⛔️",
    }.get(str(status or "").upper(), "⚪️")


def _go_live_report_output(uid: str) -> str:
    """One-message, read-only launch report with explicit fail-closed gates."""
    report = build_release_report()
    db = check_db()
    commands = check_commands()
    ux = check_ux()
    money = check_money(uid)
    bnb = check_bnb()
    ton = check_ton(uid)

    # Include the bounded live Telegram → MCP → Control Plane proof in this
    # single owner report. This check is read-only and never exposes secrets.
    try:
        from handlers.mcp_proof_handler import read_mcp_proof

        mcp_proof = read_mcp_proof()
    except Exception as exc:
        mcp_proof = {
            "ok": False,
            "status": "ERROR",
            "detail": f"MCP proof failed safely ({type(exc).__name__})",
        }
    mcp_ok = mcp_proof.get("ok") is True and mcp_proof.get("status") == "PASS"
    mcp_runtime = mcp_proof.get("runtime")
    mcp_runtime = mcp_runtime if isinstance(mcp_runtime, dict) else {}
    mcp_detail = str(
        mcp_proof.get("detail") or mcp_proof.get("status") or "MCP proof unavailable"
    ).replace("\n", " ")[:160]
    mcp_runtime_detail = (
        f"runtime_state={mcp_runtime.get('state', 'UNKNOWN')} · "
        f"running={mcp_runtime.get('running', 'UNKNOWN')} · "
        f"boot_ok={mcp_runtime.get('boot_ok', 'UNKNOWN')} · "
        f"agent_count={mcp_runtime.get('agent_count', 'UNKNOWN')}"
    )

    try:
        import state_manager
        execution = check_exchange_for_execution(state_manager.load_db())
    except Exception as exc:
        execution = {
            "execution_ready": False,
            "public_gate": "UNKNOWN",
            "verdict": "BLOCKED",
            "detail": f"fresh preflight failed: {type(exc).__name__}",
        }

    overall = str(report.get("overall_status") or "UNKNOWN").upper()
    lines = [
        "🧭 SLH OS GO-LIVE REPORT — READ ONLY",
        "",
        f"Overall release readiness: {_release_icon(overall)} {overall}",
        "",
        "Release gates:",
    ]
    for name, row in (report.get("checks") or {}).items():
        status = str(row.get("status") or "BLOCKED").upper()
        detail = str(row.get("detail") or "no detail").replace("\n", " ")
        lines.append(
            f"{_release_icon(status)} {name}: {status} · {detail[:180]}"
        )

    lines += [
        "",
        "System integrity:",
        _fmt_check("DB", db),
        _fmt_check("Commands", commands),
        _fmt_check("Mini App UX", ux),
        _fmt_check("Money / invariants", money),
        "",
        f"{_release_icon('GREEN' if mcp_ok else 'BLOCKED')} "
        f"Automation bridge (Telegram → MCP → Control Plane): "
        f"{'PASS' if mcp_ok else 'BLOCKED'} · {mcp_detail} · {mcp_runtime_detail}",
    ]

    execution_ready = execution.get("execution_ready") is True
    execution_status = "PASS" if execution_ready else "BLOCKED"
    lines += [
        "",
        f"{_release_icon('GREEN' if execution_ready else 'BLOCKED')} "
        f"Current Exchange execution preflight: {execution_status}",
        f"Gate: {execution.get('public_gate', 'UNKNOWN')} · "
        f"Verdict: {execution.get('verdict', 'UNKNOWN')} · "
        f"{str(execution.get('detail') or 'no detail')[:160]}",
        "This preflight is only a snapshot. Every Buy/Sell order rechecks "
        "canonically inside the atomic mutation and returns an execution receipt.",
    ]

    if bnb.get("ok"):
        bnb_icon = "✅"
        bnb_state = "OPEN · empirical settlement PASS"
    elif not bnb.get("public_open") and bnb.get("ready") and bnb.get("launch_ready"):
        bnb_icon = "🟡"
        bnb_state = "SAFE CLOSED · configuration PASS · empirical settlement PASS · pending operator review"
    elif not bnb.get("public_open") and bnb.get("ready") and not bnb.get("launch_ready"):
        bnb_icon = "🟡"
        bnb_state = (
            "SAFE CLOSED · configuration PASS · empirical settlement "
            + str(bnb.get("empirical_status") or "PENDING_EMPIRICAL")
        )
    else:
        bnb_icon = "⛔️"
        bnb_state = (
            "CLOSED · readiness requires attention · empirical settlement "
            + str(bnb.get("empirical_status") or "UNKNOWN")
        )
    lines += [
        "",
        f"{bnb_icon} BNB: {bnb_state}",
        f"TON: {'✅ OPEN' if ton.get('ok') else ('🟡 SAFE CLOSED' if ton.get('ready') and not ton.get('public_open') else '⛔️ NEEDS REVIEW')} · "
        f"gate={'OPEN' if ton.get('public_open') else 'CLOSED'} · "
        f"readiness={'PASS' if ton.get('ready') else 'BLOCKED'} · "
        f"rate={ton.get('rate', 'unknown')} Credits/TON · "
        f"replay={ton.get('replay_evidence', 'unknown')}",
        "",
        "🔒 No orders, broadcasts, transfers, claims or gate changes were made.",
        (
            "✅ BNB public gate OPEN; live empirical settlement evidence is currently revalidated."
            if bnb.get("public_open") and bnb.get("launch_ready")
            else "🟡 BNB remains safely CLOSED pending explicit operator review; live empirical settlement evidence is PASS and revalidated."
            if bnb.get("launch_ready")
            else "⛔️ BNB stays closed until live empirical settlement evidence is revalidated and all blockers are cleared."
        ),
        "ℹ️ Participation / public investment stays DESIGN ONLY unless separate approvals pass.",
    ]

    if bnb.get("next_action"):
        lines.append("BNB evidence next step: " + str(bnb["next_action"])[:180])
    for blocker in (bnb.get("blockers") or [])[:3]:
        lines.append("BNB blocker: " + str(blocker)[:160])

    return "\n".join(lines)[:3900]



def register(bot, context=None):
    @bot.message_handler(commands=["go_live_report", "release_report"])
    def go_live_report_cmd(message):
        if not _allowed(message):
            _send_denied(bot, message)
            return
        try:
            bot.reply_to(
                message,
                _go_live_report_output(str(message.from_user.id)),
                parse_mode=None,
            )
        except Exception as exc:
            bot.reply_to(
                message,
                f"❌ Go-Live report failed safely: {type(exc).__name__}",
                parse_mode=None,
            )

    @bot.message_handler(commands=["check", "checks"])
    def check_cmd(message):
        if not _allowed(message):
            _send_denied(bot, message)
            return
        try:
            bot.reply_to(message, _check_output(str(message.from_user.id)), parse_mode=None)
        except Exception as exc:
            bot.reply_to(message, f"❌ System check failed safely: {type(exc).__name__}")

    @bot.message_handler(commands=["check_ux", "uxcheck"])
    def check_ux_cmd(message):
        if not _allowed(message):
            _send_denied(bot, message)
            return
        try:
            result = check_ux()
            lines = [
                "🎨 SLH UX CHECK — READ ONLY",
                "",
                f"{_icon(result['ok'])} {result['detail']}",
            ]
            for item in result.get("checks", []):
                lines.append(f"{_icon(item['ok'])} {item['name']}")
            lines += [
                "",
                "Source: deployed repository files",
                "🔒 No mutation.",
            ]
            bot.reply_to(message, "\n".join(lines)[:3900], parse_mode=None)
        except Exception as exc:
            bot.reply_to(message, f"❌ UX check failed safely: {type(exc).__name__}")

    @bot.message_handler(commands=["check_money", "moneycheck"])
    def check_money_cmd(message):
        if not _allowed(message):
            _send_denied(bot, message)
            return
        try:
            result = check_money(str(message.from_user.id))
            lines = [
                "💰 SLH MONEY CHECK — READ ONLY",
                "",
                f"{_icon(result['ok'])} {result['detail']}",
            ]
            for item in result.get("checks", []):
                lines.append(
                    f"{_icon(item['ok'])} {item['name']}: {item.get('detail', '')}"
                )
            lines += ["", "🔒 No balance mutation."]
            bot.reply_to(message, "\n".join(lines)[:3900], parse_mode=None)
        except Exception as exc:
            bot.reply_to(message, f"❌ Money check failed safely: {type(exc).__name__}")

    @bot.message_handler(commands=["check_exchange", "exchange_check"])
    def check_exchange_cmd(message):
        if not _allowed(message):
            _send_denied(bot, message)
            return
        try:
            result = check_exchange()
            lines = [
                "📈 SLH EXCHANGE CHECK — READ ONLY",
                "",
                f"Open orders: {result['open_orders']}",
                f"Open test/seed orders: {result['test_seed_open']}",
                f"Recent trades: {result['recent_trades']}",
                f"Test/seed trades: {result['test_seed_trades']}",
                f"Order book integrity: {'PASS' if result['order_book_integrity'] else 'FAIL'}",
                f"Trade integrity: {'PASS' if result['trade_integrity'] else 'FAIL'}",
                f"Money invariants: {'PASS' if result['money_invariants'] else 'FAIL'}",
                f"Reserve reconciliation: {result.get('reserve_reconciliation_status', 'UNKNOWN')}",
                f"Reserve findings needing review: {result.get('reserve_blocking_count', 0)}",
                f"Reserve blocker codes: {', '.join(result.get('reserve_blocking_codes', [])[:4]) or 'NONE'}",
                f"Public trading gate: {result['public_gate']}",
                f"Public trading readiness: {'PASS' if result['public_ready'] else 'FAIL'}",
                f"Verdict: {result['verdict']}",
                f"Detail: {result['detail']}",
                "",
                "🔒 Read-only: no orders, trades, balances, wallets or gates are changed.",
            ]
            bot.reply_to(message, "\n".join(lines)[:3900], parse_mode=None)
        except Exception as exc:
            bot.reply_to(message, f"❌ Exchange check failed safely: {type(exc).__name__}")

    @bot.message_handler(commands=["check_exchange_reserves"])
    def check_exchange_reserves_cmd(message):
        if not _allowed(message):
            _send_denied(bot, message)
            return
        try:
            from core.slh_exchange_reconciliation import run_once

            report = run_once()
            bot.reply_to(
                message,
                _exchange_reserves_output(report),
                parse_mode=None,
            )
        except Exception as exc:
            bot.reply_to(
                message,
                "⛔ Exchange reserve audit BLOCKED — "
                f"read-only snapshot failed ({type(exc).__name__}). "
                "No accounting or gate changes were made.",
                parse_mode=None,
            )

    @bot.message_handler(commands=["check_bnb", "bnb_check"])
    def check_bnb_cmd(message):
        if not _allowed(message):
            _send_denied(bot, message)
            return
        try:
            result = check_bnb()
            lines = [
                "🔶 SLH BNB CHECK — READ ONLY",
                "",
                f"{_icon(result['ok'])} {result['detail']}",
                f"Public gate: {'OPEN' if result['public_open'] else 'CLOSED'}",
                f"Readiness: {'PASS' if result['ready'] else 'BLOCKED'}",
                f"Empirical smoke: {result['empirical_status']}",
                f"Evidence status: {result.get('evidence_status', 'UNKNOWN')}",
                f"Live RPC: {result.get('live_rpc_status', 'UNKNOWN')}",
                f"Confirmations required: {result['confirmations_required']}",
            ]
            for reason in result.get("gate_reasons", [])[:5]:
                lines.append(f"Gate reason: {reason}")
            for reason in result.get("blockers", [])[:5]:
                lines.append(f"Blocker: {reason}")
            for warning in result.get("warnings", [])[:3]:
                lines.append(f"Warning: {warning}")
            if result.get("next_action"):
                lines.append(f"Next action: {result['next_action']}")
            lines += [
                "",
                "⛔️ אין שליחה, broadcast, claim או gate change.",
            ]
            bot.reply_to(message, "\n".join(lines)[:3900], parse_mode=None)
        except Exception as exc:
            bot.reply_to(message, f"❌ BNB check failed safely: {type(exc).__name__}")

    @bot.message_handler(commands=["bnb_reconcile_existing"])
    def bnb_reconcile_existing_cmd(message):
        uid = str(message.from_user.id)
        if not is_owner(uid):
            bot.reply_to(
                message,
                "⛔ OWNER ONLY — הקפד שרק בעל המערכת יוכל לאמת מחדש settlement קיים.",
                parse_mode=None,
            )
            return

        parts = (getattr(message, "text", "") or "").strip().split()
        if len(parts) != 2:
            bot.reply_to(
                message,
                "שימוש: /bnb_reconcile_existing <TX_HASH קיים>\n"
                "הפקודה בודקת העברה שכבר זוכתה; היא לא שולחת BNB ולא פותחת את השער.",
                parse_mode=None,
            )
            return

        tx_hash = parts[1].strip()
        try:
            from core.bnb_empirical_smoke import reconcile_existing_settlement

            result = reconcile_existing_settlement(uid, tx_hash)
            status = str(result.get("status") or "UNKNOWN").upper()
            if status == "PASS" and result.get("gate_remained_closed") is True:
                lines = [
                    "✅ BNB EXISTING SETTLEMENT PROOF: PASS",
                    f"TX: {tx_hash}",
                    "Live settlement replay: DUPLICATE",
                    f"Original Credits entry: {result.get('credits', 'UNKNOWN')}",
                    "Current balance unchanged by replay.",
                    "Public BNB gate: CLOSED (left closed)",
                    "לא נשלחה עסקת BNB חדשה ולא נוצר זיכוי נוסף.",
                ]
            elif status == "ALREADY_PASS" and result.get("gate_remained_closed") is True:
                lines = [
                    "✅ BNB EXISTING SETTLEMENT PROOF: ALREADY_PASS",
                    f"TX: {result.get('tx_hash') or tx_hash}",
                    "Evidence was revalidated against live chain and ledger.",
                    "Public BNB gate: CLOSED (left closed)",
                    "לא נשלחה עסקת BNB חדשה ולא נוצר זיכוי נוסף.",
                ]
            elif status == "GATE_OPEN":
                lines = [
                    "⛔ BNB RECONCILIATION STOPPED: GATE_ALREADY_OPEN",
                    "הפקודה לא שינתה את השער. נדרשת בדיקה מיידית לפני שימוש ציבורי.",
                    "לא נשלחה עסקת BNB חדשה.",
                ]
            else:
                lines = [
                    f"🟡 BNB existing settlement proof: {status}",
                    str(result.get("detail") or "No proof was accepted; review the reported status."),
                    "No gate change was requested by this command.",
                    "No new BNB transaction was broadcast by this command.",
                ]
            bot.reply_to(message, "\n".join(lines)[:3900], parse_mode=None)
        except Exception as exc:
            bot.reply_to(
                message,
                f"❌ BNB existing settlement reconciliation failed safely: {type(exc).__name__}",
                parse_mode=None,
            )

    @bot.message_handler(commands=["check_ton", "ton_check_status"])
    def check_ton_cmd(message):
        if not _allowed(message):
            _send_denied(bot, message)
            return
        try:
            result = check_ton(str(message.from_user.id))
            lines = [
                "💎 SLH TON CHECK — READ ONLY",
                "",
                f"{_icon(result['ok'])} {result['detail']}",
                f"Public gate: {'OPEN' if result['public_open'] else 'CLOSED'}",
                f"Readiness: {'PASS' if result['ready'] else 'BLOCKED'}",
                f"Rate: {result['rate']} Credits / TON",
                f"Replay evidence: {result['replay_evidence']}",
                "",
                "🔒 No transaction lookup that can credit funds; no mutation.",
            ]
            bot.reply_to(message, "\n".join(lines)[:3900], parse_mode=None)
        except Exception as exc:
            bot.reply_to(message, f"❌ TON check failed safely: {type(exc).__name__}")

    print("✅ system_checks loaded")
