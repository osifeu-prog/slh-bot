"""Owner-only read-only release and recovery report for SLH OS."""

from core.authority import is_owner
from core.release_readiness import build_release_report
from core.recovery_center import build_recovery_center_report
from core.system_checks import check_exchange


def _short_ref(value, limit=44):
    text = str(value or "").strip()
    if not text:
        return None
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _display_number(value, *, signed=False):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    import math
    if not math.isfinite(number):
        return None
    return f"{number:+.8g}" if signed else f"{number:.8g}"


def _ledger_gap_evidence_lines(item):
    """Render existing audit evidence compactly; never infer that a gap is resolved."""
    evidence = item.get("evidence")
    evidence = evidence if isinstance(evidence, dict) else {}
    previous = evidence.get("previous")
    previous = previous if isinstance(previous, dict) else {}
    next_row = evidence.get("next")
    next_row = next_row if isinstance(next_row, dict) else {}
    source = evidence.get("source_evidence")
    source = source if isinstance(source, dict) else {}

    lines = []
    delta = _display_number(evidence.get("delta_to_explain"), signed=True)
    previous_after = _display_number(previous.get("after"))
    next_before = _display_number(next_row.get("before"))
    if delta is not None:
        lines.append(
            f"  Delta to explain: {delta} Credits · "
            f"previous after={previous_after or 'UNKNOWN'} · next before={next_before or 'UNKNOWN'}"
        )

    def refs(row, fields):
        values = []
        for label, key in fields:
            value = _short_ref(row.get(key))
            if value:
                values.append(f"{label}={value}")
        return ", ".join(values)

    previous_refs = refs(previous, (
        ("event", "event_id"), ("order", "order_id"),
        ("transfer", "transfer_id"), ("item", "item_id"),
    ))
    next_refs = refs(next_row, (
        ("event", "event_id"), ("order", "order_id"),
        ("purchase", "purchase_id"), ("idem", "idempotency_key"),
        ("item", "item_id"),
    ))
    if previous_refs:
        lines.append(f"  Previous refs: {previous_refs}")
    if next_refs:
        lines.append(f"  Next refs: {next_refs}")

    if source:
        match_status = _short_ref(source.get("source_match_status"), 64) or "UNKNOWN"
        resolves = source.get("resolves_gap") is True
        lines.append(
            f"  Source match: {match_status} · resolves_gap={resolves}"
        )

    transfer = source.get("transfer")
    if isinstance(transfer, dict):
        transfer_id = _short_ref(transfer.get("transfer_id")) or "UNKNOWN"
        detail = f"  Linked transfer: id={transfer_id} · record_found={transfer.get('record_found') is True}"
        transfer_rows = transfer.get("ledger_rows")
        if isinstance(transfer_rows, list) and transfer_rows:
            rendered = []
            for row in transfer_rows[:2]:
                if not isinstance(row, dict):
                    continue
                idx = row.get("index", "?")
                reason = _short_ref(row.get("reason"), 36) or "UNKNOWN"
                before = _display_number(row.get("before"))
                after = _display_number(row.get("after"))
                amount = _display_number(row.get("amount"), signed=True)
                rendered.append(f"#{idx} {reason} {before or '?'}→{after or '?'} (Δ{amount or '?'})")
            if rendered:
                detail += " · " + "; ".join(rendered)
        lines.append(detail[:260])

    purchase = source.get("purchase")
    if isinstance(purchase, dict):
        detail = (
            "  Linked purchase: "
            f"id={_short_ref(purchase.get('purchase_id')) or 'UNKNOWN'} · "
            f"record_found={purchase.get('record_found') is True}"
        )
        if purchase.get("record_found") is True:
            status = _short_ref(purchase.get("status"), 24) or "UNKNOWN"
            price = _display_number(purchase.get("price"))
            payout = _display_number(purchase.get("seller_payout"))
            commission = _display_number(purchase.get("commission"))
            method = _short_ref(purchase.get("fulfillment_method"), 24)
            detail += f" · status={status}"
            if price is not None:
                detail += f" · price={price}"
            if payout is not None:
                detail += f" · seller_payout={payout}"
            if commission is not None:
                detail += f" · commission={commission}"
            if method:
                detail += f" · fulfillment={method}"
        lines.append(detail[:260])

    alpha = source.get("alpha_consolidations")
    if isinstance(alpha, list):
        for event in alpha[:1]:
            if isinstance(event, dict):
                lines.append(
                    "  Alpha consolidation context: "
                    f"row={event.get('index', '?')} · resolves_gap={event.get('resolves_gap') is True} · "
                    f"basis={_short_ref(event.get('resolution_basis'), 56) or 'UNKNOWN'}"
                )

    return lines[:7]
