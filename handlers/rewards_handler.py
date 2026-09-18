from core.tokenomics import snapshot
from core.holiday_campaign import GRANT_AMOUNT

def register(bot):
    @bot.message_handler(commands=["rewards"])
    def rewards_cmd(msg):
        t = snapshot()
        cr = t["CREDITS"]["pricing_examples"]
        txt = (
            "🎁 תגמולים\n\n"
            "הצטרפות חדשה:        1,000 points\n"
            "השלמת שיעור:         25 points\n"
            "השלמת קורס:          250 points\n"
            "AirDrop SLH:         " + f"{GRANT_AMOUNT:,}" + " SLH (חד-פעמי)\n\n"
            "Credits:\n"
            "100 ⭐️ → " + str(cr["100_stars"]) + "\n"
            "450 ⭐️ → " + str(cr["450_stars"]) + "\n"
            "800 ⭐️ → " + str(cr["800_stars"]) + "\n\n"
            "Staking: 30/60/90/180 ימים (credits)"
        )
        bot.reply_to(msg, txt)
