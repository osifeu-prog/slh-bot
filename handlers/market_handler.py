import json
from pathlib import Path

def load_store():
    path = Path("state/plugins_store.json")
    if not path.exists():
        return {"plugins": [], "installed": []}
    return json.loads(path.read_text(encoding="utf-8"))

def register(bot, context=None):

    @bot.message_handler(commands=["market", "marketplace", "store"])
    def market(m):
        store = load_store()
    print('MARKET DEBUG STORE:', store)
        lines = [
            f"• {p['name']} ({p['id']}) - 💎{p['price']} [{p['installs']} installs]"
            for p in store.get("plugins", [])
        ]

        if not lines:
            bot.reply_to(m, "Marketplace empty.")
            return

        bot.reply_to(
            m,
            "🛒 Marketplace:\n" + "\n".join(lines)
        )

    print("✅ market handler registered")
