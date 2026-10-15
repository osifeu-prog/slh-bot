from core import profile_manager
from core.daily_reward_service import DAILY_POINTS, claim_daily_reward, get_daily_status
from core.tokenomics import rewards_snapshot
from core.holiday_campaign import eligibility


def _points(uid):
    user = profile_manager.get_user(str(uid)) or {}
    return int((user.get("gamification") or {}).get("points", 0) or 0)


def _referrals(uid):
    user = profile_manager.get_user(str(uid)) or {}
    return int((user.get("referral") or {}).get("count", 0) or 0)


def register(bot):
    @bot.message_handler(commands=["daily"])
    def daily(msg):
        uid = str(msg.from_user.id)
        try:
            result = claim_daily_reward(uid)
        except Exception as exc:
            print("DAILY REWARD CLAIM FAILED:", type(exc).__name__)
            bot.reply_to(
                msg,
                "⚠️ לא הצלחתי לאמת את התגמול היומי כרגע. "
                "לא ניתנו Credits או SLH. נסה שוב מאוחר יותר.",
            )
            return

        status = result.get("status")
        if status == "user_not_found":
            bot.reply_to(
                msg,
                "כדי לאסוף תגמול יומי צריך חשבון SLH OS קיים. "
                "פתח /start והשלם את ההרשמה.",
            )
            return

        points_total = int(result.get("points_total", _points(uid)) or 0)
        streak = int(result.get("streak", 0) or 0)
        if status == "claimed":
            bot.reply_to(
                msg,
                "🎁 התגמול היומי נאסף!\n"
                f"⭐ +{DAILY_POINTS} Points\n"
                f"🔥 רצף: {streak} ימים\n"
                f"🏆 סך Points: {points_total:,}\n\n"
                "Points הם ניקוד משחקי ואינם Credits או SLH.",
            )
        else:
            bot.reply_to(
                msg,
                "✅ התגמול היומי כבר נרשם היום. לא יינתן תגמול כפול.\n"
                f"🔥 רצף: {streak} ימים\n"
                f"🏆 סך Points: {points_total:,}",
            )

    @bot.message_handler(commands=["rewards"])
    def rewards(msg):
        uid = str(msg.from_user.id)
        r = rewards_snapshot()
        campaign = eligibility(uid)
        status = "זכאי" if campaign.get("eligible") else "לא זכאי"
        try:
            daily = get_daily_status(uid)
            daily_status = "נאסף היום" if daily.get("claimed_today") else "זמין לאיסוף"
            daily_line = (
                f"• תגמול יומי: +{DAILY_POINTS} Points — {daily_status} "
                f"(רצף: {daily.get('next_streak', 1)} ימים; /daily)\n"
            )
        except Exception:
            daily_line = f"• תגמול יומי: +{DAILY_POINTS} Points — סטטוס לא זמין; נסה /daily\n"

        text = (
            "🎁 תגמולים\n\n"
            "מקורות תגמול פעילים:\n"
            f"{daily_line}"
            f"• הצטרפות: {r['join_points']:,} Points\n"
            f"• Referral מוצלח: +{r['referral_points']:,} Points +{r['referral_credits']} Credits\n"
            f"• השלמת שיעור: {r['lesson_complete_points']:,} Points\n"
            f"• Airdrop SLH: {r['airdrop_slh']:,} SLH\n"
            "• השלמת משימה: לפי המשימה\n"
            "• Holiday Referral 100,000 SLH: מבצע חד־יומי שהסתיים ב־11/09/2026\n\n"
            f"Points שלך: {_points(uid):,}\n"
            f"Referrals מוצלחים: {_referrals(uid)}\n"
            "Referral קבוע: פעיל"
        )
        bot.reply_to(msg, text)
