import json
from pathlib import Path

from core.profile_manager import get_balance
from core.marketplace_purchase_service import purchase_plugin

STORE_FILE = Path("state/marketplace.json")


def load_store():
    if not STORE_FILE.exists():
        return {"plugins": [], "installed": []}
    return json.loads(STORE_FILE.read_text(encoding="utf-8"))


def save_store(data):
    STORE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def register(bot, context=None):
    @bot.message_handler(commands=["market", "marketplace", "store"])
    def market(m):
        store = load_store()
        plugins = store.get("plugins", [])
        if not plugins:
            bot.reply_to(m, "Marketplace empty.")
            return
        lines = [f"• {p['name']} ({p['id']}) - {p['price']} credits [{p['installs']} installs]" for p in plugins]
        bot.reply_to(m, "🛒 Marketplace:\n" + "\n".join(lines))

    @bot.message_handler(commands=["mktbuy"])
    def buy(m):
        uid = str(m.from_user.id)
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /mktbuy <plugin_id>")
            return

        plugin_id = parts[1]
        store = load_store()
        plugin = next((p for p in store.get("plugins", []) if p.get("id") == plugin_id), None)
        if not plugin:
            bot.reply_to(m, "❌ Plugin not found.")
            return

        ok, result = purchase_plugin(uid, plugin, request_id=str(getattr(m, "message_id", "")))
        if not ok:
            bot.reply_to(m, f"❌ Purchase failed: {result}")
            return

        if result.get("status") == "pending_fulfillment":
            bot.reply_to(m, f"🟡 Payment recorded: {plugin.get('name', plugin_id)}\n💳 Paid: {result.get('price', plugin.get('price', 0))} credits\n⏳ Plugin fulfillment is pending.")
            return

        # The purchase authority has already charged the wallet and installed
        # the plugin. The marketplace counter is non-financial telemetry.
        try:
            store = load_store()
            current = next((p for p in store.get("plugins", []) if p.get("id") == plugin_id), None)
            if current is not None:
                current["installs"] = current.get("installs", 0) + 1
                save_store(store)
        except Exception:
            pass

        bot.reply_to(m, f"{result.get('message', 'Plugin installed')}\n💳 Paid: {result.get('price', plugin.get('price', 0))} credits\nBalance: {get_balance(uid)}")

    print("✅ market handler registered")