def _exchange_snapshot_lines():
    """Summarize canonical exchange/reserve evidence without changing state."""
    try:
        result = check_exchange()
    except Exception as exc:
        return [
            "Exchange snapshot: BLOCKED — check unavailable "
            f"({type(exc).__name__})",
            "Reserve reconciliation: BLOCKED — RESERVE_AUDIT_UNAVAILABLE",
            "Public trading gate: UNKNOWN",
        ]

    if not isinstance(result, dict):
        return [
            "Exchange snapshot: BLOCKED — malformed result",
            "Reserve reconciliation: BLOCKED — RESERVE_AUDIT_RESULT_INVALID",
            "Public trading gate: UNKNOWN",
        ]

    status = str(result.get("reserve_reconciliation_status") or "UNKNOWN").upper()
    raw_count = result.get("reserve_blocking_count")
    codes = result.get("reserve_blocking_codes")
    count_valid = isinstance(raw_count, int) and not isinstance(raw_count, bool) and raw_count >= 0
    codes_valid = isinstance(codes, list) and all(isinstance(code, str) for code in codes)
    report_valid = (
        status in {"PASS", "BLOCKED"}
        and count_valid
        and codes_valid
        and ((status == "PASS" and raw_count == 0 and not codes)
             or (status == "BLOCKED" and raw_count > 0 and bool(codes)))
    )
    if not report_valid:
        status = "BLOCKED"
        count = raw_count if count_valid else "UNKNOWN"
        code_text = "RESERVE_AUDIT_RESULT_INVALID"
    else:
        count = raw_count
        code_text = ", ".join(codes[:6]) or "NONE"

    gate = str(result.get("public_gate") or "UNKNOWN").upper()
    if gate not in {"CLOSED", "OPEN", "UNKNOWN"}:
        gate = "UNKNOWN"
    readiness = "PASS" if result.get("public_ready") is True else "FAIL"
    verdict = str(result.get("verdict") or "UNKNOWN").upper()[:40]

    return [
        f"Exchange snapshot: verdict={verdict} · readiness={readiness}",
        f"Reserve reconciliation: {status} · findings={count} · codes={code_text}",
        f"Public trading gate: {gate}",
    ]



def register(bot, context=None):
    @bot.message_handler(commands=["releasecheck", "release_supervisor", "release"])
    def releasecheck_cmd(msg):
        if not is_owner(msg.from_user.id):
            bot.reply_to(msg, "⛔️ Owner only", parse_mode=None)
            return

        report = build_release_report()
        invoked = str(getattr(msg, "text", "") or "").strip().split()
        command = invoked[0].split("@", 1)[0].lstrip("/").lower() if invoked else "releasecheck"
        title = "SLH Release Supervisor" if command in {"release", "release_supervisor"} else "SLH Release Check"
        overall = str(report.get("overall_status") or "UNKNOWN").upper()
        lines = [f"🚦 {title} — {overall} · READ ONLY", ""]
        for name, check in report["checks"].items():
            icon = "✅" if check["status"] == "GREEN" else "⚠️" if check["status"] == "DEGRADED" else "⛔️"
            lines.append(f"{icon} {name}: {check['status']} — {check['detail']}")

        lines.append("")
        lines.extend(_exchange_snapshot_lines())

        blockers = report.get("blockers") or []
        lines.append("")
        if blockers:
            lines.append("🛑 Release blockers:")
            lines.extend(f"• {item}" for item in blockers)
        else:
            lines.append("✅ אין blockers ב־release gate.")

        lines.append("")
        lines.append("🛡 RECOVERY CENTER — ACTIONABLE / READ ONLY")
        try:
            recovery = build_recovery_center_report(release_report=report)
            lines.append(f"Recovery status: {recovery['overall_status']}")
            account = recovery["account_ledger"]
            lines.append(
                "Account ledger: "
                f"{account.get('status', 'UNKNOWN')} · "
                f"unresolved gaps={account.get('unresolved_continuity_break_count', 'UNKNOWN')} · "
                f"balance matches tail={account.get('current_balance_matches_tail', 'UNKNOWN')}"
            )
            reserves = recovery.get("exchange_reserves", {})
            reserve_status = reserves.get("status", "UNKNOWN")
            reserve_readiness = reserves.get("release_readiness_status", "UNKNOWN")
            reserve_count = reserves.get("release_blocking_finding_count")
            lines.append(
                "Exchange reserves: "
                f"{reserve_status} · release readiness={reserve_readiness} · "
                f"blocking findings={reserve_count if reserve_count is not None else 'UNKNOWN'}"
            )
            recovery_blockers = recovery.get("blockers", [])
            reserve_blockers = [
                item for item in recovery_blockers
                if str(item.get("id", "")).startswith("RESERVE-")
                or str(item.get("kind", "")).startswith("EXCHANGE_RESERVE")
                or str(item.get("kind", "")).startswith("CANCELLED_SELL_ORDER")
                or str(item.get("kind", "")).startswith("RESERVE_")
            ]
            ledger_blockers = [item for item in recovery_blockers if item not in reserve_blockers]
            if ledger_blockers:
                lines.append("Ledger recovery actions:")
                for item in ledger_blockers[:4]:
                    lines.append(f"• [{item['id']}] {item['summary']}")
                    lines.append(f"  Next: {item['next_action']}")
                    lines.extend(_ledger_gap_evidence_lines(item))
            if reserve_blockers:
                lines.append("Exchange reserve blockers:")
                for item in reserve_blockers[:4]:
                    lines.append(f"• [{item['id']}] {item['summary']}")
                    lines.append(f"  Next: {item['next_action']}")
            if not recovery_blockers:
                lines.append("No detailed ledger-gap or reserve blocker was returned by the audits.")
            for item in recovery.get("review_items", [])[:2]:
                lines.append(f"👀 [{item['id']}] {item['summary']}")
                lines.append(f"  Next: {item['next_action']}")
            lines.append("Finding IDs are stable; history is not yet persisted by this read-only version.")
        except Exception as exc:
            lines.append(f"Recovery center: UNAVAILABLE ({type(exc).__name__}); release checks remain unchanged.")

        lines.append("")
        lines.append("🔐 Read-only: no balances, ledger rows, orders, or BNB/TON/Exchange gates are changed.")
        bot.reply_to(msg, "\n".join(lines), parse_mode=None)

    print("✅ releasecheck loaded")
