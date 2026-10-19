"""Owner-only read-only release and recovery report for SLH OS."""

from core.authority import is_owner
from core.release_readiness import build_release_report
from core.recovery_center import build_recovery_center_report


def register(bot, context=None):
    @bot.message_handler(commands=["releasecheck"])
    def releasecheck_cmd(msg):
        if not is_owner(msg.from_user.id):
            bot.reply_to(msg, "⛔️ Owner only", parse_mode=None)
            return

        report = build_release_report()
        lines = [f"🚦 SLH Release Check — {report['overall_status']}", ""]
        for name, check in report["checks"].items():
            icon = "✅" if check["status"] == "GREEN" else "⚠️" if check["status"] == "DEGRADED" else "⛔️"
            lines.append(f"{icon} {name}: {check['status']} — {check['detail']}")

        blockers = report["blockers"]
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
