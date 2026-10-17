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
