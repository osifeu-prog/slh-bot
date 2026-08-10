def load_handlers(bot, context):
    from handlers.logo_handler import register_logo_handler
    register_logo_handler(bot)

    print("?? Loading modular handlers...")

    modules = [
        ("dashboard", "handlers.dashboard_handler"),
        ("onboarding", "handlers.onboarding_v2"),
        ("agents", "handlers.agents_handler"),
        ("audit", "handlers.audit_handler"),
        ("termux", "handlers.termux_handler"),
        ("payment", "handlers.payment_handler"),
        ("econ", "econ_handler"),
        ("wallet", "handlers.wallet_handler"),
        ("task", "handlers.task_handler"),
        ("mission", "handlers.mission_handler"),
        ("academy", "handlers.academy_handler"),
        ("academy_menu", "handlers.academy_menu_handler"),
        ("device", "handlers.device_handler"),
        ("feedback", "handlers.feedback_handler"),
        ("gateway", "handlers.gateway_handler"),
        ("help", "handlers.help_handler"),
        ("join", "handlers.join_handler"),
        ("kb", "handlers.kb_handler"),
        ("leaderboard", "handlers.leaderboard_handler"),
        ("learning_path", "learning_path"),
        ("lesson", "handlers.lesson_handler"),
        ("llm", "handlers.llm_handler"),
        ("map", "handlers.map_handler"),
        ("me", "handlers.me_handler"),
        ("monitor", "handlers.monitor_handler"),
        ("journal", "handlers.journal_handler"),
        ("endday", "handlers.endday_handler"),
        ("morning", "handlers.morning_handler"),
        ("ownership_transfer", "handlers.ownership_transfer_handler"),
        ("repeat", "handlers.repeat_handler"),
        ("system", "handlers.system_handler"),
        ("user", "handlers.user_handler"),
        ("voting", "handlers.ai_voting_handler"),
        ("staking", "handlers.staking_handler"),
        ("dev", "handlers.dev_handler"),
        ("ux", "handlers.ux_handler"),
        ("admin", "admin_handler"),
        ("admin_extras", "handlers.admin_extras"),
        ("askdebug", "handlers.askdebug_handler"),
        ("exec", "handlers.exec_handler"),
        ("git", "handlers.git_handler"),
        ("ton", "ton_handler"),
    ]

    import importlib
    import inspect

    for name, mod_path in modules:
        try:
            m = importlib.import_module(mod_path)

            if hasattr(m, "register"):
                fn = m.register
                params = inspect.signature(fn).parameters

                if len(params) >= 2:
                    fn(bot, context)
                else:
                    fn(bot)

            elif hasattr(m, "register_llm_handler"):
                m.register_llm_handler(bot)

            elif hasattr(m, "register_help"):
                m.register_help(bot)

            elif hasattr(m, "register_repeat_handler"):
                m.register_repeat_handler(bot)

            elif hasattr(m, "init"):
                m.init(bot)

            elif hasattr(m, "register_learning_path"):
                m.register_learning_path(bot)

            elif hasattr(m, "register_handlers"):
                m.register_handlers(bot, context)

            else:
                raise Exception("No supported register function")

            print(f"? {name} loaded")

        except Exception as e:
            print(f"?? {name} skipped:", str(e)[:120])

    try:
        from handlers.esp_handler import register_esp_handler
        register_esp_handler(bot)
        print("? esp loaded")
    except Exception as e:
        print("esp skipped:", e)

    try:
        from handlers.advanced_ask_handler import register_ask_handler
        register_ask_handler(bot)
        print("? advanced ask loaded")
    except Exception as e:
        print("ask skipped:", e)

    print("? ALL HANDLERS READY")
