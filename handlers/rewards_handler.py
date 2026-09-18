from core import profile_manager
from core.tokenomics import rewards_snapshot
from core.holiday_campaign import eligibility


def _points(uid):
    user = profile_manager.get_user(str(uid)) or {}
    return int((user.get("gamification") or {}).get("points", 0) or 0)


def _referrals(uid):
    user = profile_manager.get_user(str(uid)) or {}
    return int((user.get("referral") or {}).get("count", 0) or 0)


def register(bot):
    @bot.message_handler(commands=["rewards"])
    def rewards(msg):
        uid = str(msg.from_user.id)
        r = rewards_snapshot()
        campaign = eligibility(uid)
        status = "זכאי" if campaign.get("eligible") else "לא זכאי"
        text = (
            "🎁 תגמולים\n\n"
            "מקורות תגמול פעילים:\n"
            f"• הצטרפות: {r['join_points']:,} Points\n"
            f"• Referral מוצלח: {r['referral_points']:,} Points\n"
            f"• השלמת שיעור: {r['lesson_complete_points']:,} Points\n"
            "• השלמת משימה: לפי המשימה\n"
            f"• Holiday Referral: עד {r['airdrop_slh']:,} SLH, בכפוף לזכאות\n\n"
            f"Points שלך: {_points(uid):,}\n"
            f"Referrals מוצלחים: {_referrals(uid)}\n"
            f"Holiday Referral: {status}"
        )
        bot.reply_to(msg, text)
