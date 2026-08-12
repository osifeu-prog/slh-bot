import json, os

def register(bot):
    @bot.message_handler(commands=['stake'])
    def stake_cmd(msg):
        try:
            amount = int(msg.text.split()[-1])
            with open('state/db.json', encoding='utf-8') as f:
                db = json.load(f)
            user = db['users'].setdefault(str(msg.from_user.id), {}).setdefault('wallet', {})
            if user.get('credits', 0) < amount:
                bot.reply_to(msg, f"אין מספיק קרדיטים ({user.get('credits', 0)})")
                return
            user['credits'] -= amount
            user.setdefault('staked', 0)
            user['staked'] += amount
            with open('state/db.json', 'w', encoding='utf-8') as f:
                json.dump(db, f, ensure_ascii=False, indent=2)
            bot.reply_to(msg, f"✅ {amount} credits הועברו לסטייקינג")
        except Exception as e:
            bot.reply_to(msg, f"❌ {e}")

    @bot.message_handler(commands=['unstake'])
    def unstake_cmd(msg):
        try:
            amount = int(msg.text.split()[-1])
            with open('state/db.json', encoding='utf-8') as f:
                db = json.load(f)
            user = db['users'].setdefault(str(msg.from_user.id), {}).setdefault('wallet', {})
            if user.get('staked', 0) < amount:
                bot.reply_to(msg, f"אין מספיק סטייק ({user.get('staked', 0)})")
                return
            user['staked'] -= amount
            user['credits'] += amount
            with open('state/db.json', 'w', encoding='utf-8') as f:
                json.dump(db, f, ensure_ascii=False, indent=2)
            bot.reply_to(msg, f"✅ {amount} credits הוחזרו מהסטייקינג")
        except Exception as e:
            bot.reply_to(msg, f"❌ {e}")
