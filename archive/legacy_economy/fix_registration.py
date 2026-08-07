import re

with open('bot_stable.py', 'r') as f:
    content = f.read()

# מוסיף רישום אוטומטי בתוך start_handler
register_code = '''
    # רישום אוטומטי למסד
    conn = sqlite3.connect('slh_empire.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO wallets VALUES (?,0)", (str(message.from_user.id),))
    conn.commit()
    conn.close()
'''

content = re.sub(r'(def start_handler\(message\):)', r'\1' + register_code, content)

# מוסיף פקודת wallet אם אין
if 'wallet_handler' not in content:
    wallet_code = '''

@bot.message_handler(commands=['wallet', 'יתרה'])
def wallet_handler(message):
    conn = sqlite3.connect('slh_empire.db')
    c = conn.cursor()
    c.execute("SELECT wallet_balance FROM wallets WHERE user_id=?", (str(message.from_user.id),))
    res = c.fetchone()
    balance = res[0] if res else 0
    conn.close()
    bot.reply_to(message, f"👑 היתרה שלך: {balance} SLH")
'''
    content += wallet_code

with open('bot_stable.py', 'w') as f:
    f.write(content)

print("תוקן: רישום אוטומטי + /wallet נוספו")
