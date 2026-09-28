import os, json, subprocess, time
from datetime import datetime
from telebot import types

MINI_APP_URL = "https://slh-cloud-bot-production.up.railway.app/mini-app?v=20260928-system"

def register(bot, context=None):
    @bot.message_handler(commands=["os"])
    def os_cmd(message):
        # Railway does not include git in the slim runtime image. Prefer the
        # immutable deployment commit exposed by Railway; use git only locally.
        git_hash = (os.getenv("RAILWAY_GIT_COMMIT_SHA") or "").strip()
        if git_hash:
            git_hash = git_hash[:7]
        else:
            try:
                git_hash = subprocess.check_output(
                    ["git", "rev-parse", "--short", "HEAD"],
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=2,
                ).strip() or "unknown"
            except Exception:
                git_hash = "unknown"

        try:
            from handlers import llm_handler
            now = time.time()
            providers = []
            gemini_key = bool((os.getenv("GEMINI_API_KEY") or "").strip())
            groq_key = bool((os.getenv("GROQ_API_KEY") or "").strip())
            ollama_base = bool((os.getenv("OLLAMA_BASE_URL") or "").strip())
            gemini_cd = now < float(llm_handler._provider_cooldown_until.get("gemini", 0))
            groq_cd = now < float(llm_handler._provider_cooldown_until.get("groq", 0))
            ollama_cd = now < float(getattr(llm_handler, "_OLLAMA_COOLDOWN_UNTIL", 0))
            if gemini_key:
                providers.append("Gemini:cooldown" if gemini_cd else "Gemini:configured")
            if groq_key:
                providers.append("Groq:cooldown" if groq_cd else "Groq:configured")
            if ollama_base:
                providers.append("Ollama:cooldown" if ollama_cd else "Ollama:configured")
            llm_state = "✅" if any([
                gemini_key and not gemini_cd,
                groq_key and not groq_cd,
                ollama_base and not ollama_cd,
            ]) else ("⚠️" if providers else "❌")
            llm_detail = ", ".join(providers) if providers else "none configured"
        except Exception:
            llm_state = "⚠️"
            llm_detail = "status unavailable"

        railway = os.getenv("RAILWAY_ENVIRONMENT", "local")
        handlers = len([f for f in os.listdir("handlers") if f.endswith(".py")])
        try:
            from core.agent_registry import STORE
            agents = len(STORE.get_all())
        except Exception:
            agents = "?"
        try:
            with open("state/ai_health.json") as f:
                health = json.load(f)
            ai_failures = health["groq"]["failures"]
        except Exception:
            ai_failures = "?"

        header = f"""🟢 SLH OS CONTROL CENTER
{datetime.now():%Y-%m-%d %H:%M:%S}
🔀 Git: {git_hash} | 🧠 LLM: {llm_state} ({llm_detail}) | 🌐 {railway}
📂 Handlers: {handlers} | 🤖 Agents: {agents} | ❤️ AI: {ai_failures} failures
"""

        menu = (
            "CORE: /start /os /status /help /miniapp /dashboard /ask\n"
            "MONEY: /wallet /market /pay /transfer /stake /exchange /orders /withdraw\n"
            "ALPHA: /alpha /academy /share /rewards /task /journal\n"
            "CONTROL: /system /map /services /agents /control /projects /deploy /redeploy /logs\n"
            "SECURITY: /vault /vault_verify /vault_health /vault_log\n"
            "CHAIN: /ton_address /ton_balance /ton_claim /settlement_status\n"
            "DEV: /e /exec"
        )
        bot.reply_to(message, header + menu)

    @bot.message_handler(commands=["miniapp"])
    def miniapp_cmd(message):
        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton(
            text="🚀 פתח מיני-אפ",
            web_app=types.WebAppInfo(url=MINI_APP_URL)
        )
        markup.add(btn)
        bot.send_message(message.chat.id, "SLH OS Mini‑App", reply_markup=markup)

    print("✅ os + miniapp handler registered")
