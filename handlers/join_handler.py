import json

user_states = {}

def register(bot):
    @bot.message_handler(commands=['join'])
    def join_start(msg):
        uid = str(msg.from_user.id)
        user_states[uid] = {"step": "name"}
        bot.reply_to(msg, "👋 ברוך הבא! איך קוראים לך? (שם מלא)")

    @bot.message_handler(func=lambda m: str(m.from_user.id) in user_states)
    def join_steps(msg):
        uid = str(msg.from_user.id)
        state = user_states[uid]
        step = state["step"]

        if step == "name":
            state["name"] = msg.text.strip()
            state["step"] = "group"
            bot.reply_to(msg, f"נעים מאוד, {state['name']}!\nלאיזו קבוצה תרצה להצטרף?\n(לדוגמה: Bitcoin Masters, AI Builders, או כל שם שתרצה)")

        elif step == "group":
            group = msg.text.strip()
            # שמור הרשמה
            try:
                with open("state/db.json", "r") as f:
                    db = json.load(f)
            except:
                db = {}
            db.setdefault("users", {}).setdefault(uid, {})
            db["users"][uid].update({
                "name": state.get("name", ""),
                "group": group,
                "joined": True
            })
            with open("state/db.json", "w") as f:
                json.dump(db, f, indent=2, ensure_ascii=False)

            del user_states[uid]
            bot.reply_to(msg, f"✅ נרשמת בהצלחה, {state['name']}!\nקבוצה: {group}\n\nמה תרצה לעשות עכשיו?\n📚 /courses\n💰 /token_wizard\n🏆 /leaderboard")

    @bot.message_handler(commands=['cancel_join'])
    def join_cancel(msg):
        uid = str(msg.from_user.id)
        if uid in user_states:
            del user_states[uid]
            bot.reply_to(msg, "❌ ההרשמה בוטלה.")
        else:
            bot.reply_to(msg, "אין הרשמה פעילה.")
