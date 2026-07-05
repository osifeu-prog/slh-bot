import json

DB_PATH = "state/db.json"

def load_db():
    with open(DB_PATH) as f:
        return json.load(f)

def register(bot):
    @bot.message_handler(commands=['leaderboard'])
    def leaderboard(m):
        db = load_db()
        students = db.get("students", {})
        if not students:
            bot.reply_to(m, "📭 No students registered yet.")
            return

        ranked = sorted(
            students.items(),
            key=lambda kv: kv[1].get("referral_count", 0),
            reverse=True
        )

        medals = ["🥇", "🥈", "🥉"]
        lines = ["🏆 **Leaderboard – Top Referrers**\n"]
        for i, (uid, data) in enumerate(ranked[:10]):
            name = data.get("name", f"User {uid}")
            count = data.get("referral_count", 0)
            prefix = medals[i] if i < 3 else f"{i+1}."
            lines.append(f"{prefix} {name} — {count} referrals")

        bot.reply_to(m, "\n".join(lines), parse_mode="Markdown")

def init():
    pass
