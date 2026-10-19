"""Owner-only read-only release and recovery report for SLH OS."""

from core.authority import is_owner
from core.release_readiness import build_release_report
from core.recovery_center import build_recovery_center_report
from core.system_checks import check_exchange


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
            recovery_blockers = recovery.get("blockers", [])
            if recovery_blockers:
                lines.append("Next actions:")
                for item in recovery_blockers[:4]:
                    lines.append(f"• [{item['id']}] {item['summary']}")
                    lines.append(f"  Next: {item['next_action']}")
            else:
                lines.append("No detailed ledger-gap finding was returned by the account audit.")
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
