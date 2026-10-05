"""Owner-only read-only release gate for SLH OS."""

from core.authority import is_owner
from core.release_readiness import build_release_report


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
            lines.append("🛑 Blockers:")
            lines.extend(f"• {item}" for item in blockers)
        else:
            lines.append("✅ אין blockers ב־release gate.")

        lines.append("")
        lines.append("ℹ️ הבדיקה read-only בלבד; אינה פותחת שערי BNB/TON ואינה משנה balances.")
        bot.reply_to(msg, "\n".join(lines), parse_mode=None)

    print("✅ releasecheck loaded")
