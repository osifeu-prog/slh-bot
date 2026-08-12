import json

user_states = {}

def register(bot):

    @bot.message_handler(commands=['join'])
    def join_start(msg):
        uid = str(msg.from_user.id)

        try:
            with open("state/db.json", encoding="utf-8") as f:
                db = json.load(f)

            user = db.get("users", {}).get(uid)

            if user and user.get("joined"):
                bot.reply_to(
                    msg,
                    f"👋 ברוך שובך {user.get('name','')}!\n\n"
                    "הפרופיל שלך כבר קיים.\n"
                    "📚 /courses\n"
                    "💰 /wallet\n"
                    "🏆 /leaderboard"
                )
                return

        except Exception:
            pass

        user_states[uid] = {"step": "name"}
        bot.reply_to(msg, "👋 ברוך הבא! איך קוראים לך? (שם מלא)")

    @bot.message_handler(
        func=lambda m: str(m.from_user.id) in user_states
        and not str(m.text or "").startswith("/")
    )
    def join_steps(msg):
        uid = str(msg.from_user.id)
        state = user_states[uid]
        step = state["step"]

        if step == "name":
            state["name"] = (msg.text or "").strip()
            state["step"] = "group"

            bot.reply_to(
                msg,
                f"נעים מאוד, {state['name']}!\n"
                "לאיזו קבוצה תרצה להצטרף?\n"
                "(לדוגמה: Bitcoin Masters, AI Builders)"
            )

        elif step == "group":
            group = (msg.text or "").strip()

            try:
                with open("state/db.json", "r", encoding="utf-8") as f:
                    db = json.load(f)
            except Exception:
                db = {}

            db.setdefault("users", {}).setdefault(uid, {})

            db["users"][uid].update({
                "name": state.get("name", ""),
                "group": group,
                "joined": True
            })

            with open("state/db.json", "w", encoding="utf-8") as f:
                json.dump(db, f, indent=2, ensure_ascii=False)

            del user_states[uid]

            bot.reply_to(
                msg,
                f"✅ נרשמת בהצלחה, {state['name']}!\n"
                f"קבוצה: {group}\n\n"
                "מה תרצה לעשות עכשיו?\n"
                "📚 /courses\n"
                "💰 /wallet\n"
                "🏆 /leaderboard"
            )

    @bot.message_handler(commands=['cancel_join'])
    def join_cancel(msg):
        uid = str(msg.from_user.id)

        if uid in user_states:
            del user_states[uid]
            bot.reply_to(msg, "❌ ההרשמה בוטלה.")
        else:
            bot.reply_to(msg, "אין הרשמה פעילה.")

print("join handler loaded")
