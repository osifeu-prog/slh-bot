import json
from pathlib import Path

from core.asset_registry import all_assets
from core.tokenomics import snapshot
from core.revenue_ledger import summary as revenue_summary


def register(bot):
    @bot.message_handler(commands=["assets"])
    def assets_cmd(msg):
        lines = ["💼 SLH Assets"]
        for key, asset in all_assets().items():
            status = "TRADABLE" if asset.get("tradable") else "NOT TRADABLE"
            chain = "on-chain" if asset.get("on_chain") else "internal"
            lines.append(f"• {asset['symbol']} — {asset['name']} — {status} — {chain}")
        bot.reply_to(msg, "\n".join(lines))

    @bot.message_handler(commands=["tokenomics"])
    def tokenomics_cmd(msg):
        data = snapshot()
        lines = ["🪙 SLH Tokenomics"]
        for key, item in data.items():
            lines.append(
                f"• {key}: {item.get('type')} | on-chain={item.get('on_chain', False)} | "
                f"tradable={item.get('tradable', False)}"
            )
        lines.append("\nAcademy remains a learning product and is independent of staking access.")
        lines.append("SLH has no declared minting path in the current model.")
        bot.reply_to(msg, "\n".join(lines))

    @bot.message_handler(commands=["revenue_audit"])
    def revenue_audit_cmd(msg):
        from admin_utils import is_admin
        if not is_admin(msg):
            bot.reply_to(msg, "⛔️ Admin only")
            return
        data = revenue_summary()
        lines = [f"📈 Revenue ledger events: {data['events']}"]
        for currency, total in sorted(data["totals"].items()):
            lines.append(f"• {currency}: {total}")
        lines.append("Internal Credit spending is not counted as cash revenue.")
        bot.reply_to(msg, "\n".join(lines))
