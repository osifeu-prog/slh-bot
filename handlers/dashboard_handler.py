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
        balances = onchain.get("balances", {}) if isinstance(onchain, dict) else {}

        name = identity.get("display_name") or "משתמש"
        enrolled = academy.get("enrolled", [])
        completed = tasks.get("completed", 0)
        total = tasks.get("open", 0) + completed
        alpha_status = alpha.get("status", "unknown")

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
            f"🖥️ System: Alpha {system.get('alpha', 'unknown')} · "
            f"{system.get('users', 0)} users · {system.get('agents', 0)} agents · "
            f"{system.get('store_items', 0)} store items\n\n"
            f"מה תרצה לעשות?"
        )

        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("📚 המשך קורס", callback_data="continue_course"))
        markup.add(types.InlineKeyboardButton("🤖 צור סוכן חדש", callback_data="create_agent"))
        markup.add(types.InlineKeyboardButton("📊 סטטוס מערכת", callback_data="system_status"))
        bot.send_message(m.chat.id, text, reply_markup=markup)
