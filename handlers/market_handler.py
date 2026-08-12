import json
from pathlib import Path

STORE_FILE = Path("state/marketplace.json")

def load_store():
    if not STORE_FILE.exists():
        return {"plugins": [], "installed": []}

    return json.loads(
        STORE_FILE.read_text(encoding="utf-8")
    )


def register(bot, context=None):

    @bot.message_handler(commands=["market", "marketplace", "store"])
    def market(m):
        store = load_store()

        plugins = store.get("plugins", [])

        if not plugins:
            bot.reply_to(m, "Marketplace empty.")
            return

        lines = [
            f"• {p['name']} ({p['id']}) - {p['price']} credits [{p['installs']} installs]"
            for p in plugins
        ]

        bot.reply_to(
            m,
            "🛒 Marketplace:\n" + "\n".join(lines)
        )

    print("✅ market handler registered")
