"""Share & Referral handler."""
import state_manager

def register(bot):
    @bot.message_handler(commands=["share","refer","invite"])
    def share_cmd(msg):
        uid=str(msg.from_user.id)
        db=state_manager.load_db()
        u=db.get("users",{}).get(uid,{})
        bot_username="Me_ad_main_bot"
        link=f"https://t.me/{bot_username}?start=ref_{uid}"
        ref=u.get("referral",{}) if isinstance(u.get("referral"),dict) else {}
        count=ref.get("count",0)
        commission=ref.get("commission",0)
        text=(
            "🔗 ההזמנה האישית שלך\n\n"
            f"{link}\n\n"
            f"👥 הוזמנו: {count}\n"
            f"💰 עמלות: {commission}\n\n"
            "שתף עם חברים — כשהם קונים, אתה מרוויח."
        )
        bot.reply_to(msg,text)
