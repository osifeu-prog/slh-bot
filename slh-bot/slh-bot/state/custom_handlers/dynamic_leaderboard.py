import json

DB_PATH = "state/db.json"

def register(bot):
    @bot.message_handler(commands=['leaderboard'])
    def dynamic_leaderboard(msg):
        db = json.load(open(DB_PATH))
        scores = {}

        # Points from completed tasks (10 per task)
        tasks = db.get("tasks", [])
        for t in tasks:
            if t.get("status") == "done":
                uid = str(t.get("user_id", "unknown"))
                scores[uid] = scores.get(uid, 0) + 10

        # Points from token balance (0.1 point per SLH)
        token = db.get("token", {})
        balances = token.get("balances", {})
        for uid, bal in balances.items():
            scores[uid] = scores.get(uid, 0) + int(bal * 0.1)

        # Sort and limit to top 10
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:10]

        if not sorted_scores:
            bot.reply_to(msg, "No data yet.")
            return

        text = "🏆 Dynamic Leaderboard:\n"
        for i, (uid, score) in enumerate(sorted_scores, 1):
            text += f"{i}. {uid} – ⭐️ {score}\n"
        bot.reply_to(msg, text)
