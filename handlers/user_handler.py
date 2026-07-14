import json, os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'state', 'db.json')

def load_db():
    with open(DB_PATH, encoding='utf-8') as f:
        return json.load(f)

def register(bot):
    @bot.message_handler(commands=['profile'])
    def user_info(m):
        uid = str(m.chat.id)
        db = load_db()
        user = db.get('users', {}).get(uid, {})
        profile = user.get('profile', {})
        wallet = user.get('wallet', {})
        academy = user.get('academy', {})
        gamification = user.get('gamification', {})
        name = profile.get('name') or profile.get('first_name') or m.from_user.first_name or 'דוניב נכא'
        credits = wallet.get('credits', 0)
        points = gamification.get('points', 0)
        level = gamification.get('level', 1)
        active_course = academy.get('active_course', 'אין')
        progress = len(academy.get('courses', {}).get(active_course, {}).get('completed', [])) if active_course != 'איק' else 0
        total_lessons = 10
        pct = min(100, int(progress / total_lessons * 100)) if total_lessons else 0
        text = f'👤 {name}\n'
        text += f'💰 חואיוה: {credits}\n'
        text += f'⭐ חווידייד: {points}\n'
        text += f'� בריד: {level}\n'
        text += f'📚 חריני נלינדירכית פוירגותיית דרית תכית אכא'
        bot.reply_to(m, text)