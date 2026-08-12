import json
from pathlib import Path

from core.profile_manager import get_balance, add_balance
from plugins_store import install_plugin

STORE_FILE = Path("state/marketplace.json")


def load_store():
    if not STORE_FILE.exists():
        return {"plugins": [], "installed": []}

    return json.loads(
        STORE_FILE.read_text(encoding="utf-8")
    )


def save_store(data):
    STORE_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8"
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


    @bot.message_handler(commands=["buy"])
    def buy(m):
        uid = str(m.from_user.id)

        parts = m.text.split()

        if len(parts) < 2:
            bot.reply_to(
                m,
                "Usage: /buy <plugin_id>"
            )
            return

        plugin_id = parts[1]

        store = load_store()

        plugin = next(
            (p for p in store.get("plugins", []) if p["id"] == plugin_id),
            None
        )

        if not plugin:
            bot.reply_to(
                m,
                "❌ Plugin not found."
            )
            return

        price = plugin.get("price", 0)

        balance = get_balance(uid)

        if balance < price:
            bot.reply_to(
                m,
                f"❌ Not enough credits.\nBalance: {balance}\nRequired: {price}"
            )
            return

        if price > 0:
            add_balance(uid, -price)

        result = install_plugin(plugin_id)

        plugin["installs"] = plugin.get("installs", 0) + 1
        save_store(store)

        bot.reply_to(
            m,
            f"{result}\n"
            f"💳 Paid: {price} credits\n"
            f"Balance: {get_balance(uid)}"
        )

    print("✅ market handler registered")

