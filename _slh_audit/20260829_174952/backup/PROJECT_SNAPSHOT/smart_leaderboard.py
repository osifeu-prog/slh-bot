import json

DB_PATH = "state/db.json"

def load_db():
    with open(DB_PATH) as f:
        return json.load(f)

def register(bot):
    @bot.message_handler(commands=['leaderboard'])
    def leaderboard(m):
        db = load_db()
        users = db.get('users', {})
        ranking = []
        for uid, u in users.items():
            name = u.get('profile', {}).get('name') or u.get('profile', {}).get('first_name') or uid
            points = u.get('gamification', {}).get('points', 0)
            ranking.append((name, points))
        if not ranking:
            bot.reply_to(m, '📭 No users yet.')
            return
        ranking.sort(key=lambda x: x[1], reverse=True)
        lines = ['🏆 Leaderboard:']
        for i, (name, pts) in enumerate(ranking, 1):
            lines.append(f'{i}. {name} – ⭐️ {pts}')
        bot.reply_to(m, '\n'.join(lines))
