"""Owner/admin/developer read-only system checks for SLH OS."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

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
_PENDING_BNB_REVERSALS: dict[str, dict] = {}
_BNB_REVERSAL_CONFIRM_TTL = timedelta(minutes=5)


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
    @bot.message_handler(commands=["go_live_report", "release_report", "zero_hour"])
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

    @bot.message_handler(commands=["check_exchange", "exchange_check", "exchange_status"])
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

    @bot.message_handler(commands=["check_owner_ledger"])
    def check_owner_ledger_cmd(message):
        uid = str(message.from_user.id)
        if not is_owner(uid):
            bot.reply_to(message, "⛔ OWNER ONLY — owner ledger diagnostics.", parse_mode=None)
            return
        chat = getattr(message, "chat", None)
        if chat is None or getattr(chat, "type", None) != "private":
            bot.reply_to(message, "⛔ להריץ את בדיקת ספר החשבונות רק בשיחה פרטית עם הבוט.", parse_mode=None)
            return
        try:
            import state_manager
            from core.account_ledger_audit import audit_account_ledger

            db = state_manager.load_db()
            result = audit_account_ledger(db, uid)
            users = db.get("users") if isinstance(db, dict) else {}
            owner_user = users.get(uid) if isinstance(users, dict) else {}
            wallet = owner_user.get("wallet") if isinstance(owner_user, dict) else {}
            wallet = wallet if isinstance(wallet, dict) else {}

            # Include the existing legacy-staking guard's read-only evidence in
            # the same owner report. This never invokes unstake_locked or writes.
            staking_review = []
            staking_guard_available = False
            locked_positions_checked = 0
            try:
                from core.staking_service import _find_legacy_unstake_ambiguity

                staking_guard_available = callable(_find_legacy_unstake_ambiguity)
                positions = db.get("stake_positions") if isinstance(db, dict) else {}
                positions = positions if isinstance(positions, dict) else {}
                for position_id, position in positions.items():
                    if not isinstance(position, dict) or str(position.get("uid")) != uid:
                        continue
                    if position.get("status") != "locked":
                        continue
                    locked_positions_checked += 1
                    evidence = _find_legacy_unstake_ambiguity(db, uid, position)
                    if isinstance(evidence, dict):
                        staking_review.append({
                            "position_id": str(position_id),
                            "amount": position.get("amount"),
                            "evidence": evidence,
                        })
            except Exception as guard_exc:
                staking_review_error = type(guard_exc).__name__
            else:
                staking_review_error = None

            lines = [
                "🧾 OWNER ACCOUNT LEDGER — READ ONLY",
                "🔍 FORENSIC BUNDLE: ledger + staking guard + exchange",
                "",
                f"Ledger status: {result.get('status', 'BLOCKED')}",
                f"Owner ledger rows scanned: {result.get('rows_checked', 0)}",
                f"Credits sequence rows checked: {result.get('credits_sequence_rows_checked', result.get('rows_checked', 0))}",
                f"Non-Credits rows skipped: {result.get('non_credits_rows_skipped', 0)}",
                f"Observed discontinuities: {result.get('observed_discontinuity_count', 0)}",
                f"Resolved with source evidence: {result.get('resolved_gap_count', 0)}",
                f"Credits continuity breaks: {result.get('continuity_break_count', 0)}",
                f"Unresolved Credits gaps: {result.get('unresolved_continuity_break_count', result.get('continuity_break_count', 0))}",
                f"Row arithmetic errors: {result.get('arithmetic_error_count', 0)}",
                f"Malformed global rows: {result.get('malformed_global_rows', 0)}",
                f"Wallet Credits: {result.get('current_wallet_credits', wallet.get('credits', 'UNKNOWN'))}",
                f"Wallet Staked: {wallet.get('staked', 'UNKNOWN')}",
                f"Last Credits candidate after: {result.get('ledger_tail_after', 'UNKNOWN')}",
                f"Wallet matches Credits sequence tail: {result.get('current_balance_matches_tail', False)}",
                "",
                f"Legacy staking guard: {'AVAILABLE' if staking_guard_available else 'UNAVAILABLE'}",
                f"Locked positions checked: {locked_positions_checked}",
                f"Positions blocked for legacy review: {len(staking_review)}",
            ]
            if staking_review_error:
                lines.append(f"Staking guard diagnostic error: {staking_review_error}")
            for record in staking_review[:8]:
                evidence = record.get("evidence") or {}
                lines.append(
                    f"  LEGACY_UNSTAKE_AMBIGUITY: {record.get('position_id')} "
                    f"amount={record.get('amount')} ledger_row={evidence.get('ledger_index')} "
                    f"age_seconds={evidence.get('seconds_from_creation')}"
                )
            if len(staking_review) > 8:
                lines.append(f"  +{len(staking_review) - 8} additional positions omitted")
            lines.append("")
            for item in result.get("findings", [])[:12]:
                if not isinstance(item, dict):
                    continue
                kind = str(item.get("type") or "UNKNOWN")
                if isinstance(item.get("previous"), dict) and isinstance(item.get("next"), dict):
                    previous, next_row = item["previous"], item["next"]
                    evidence = item.get("source_evidence")
                    evidence = evidence if isinstance(evidence, dict) else {}
                    reconciled = item.get("reconciled") is True or evidence.get("resolves_gap") is True
                    if reconciled:
                        evidence_status = "source evidence verified"
                    elif item.get("source_evidence_required") is True:
                        evidence_status = "source evidence required"
                    else:
                        evidence_status = "source evidence status unknown"
                    lines.append(
                        f"{kind}: #{previous.get('index')} {previous.get('reason')}[{previous.get('domain_hint')}] "
                        f"after={previous.get('after')} → #{next_row.get('index')} "
                        f"{next_row.get('reason')}[{next_row.get('domain_hint')}] "
                        f"before={next_row.get('before')} delta={item.get('delta_to_explain')}; {evidence_status}"
                    )
                    match_status = str(evidence.get("source_match_status") or "").strip()
                    if match_status:
                        lines.append(
                            f"  Source match: {match_status} · resolves_gap={evidence.get('resolves_gap') is True}"
                        )
                    alpha = evidence.get("alpha_consolidations")
                    if isinstance(alpha, list):
                        for event in alpha[:1]:
                            if not isinstance(event, dict):
                                continue
                            basis = str(event.get("resolution_basis") or "UNKNOWN")[:64]
                            source_commit = str(event.get("source_commit") or "").strip()
                            lines.append(
                                "  Alpha consolidation: "
                                f"row={event.get('index', '?')} · basis={basis}"
                                + (f" · commit={source_commit[:12]}" if source_commit else "")
                            )
                            verification_failures = event.get("verification_failures")
                            if isinstance(verification_failures, list) and verification_failures:
                                safe_failures = [str(name)[:48] for name in verification_failures[:8]]
                                lines.append("  Alpha verification failed: " + ", ".join(safe_failures))
                    intervening = evidence.get("intervening_rows")
                    if isinstance(intervening, list):
                        for middle in intervening[:3]:
                            if not isinstance(middle, dict) or middle.get("type") == "alpha_consolidate":
                                continue
                            row_id = middle.get("index", "?")
                            reason = str(middle.get("reason") or middle.get("type") or "UNKNOWN")[:48]
                            domain = str(middle.get("domain_hint") or "UNKNOWN")[:24]
                            if middle.get("uid_matches_owner") is True:
                                lines.append(
                                    f"  BETWEEN ROWS: #{row_id} owner=true {reason}[{domain}] "
                                    f"before={middle.get('before')} amount={middle.get('amount')} "
                                    f"after={middle.get('after')} purchase={str(middle.get('purchase_id') or '-')[:40]} "
                                    f"transfer={str(middle.get('transfer_id') or '-')[:32]}"
                                )
                            else:
                                lines.append(
                                    f"  BETWEEN ROWS: #{row_id} owner=false; "
                                    "other-account details withheld"
                                )
                    if isinstance(evidence, dict):
                        source_parts = []
                        transfer = evidence.get("transfer")
                        if isinstance(transfer, dict):
                            source_parts.append(
                                f"transfer rows={len(transfer.get('ledger_rows') or [])}/"
                                f"processed_keys={len(transfer.get('processed_keys') or [])}"
                            )
                        purchase = evidence.get("purchase")
                        if isinstance(purchase, dict):
                            if purchase.get("record_found") is True:
                                source_parts.append(
                                    f"purchase={purchase.get('status')} item={purchase.get('item_id')} "
                                    f"payout={purchase.get('seller_payout')}"
                                )
                            else:
                                source_parts.append("purchase record not found")
                        if source_parts:
                            lines.append(
                                "  SOURCE CONTEXT ONLY: " + "; ".join(source_parts)
                                + "; gap remains unresolved"
                            )
                elif isinstance(item.get("row"), dict):
                    row = item["row"]
                    lines.append(
                        f"{kind}: #{row.get('index')} {row.get('reason')} "
                        f"before={row.get('before')} amount={row.get('amount')} after={row.get('after')}"
                    )
                else:
                    lines.append(f"{kind}: row #{item.get('index', 'UNKNOWN')}")
            for blocker in result.get("blockers", [])[:8]:
                lines.append(f"Blocker: {blocker}")
            if result.get("findings_truncated"):
                lines.append("Additional findings omitted; Telegram output is capped at 12 findings.")
            try:
                exchange_snapshot = check_exchange()
                lines += [
                    "",
                    "EXCHANGE SNAPSHOT — READ ONLY",
                    f"Public trading gate: {exchange_snapshot.get('public_gate', 'UNKNOWN')}",
                    f"Public trading readiness: {'PASS' if exchange_snapshot.get('public_ready') else 'FAIL'}",
                    f"Exchange verdict: {exchange_snapshot.get('verdict', 'UNKNOWN')}",
                    f"Exchange detail: {exchange_snapshot.get('detail', 'UNKNOWN')}",
                ]
            except Exception as exchange_exc:
                lines += ["", f"Exchange snapshot: UNKNOWN ({type(exchange_exc).__name__})"]

            lines += [
                "",
                "⚠️ Reason/domain hints are heuristic, not accounting proof.",
                "🔒 No DB, ledger, Credits, wallets, or gates changed.",
                "Do not execute an accounting correction until every discontinuity has source-backed reconciliation.",
            ]
            bot.reply_to(message, "\n".join(lines)[:3900], parse_mode=None)
        except Exception as exc:
            bot.reply_to(
                message,
                f"⛔ Owner ledger audit failed safely: {type(exc).__name__}",
                parse_mode=None,
            )

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
                f"Historical BNB deposits: {result.get('historical_deposits_status', 'UNKNOWN')} · "
                f"checked={result.get('historical_deposits_found', 0)} · "
                f"needs review={result.get('historical_deposits_failed', 0)}",
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

    @bot.message_handler(commands=["check_bnb_deposits"])
    def check_bnb_deposits_cmd(message):
        if not _allowed(message):
            _send_denied(bot, message)
            return
        try:
            import state_manager
            from core.bnb_history_audit import audit_bnb_deposit_history

            result = audit_bnb_deposit_history(state_manager.load_db())
            status = str(result.get("status") or "BLOCKED").upper()
            lines = [
                "🧾 BNB DEPOSIT HISTORY — READ ONLY",
                "",
                f"Status: {status}",
                f"Rows found: {result.get('rows_found', 0)}",
                f"Rows checked: {result.get('rows_checked', 0)}",
                f"Rows needing review: {result.get('failed_rows', 0)}",
            ]
            for reason in result.get("blockers", [])[:8]:
                lines.append(f"Blocker: {reason}")
            for item in result.get("findings", [])[:12]:
                if not isinstance(item, dict):
                    continue
                issues = ", ".join(str(x) for x in (item.get("issues") or [])[:5])
                lines.append(
                    f"{str(item.get('time') or 'time unknown')[:25]} · "
                    f"TX …{item.get('tx_suffix', 'MISSING')} · "
                    f"{item.get('status', 'UNKNOWN')} · {issues or 'PASS'}"
                )
            lines += [
                "",
                "🔒 No DB, ledger, balance, config or gate changes.",
                "If any row is blocked, keep BNB CLOSED pending reviewed reconciliation.",
            ]
            bot.reply_to(message, "\n".join(lines)[:3900], parse_mode=None)
        except Exception as exc:
            bot.reply_to(
                message,
                f"❌ BNB history audit failed safely: {type(exc).__name__}",
                parse_mode=None,
            )

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

    @bot.message_handler(commands=["bnb_reverse_prepare"])
    def bnb_reverse_prepare_cmd(message):
        uid = str(message.from_user.id)
        if not is_owner(uid):
            bot.reply_to(message, "⛔ OWNER ONLY — BNB accounting correction.", parse_mode=None)
            return
        chat = getattr(message, "chat", None)
        if chat is None or getattr(chat, "type", None) != "private":
            bot.reply_to(message, "⛔ יש להריץ את הפקודה בשיחה פרטית עם הבוט.", parse_mode=None)
            return
        parts = (getattr(message, "text", "") or "").strip().split()
        auto_discovered = False
        if len(parts) == 1:
            # Owner convenience path: discover a unique self-transfer row from
            # the canonical ledger. The subsequent source/chain/audit preview is
            # still performed by the same strict correction service.
            try:
                import state_manager

                db = state_manager.load_db()
                ledger = db.get("ledger", []) if isinstance(db, dict) else None
                if not isinstance(ledger, list):
                    raise ValueError("LEDGER_UNREADABLE")
                candidates = []
                for index, row in enumerate(ledger):
                    if not isinstance(row, dict) or str(row.get("uid") or "") != uid:
                        continue
                    if str(row.get("reason") or "") != "bnb:deposit":
                        continue
                    meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
                    tx_hash_candidate = str(meta.get("tx_hash") or "").strip()
                    sender = str(meta.get("from") or "").strip()
                    recipient = str(meta.get("to") or "").strip()
                    if (
                        len(tx_hash_candidate) == 66
                        and tx_hash_candidate.lower().startswith("0x")
                        and all(ch in "0123456789abcdefABCDEF" for ch in tx_hash_candidate[2:])
                        and sender and recipient and sender.lower() == recipient.lower()
                    ):
                        candidates.append({
                            "index": index,
                            "tx_hash": tx_hash_candidate.lower(),
                            "amount": row.get("amount"),
                        })
            except Exception as exc:
                bot.reply_to(
                    message,
                    f"⛔ גילוי מקור BNB נכשל בבטחה ({type(exc).__name__}); לא בוצע שינוי.",
                    parse_mode=None,
                )
                return
            if len(candidates) != 1:
                if not candidates:
                    detail = (
                        "לא נמצאה רשומת bnb:deposit של החשבון העצמי שבה from=to. "
                        "לא בוצע שינוי. אם יש TX מסוים לבדיקה, אפשר להעבירו כארגומנט."
                    )
                else:
                    summaries = ", ".join(
                        f"row {item['index']} · …{item['tx_hash'][-8:]}"
                        for item in candidates[:5]
                    )
                    detail = (
                        f"נמצאו {len(candidates)} מועמדים; אין בחירה אוטומטית. "
                        f"מועמדים: {summaries}. יש לציין TX מדויק."
                    )
                bot.reply_to(
                    message,
                    "🔎 BNB AUTO-DISCOVERY — READ ONLY\n"
                    + detail
                    + "\nפורמט ידני: /bnb_reverse_prepare <TX_HASH>",
                    parse_mode=None,
                )
                return
            tx_hash = candidates[0]["tx_hash"]
            auto_discovered = True
        elif len(parts) == 2:
            tx_hash = parts[1].strip()
        else:
            bot.reply_to(
                message,
                "שימוש: /bnb_reverse_prepare [TX_HASH]\n"
                "ללא TX_HASH הבוט יאתר מועמד יחיד בלבד; הבדיקה לקריאה בלבד.",
                parse_mode=None,
            )
            return
        try:
            from core.credit_adjustment_service import preview_invalid_bnb_deposit_reversal

            preview = preview_invalid_bnb_deposit_reversal(
                actor_uid=uid, uid=uid, tx_hash=tx_hash
            )
            if preview.get("status") == "ALREADY_REVERSED":
                bot.reply_to(
                    message,
                    "ℹ️ התיקון כבר קיים ומאומת; לא נוצר זיכוי/חיוב נוסף.\n"
                    f"Balance after correction: {preview.get('balance_after', 'UNKNOWN')} Credits",
                    parse_mode=None,
                )
                return
            if preview.get("status") != "PREPARED" or preview.get("gate_remained_closed") is not True:
                bot.reply_to(message, "⛔ PREVIEW BLOCKED — no mutation performed.", parse_mode=None)
                return

            now = datetime.now(timezone.utc)
            for key, item in list(_PENDING_BNB_REVERSALS.items()):
                expires = item.get("expires_at")
                if not isinstance(expires, datetime) or expires <= now:
                    _PENDING_BNB_REVERSALS.pop(key, None)
            if len(_PENDING_BNB_REVERSALS) >= 20:
                bot.reply_to(message, "⛔ יש יותר מדי בקשות אישור פעילות; בטל/המתן עד לפקיעת בקשה קיימת.", parse_mode=None)
                return

            confirmation = secrets.token_urlsafe(9)
            while confirmation in _PENDING_BNB_REVERSALS:
                confirmation = secrets.token_urlsafe(9)
            _PENDING_BNB_REVERSALS[confirmation] = {
                "actor_uid": uid,
                "uid": uid,
                "tx_hash": tx_hash.lower(),
                "expected_current_balance": preview["expected_current_balance"],
                "expires_at": now + _BNB_REVERSAL_CONFIRM_TTL,
            }
            lines = [
                "🧾 BNB REVERSAL PREVIEW — LIVE READ ONLY",
                "Discovery: AUTO (unique source row)" if auto_discovered else "Discovery: explicit TX supplied",
                f"Source ledger row: {preview.get('source_ledger_index')}",
                f"TX suffix: …{preview.get('tx_suffix')}",
                f"Credits to reverse: {preview.get('amount_reversed')}",
                f"Current balance: {preview.get('balance_before')} Credits",
                f"Projected balance: {preview.get('balance_after')} Credits",
                "Historical BNB audit: all other rows passed; only this source self-transfer remains blocked.",
                "Public BNB gate: CLOSED",
                "DB changed: NO · Settlement executed: NO",
                "",
                f"To apply this one correction, within 5 minutes send: /bnb_reverse_confirm {confirmation}",
                "Confirmation revalidates live chain, full deposit history, current balance and ledger sequence.",
            ]
            bot.reply_to(message, "\n".join(lines)[:3900], parse_mode=None)
        except Exception as exc:
            bot.reply_to(
                message,
                f"⛔ BNB reversal preview blocked safely: {type(exc).__name__}",
                parse_mode=None,
            )

    @bot.message_handler(commands=["bnb_reverse_confirm"])
    def bnb_reverse_confirm_cmd(message):
        uid = str(message.from_user.id)
        if not is_owner(uid):
            bot.reply_to(message, "⛔ OWNER ONLY — BNB accounting correction.", parse_mode=None)
            return
        chat = getattr(message, "chat", None)
        if chat is None or getattr(chat, "type", None) != "private":
            bot.reply_to(message, "⛔ יש להריץ את הפקודה בשיחה פרטית עם הבוט.", parse_mode=None)
            return
        parts = (getattr(message, "text", "") or "").strip().split()
        if len(parts) != 2:
            bot.reply_to(
                message,
                "שימוש: /bnb_reverse_confirm <CONFIRMATION_CODE>",
                parse_mode=None,
            )
            return
        code = parts[1].strip()
        pending = _PENDING_BNB_REVERSALS.get(code)
        now = datetime.now(timezone.utc)
        if not isinstance(pending, dict) or pending.get("actor_uid") != uid:
            bot.reply_to(message, "⛔ Confirmation code invalid or not issued to this owner.", parse_mode=None)
            return
        expires = pending.get("expires_at")
        if not isinstance(expires, datetime) or expires <= now:
            _PENDING_BNB_REVERSALS.pop(code, None)
            bot.reply_to(message, "⌛ Confirmation expired; run /bnb_reverse_prepare again.", parse_mode=None)
            return

        # Consume before entering the atomic mutation, so a token can never be replayed.
        _PENDING_BNB_REVERSALS.pop(code, None)
        try:
            from core.credit_adjustment_service import reverse_invalid_bnb_deposit

            result = reverse_invalid_bnb_deposit(
                actor_uid=uid,
                uid=uid,
                tx_hash=str(pending.get("tx_hash") or ""),
                expected_current_balance=str(pending.get("expected_current_balance") or ""),
                now=now,
            )
            if result.get("status") == "APPLIED" and result.get("gate_remained_closed") is True:
                lines = [
                    "✅ BNB ACCOUNTING CORRECTION APPLIED",
                    f"TX suffix: …{str(result.get('tx_hash') or '')[-8:]}",
                    f"Credits reversed: {result.get('amount_reversed')}",
                    f"Balance before: {result.get('balance_before')}",
                    f"Balance after: {result.get('balance_after')}",
                    "Original ledger row preserved; one compensating debit and audit event appended.",
                    "Public BNB gate remained CLOSED.",
                ]
            elif result.get("status") == "ALREADY_REVERSED" and result.get("gate_remained_closed") is True:
                lines = [
                    "ℹ️ BNB correction already exists and reconciles; no duplicate debit was applied.",
                    f"Balance after: {result.get('balance_after')}",
                    "Public BNB gate remained CLOSED.",
                ]
            else:
                lines = [
                    "⛔ Correction did not return an accepted status.",
                    "Review live audit before retrying; a fresh preview is required.",
                ]
            bot.reply_to(message, "\n".join(lines)[:3900], parse_mode=None)
        except Exception as exc:
            bot.reply_to(
                message,
                f"⛔ BNB accounting correction refused safely: {type(exc).__name__}. "
                "No retry token remains; re-run a fresh preview after reviewing the blocker.",
                parse_mode=None,
            )

    @bot.message_handler(commands=["bnb_reverse_cancel"])
    def bnb_reverse_cancel_cmd(message):
        uid = str(message.from_user.id)
        if not is_owner(uid):
            bot.reply_to(message, "⛔ OWNER ONLY — BNB accounting correction.", parse_mode=None)
            return
        parts = (getattr(message, "text", "") or "").strip().split()
        if len(parts) != 2:
            bot.reply_to(message, "שימוש: /bnb_reverse_cancel <CONFIRMATION_CODE>", parse_mode=None)
            return
        code = parts[1].strip()
        pending = _PENDING_BNB_REVERSALS.get(code)
        if isinstance(pending, dict) and pending.get("actor_uid") == uid:
            _PENDING_BNB_REVERSALS.pop(code, None)
            bot.reply_to(message, "בקשת האישור בוטלה; לא בוצע שינוי בנתונים.", parse_mode=None)
        else:
            bot.reply_to(message, "Confirmation code invalid or not issued to this owner.", parse_mode=None)

    print("✅ system_checks loaded")
