import telebot, json, os, sys
from telebot import types

CONFIG_PATH = "config.json"

# טעינת TOKEN מקובץ הקונפיג
with open(CONFIG_PATH, 'r') as f: config = json.load(f)
TOKEN = config.get("TELEGRAM_BOT_TOKEN", "")
SUPER_ADMIN = config.get("SUPER_ADMIN", 8789977826)

if not TOKEN or ":" not in TOKEN:
    print("שגיאה: אין TELEGRAM_BOT_TOKEN תקין ב-config.json")
    sys.exit(1)

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(m):
    name = m.from_user.first_name or "מפקד"
    msg = f"ברוך שובך, {name}!\nהמערכת פעילה."
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("/staking_report", "/show_keys")
    keyboard.add("/rotate_keys", "/set_keys API SECRET")
    bot.send_message(m.chat.id, msg, reply_markup=keyboard)

@bot.message_handler(commands=['staking_report'])
def staking_report(m):
    with open(CONFIG_PATH, 'r') as f: config = json.load(f)
    if config.get('DEMO_MODE'):
        usdt = 1000.00; profit = usdt * 0.04
        msg = f"💰 Binance USDT: {usdt:.2f} DEMO\n📈 רווח חודשי: {profit:.2f} USDT"
    else: msg = "⚠️ מצב LIVE"
    bot.send_message(m.chat.id, msg)

@bot.message_handler(commands=['show_keys'])
def show_keys(m):
    if m.from_user.id!= SUPER_ADMIN: return bot.send_message(m.chat.id, "⛔ רק SUPER_ADMIN")
    with open(CONFIG_PATH, 'r') as f: config = json.load(f)
    api = config.get('BINANCE_API_KEY', 'לא הוגדר')
    sec = config.get('BINANCE_SECRET', 'לא הוגדר')
    api_show = f"...{api[-4:]}" if len(api) > 4 else api
    sec_show = f"...{sec[-4:]}" if len(sec) > 4 else sec
    msg = f"🔑 מפתחות שמורים:\nAPI: {api_show}\nSECRET: {sec_show}\nDEMO: {config.get('DEMO_MODE')}"
    bot.send_message(m.chat.id, msg)

@bot.message_handler(commands=['set_keys'])
def set_keys(m):
    if m.from_user.id!= SUPER_ADMIN: return bot.send_message(m.chat.id, "⛔ רק SUPER_ADMIN")
    try:
        parts = m.text.split()
        api, secret = parts[1], parts[2]
        with open(CONFIG_PATH, 'r') as f: config = json.load(f)
        config['BINANCE_API_KEY'] = api
        config['BINANCE_SECRET'] = secret
        with open(CONFIG_PATH, 'w') as f: json.dump(config, f, indent=2)
        bot.send_message(m.chat.id, "✅ המפתחות עודכנו. עושה ריסטארט...")
        os.system("pkill -f agent_client_termux.py && sleep 2 && python agent_client_termux.py &")
    except:
        bot.send_message(m.chat.id, "שימוש: /set_keys YOUR_API_KEY YOUR_SECRET_KEY")

@bot.message_handler(commands=['rotate_keys'])
def rotate_keys(m):
    if m.from_user.id!= SUPER_ADMIN: return bot.send_message(m.chat.id, "⛔ רק SUPER_ADMIN")
    bot.send_message(m.chat.id, "שלח לי את ה-BINANCE_API_KEY החדש")
    bot.register_next_step_handler(m, get_new_secret)

def get_new_secret(m): 
    bot.send_message(m.chat.id, "עכשיו שלח את ה-BINANCE_SECRET החדש")
    bot.register_next_step_handler(m, save_keys, m.text.strip())

def save_keys(m, api_key):
    with open(CONFIG_PATH, 'r') as f: config = json.load(f)
    config['BINANCE_API_KEY'] = api_key; config['BINANCE_SECRET'] = m.text.strip()
    with open(CONFIG_PATH, 'w') as f: json.dump(config, f, indent=2)
    bot.send_message(m.chat.id, "✅ התעדכן! עושה ריסטארט...")
    os.system("pkill -f agent_client_termux.py && sleep 2 && python agent_client_termux.py &")

print("🤖 Termux Agent Online")
bot.polling(none_stop=True)
