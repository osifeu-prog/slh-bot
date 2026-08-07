def load_handlers(bot, context):
    from handlers.logo_handler import register_logo_handler
    register_logo_handler(bot)
    print("נ”„ Loading modular handlers...")

    modules = [
        ("dashboard", "handlers.dashboard_handler"),
        ("onboarding", "handlers.onboarding_v2"),
        ("agents", "handlers.agents_handler"),
        ("audit", "handlers.audit_handler"),
        ("termux", "handlers.termux_handler"),
        ("payment", "payment_handler"),
        ("econ", "econ_handler"),
        ("task", "handlers.task_handler"),
        ("mission", "handlers.mission_handler"),
        ("academy", "handlers.academy_handler"),
        ("academy_menu", "handlers.academy_menu_handler"),
        ("device", "handlers.device_handler"),
        ("device_bridge", "handlers.device_bridge"),
        ("feedback", "handlers.feedback_handler"),
        ("gateway", "handlers.gateway_handler"),
        ("help", "handlers.help_handler"),
        ("join", "handlers.join_handler"),
        ("kb", "handlers.kb_handler"),
        ("leaderboard", "handlers.leaderboard_handler"),
        ("lesson", "handlers.lesson_handler"),
        ("llm", "handlers.llm_handler"),
        ("map", "handlers.map_handler"),
        ("me", "handlers.me_handler"),
        ("monitor", "handlers.monitor_handler"),
        ("morning", "handlers.morning_handler"),
        ("ownership_transfer", "handlers.ownership_transfer_handler"),
        ("repeat", "handlers.repeat_handler"),
        ("system", "handlers.system_handler"),
        ("user", "handlers.user_handler"),
        ("voting", "handlers.voting_handler"),
        ("admin", "admin_handler"),                # ← /backup, /admin, /exec
        ("askdebug", "handlers.askdebug_handler"),
    ]

    import importlib
    for name, mod_path in modules:
        try:
            m = importlib.import_module(mod_path)
            if name in ("agents", "audit", "admin"):
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

    # esp & advanced_ask (separate registration)
    try:
        from handlers.esp_handler import register_esp_handler
        register_esp_handler(bot)
        print("✅ esp_handler loaded")
    except Exception as e:
        print("esp_handler skipped:", str(e)[:100])

    try:
        from handlers.advanced_ask_handler import register_ask_handler
        register_ask_handler(bot)
        print("✅ advanced_ask_handler loaded")
    except Exception as e:
        print("ask handler error:", str(e)[:100])

    print("✅ All handlers loaded")

