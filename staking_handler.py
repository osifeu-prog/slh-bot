from bot_core import bot
import sqlite3
import os
from telebot import TeleBot
from binance.client import Client

DB_PATH = "/data/data/com.termux/files/home/slh_clean/slh_state.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS staking
                 (user_id INTEGER PRIMARY KEY, amount REAL, binance_address TEXT)''')
    conn.commit()
    return conn

def register_staking_handlers(bot: TeleBot):
    binance_key = os.getenv("BINANCE_API_KEY")
    binance_secret = os.getenv("BINANCE_SECRET")
    binance = Client(binance_key, binance_secret) if binance_key else None

    @bot.message_handler(commands=['stake'])
    def stake(m):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT amount FROM staking WHERE user_id=?", (m.from_user.id,))
        row = c.fetchone()
        amount = row[0] if row else 0
        conn.close()
        bot.send_message(m.chat.id, f"🏦 SLH STAKING\nStatus: {'Active' if amount else 'Not active'}\nLocked: {amount} credits")

    @bot.message_handler(commands=['stake_join'])
    def stake_join(m):
        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO staking (user_id, amount) VALUES (?, 100)", (m.from_user.id,))
        conn.commit()
        conn.close()
        bot.send_message(m.chat.id, "✅ Joined SLH Staking\nInitial stake: 100 credits\nYour rewards engine is active 🚀")

    @bot.message_handler(commands=['staking_report'])
    def staking_report(m):
        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT amount FROM staking WHERE user_id=?", (m.from_user.id,))
        row = c.fetchone()
        amount = row[0] if row else 0
        conn.close()

        reward = amount * 0.04 / 365
        binance_balance = "N/A"
        if binance:
            try: binance_balance = binance.get_asset_balance(asset='USDT')['free']
            except: pass

        bot.send_message(m.chat.id, f"📊 STAKING REPORT\nStake: {amount}\nEst Daily Reward: {reward:.4f}\nBinance USDT: {binance_balance}\nStatus: {'ACTIVE' if amount else 'INACTIVE'}")

import json

@bot.message_handler(commands=['rotate_keys'])
def rotate_keys(m):
    if m.from_user.id != 8789977826:
        return bot.send_message(m.chat.id, "⛔ רק SUPER_ADMIN")
    
    new_key = bot.send_message(m.chat.id, "שלח לי את ה-BINANCE_API_KEY החדש")
    bot.register_next_step_handler(new_key, get_new_secret)

def get_new_secret(m):
    api_key = m.text.strip()
    bot.send_message(m.chat.id, "עכשיו שלח את ה-BINANCE_SECRET החדש")
    bot.register_next_step_handler(m, save_keys, api_key)

def save_keys(m, api_key):
    secret = m.text.strip()
    config_path = "/data/data/com.termux/files/home/slh_clean/config.json"
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    config['BINANCE_API_KEY'] = api_key
    config['BINANCE_SECRET'] = secret
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    bot.send_message(m.chat.id, "✅ המפתחות התעדכנו! עושה ריסטארט לבוט...")
    os.system("pkill -f agent_client_termux.py && sleep 2 && python agent_client_termux.py &")

