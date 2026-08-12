import os, json, subprocess
from datetime import datetime
from telebot import types

def register(bot, context=None):
    @bot.message_handler(commands=["os"])
    def os_cmd(message):
        git_hash = subprocess.getoutput("git rev-parse --short HEAD")
        groq = "✅" if os.getenv("GROQ_API_KEY") else "❌"
        railway = os.getenv("RAILWAY_ENVIRONMENT", "local")
        handlers = len([f for f in os.listdir("handlers") if f.endswith(".py")])
        try:
            from core.agent_registry import STORE
            agents = len(STORE.get_all())
        except: agents = "?"
        try:
            with open("state/ai_health.json") as f: health = json.load(f)
            ai_failures = health["groq"]["failures"]
        except: ai_failures = "?"
        header = f"""🟢 SLH OS CONTROL CENTER
{datetime.now():%Y-%m-%d %H:%M:%S}
🔀 Git: {git_hash} | 🧠 LLM: {groq} | 🌐 {railway}
📂 Handlers: {handlers} | 🤖 Agents: {agents} | ❤️ AI: {ai_failures} failures
"""
        menu = "/start /agents /task /wallet /market /miniapp /ask /dashboard /help /status"
        bot.reply_to(message, header + menu)

    @bot.message_handler(commands=["miniapp"])
    def miniapp_cmd(message):
        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton(
            text="🚀 פתח מיני-אפ",
            web_app=types.WebAppInfo(url="https://web-production-22f28.up.railway.app/mini-app")
        )
        markup.add(btn)
        bot.send_message(message.chat.id, "SLH OS Mini‑App", reply_markup=markup)

    print("✅ os + miniapp handler registered")
