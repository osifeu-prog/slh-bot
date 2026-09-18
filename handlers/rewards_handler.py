from core import profile_manager
from core.holiday_campaign import GRANT_AMOUNT, eligibility

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
        referral_count = _referrals(uid)
        campaign = eligibility(uid)
        status = "זכאי" if campaign.get("eligible") else "לא זכאי"
        text = (
            "🎁 תגמולים\n\n"
            "מקורות תגמול פעילים:\n"
            "• הצטרפות: 1,000 Points\n"
            "• Referral מוצלח: 10 Points\n"
            "• השלמת שיעור: 25 Points\n"
            "• השלמת משימה: לפי המשימה\n"
            f"• Holiday Referral: עד {GRANT_AMOUNT:,} SLH, בכפוף לזכאות\n\n"
            f"Points שלך: {_points(uid):,}\n"
            f"Referrals מוצלחים: {referral_count}\n"
            f"Holiday Referral: {status}"
        )
        bot.reply_to(msg, text)

print("rewards handler loaded")
