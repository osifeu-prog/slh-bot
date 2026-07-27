def load_handlers(bot, context):
    print("🔄 Loading modular handlers...")
    for name, mod in [
        ("dashboard", "handlers.dashboard_handler"),
        ("onboarding", "handlers.onboarding_v2"),
        ("agents", "handlers.agents_handler"),
        ("audit", "handlers.audit_handler"),
        ("termux", "handlers.termux_handler"),
        ("payment", "payment_handler"),
        ("econ", "econ_handler"),
        ("task", "handlers.task_handler"),
        ("mission", "handlers.mission_handler"),
    ]:
        try:
            import importlib
            m = importlib.import_module(mod)

            if name in ("agents", "audit"):
                register = getattr(m, "register")
                register(bot, context)
            elif name == "payment":
                register = getattr(m, "register_payment_handlers")
                register(bot)
            elif name == "econ":
                register = getattr(m, "register_econ_handlers")
                register(bot)
            else:
                register = getattr(m, "register")
                register(bot)

            print(f"✅ {name}_handler loaded")
        except Exception as e:
            print(f"{name} error:", str(e)[:100])

    # Ask handler (LLM)
    try:
        from handlers.advanced_ask_handler import register_ask_handler
        register_ask_handler(bot)
        print("✅ advanced_ask_handler loaded")
    except Exception as e:
        print("ask handler error:", str(e)[:100])

    try:
        from admin_utils import is_admin
        @bot.message_handler(commands=["admin"])
        def admin_cmd(m):
            if not is_admin(m): bot.reply_to(m,"⛔️ גישת מנהל בלבד.");return
            bot.reply_to(m,"🛡 פאנל ניהול:\n/status\n/agents\n/dashboard")
        print("✅ admin_handler loaded")
    except Exception as e:
        print("admin handler error:", e)
    print("✅ All handlers loaded")
