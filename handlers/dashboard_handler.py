from telebot import types


def register(bot):
    @bot.message_handler(commands=["dashboard"])
    def dashboard(m):
        try:
            from core.dashboard_read_model import get_dashboard
            d = get_dashboard(str(m.from_user.id))
        except ValueError as exc:
            if str(exc) == "USER_NOT_FOUND":
                bot.send_message(m.chat.id, "❌ המשתמש לא נמצא במערכת.")
                return
            bot.send_message(m.chat.id, "❌ לא ניתן לטעון Dashboard כרגע.")
            return
        except Exception as exc:
            print(f"[DASHBOARD] {type(exc).__name__}")
            bot.send_message(m.chat.id, "❌ לא ניתן לטעון Dashboard כרגע.")
            return

        identity = d.get("identity", {})
        wallet = d.get("wallet", {})
        academy = d.get("academy", {})
        tasks = d.get("tasks", {})
        alpha = d.get("alpha", {})
        rewards = d.get("rewards", {})
        system = d.get("system", {})
        onchain = d.get("onchain", {})
        exchange = d.get("exchange", {})
        balances = onchain.get("balances", {}) if isinstance(onchain, dict) else {}

        name = identity.get("display_name") or "משתמש"
        enrolled = academy.get("enrolled", [])
        completed = tasks.get("completed", 0)
        total = tasks.get("open", 0) + completed
        alpha_status = alpha.get("status", "unknown")

        ex_status = exchange.get("status", {}) if isinstance(exchange, dict) else {}
        ex_ticker = exchange.get("ticker", {}) if isinstance(exchange, dict) else {}
        ex_book = exchange.get("orderbook", {}) if isinstance(exchange, dict) else {}
        ex_last = ex_ticker.get("last_price")
        ex_bid = ex_book.get("best_bid")
        ex_ask = ex_book.get("best_ask")

        if ex_last is None:
            ex_last_text = "אין עסקה אחרונה"
        else:
            ex_last_text = str(ex_last)

        text = (
            f"🌟 ה-Dashboard שלך\n\n"
            f"👤 {name} · {identity.get('role', 'USER')}\n"
            f"💰 Credits: {wallet.get('credits', 0)}\n"
            f"🔒 Staked: {wallet.get('staked', 0)}\n"
            f"🪙 Internal SLH: {wallet.get('token_balance', 0)}\n\n"
            f"⛓️ On-chain SLH: {balances.get('SLH', 0)}\n"
            f"📚 Academy: {len(enrolled)} enrolled\n"
            f"🎯 Tasks: {completed}/{total} completed\n"
            f"🏁 Alpha: {alpha_status}\n"
            f"🏆 Points: {rewards.get('points', 0)}\n\n"
            f"🪙 Exchange: {'OPEN' if ex_status.get('open') else 'CLOSED'}\n"
            f"   Ask: {ex_ask if ex_ask is not None else '—'}\n"
            f"   Bid: {ex_bid if ex_bid is not None else '—'}\n"
            f"   Last: {ex_last_text}\n"
            f"   Orders: {ex_status.get('total_orders', 0)} · Trades: {ex_status.get('total_trades', 0)}\n\n"
            f"🖥️ System: Alpha {system.get('alpha', 'unknown')} · "
            f"{system.get('users', 0)} users · {system.get('agents', 0)} agents · "
            f"{system.get('store_items', 0)} store items\n\n"
            f"מה תרצה לעשות?"
        )

        markup = types.InlineKeyboardMarkup(row_width=3)
        markup.add(
            types.InlineKeyboardButton("👛 ארנק", callback_data="menu_wallet"),
            types.InlineKeyboardButton("📚 Academy", callback_data="continue_course"),
            types.InlineKeyboardButton("🎯 משימות", callback_data="menu_missions"),
        )
        markup.add(
            types.InlineKeyboardButton("🤖 סוכנים", callback_data="menu_agents"),
            types.InlineKeyboardButton("🧠 AI", callback_data="menu_ai"),
            types.InlineKeyboardButton("🎁 Rewards", callback_data="gifts:home"),
        )
        markup.add(
            types.InlineKeyboardButton("👥 הזמנה", callback_data="menu_share"),
            types.InlineKeyboardButton("📊 מערכת", callback_data="system_status"),
            types.InlineKeyboardButton("🔄 רענון", callback_data="refresh_dashboard"),
        )
        markup.add(
            types.InlineKeyboardButton(
                "🚀 Mini App",
                web_app=types.WebAppInfo(
                    url="https://slh-cloud-bot-production.up.railway.app/mini-app-v4?v=20260925-dashboard"
                ),
            )
        )
        bot.send_message(m.chat.id, text, reply_markup=markup)
