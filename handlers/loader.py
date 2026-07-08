def load_handlers(bot, context):

    print("🔄 Loading modular handlers...")

    # ===== MODULAR HANDLERS =====
    try:
        from handlers.agents_handler import register as register_agents
        register_agents(bot, context)
    except Exception as e:
        print("agents_handler error:", e)

    try:
        from handlers.task_handler import register as register_task
        register_task(bot, context)
    except Exception as e:
        print("task_handler error:", e)

    try:
        from handlers.morning_handler import register as register_morning
        register_morning(bot, context)
    except Exception as e:
        print("morning_handler error:", e)

    try:
        from handlers.system_handler import register as register_system
        register_system(bot, context)
    except Exception as e:
        print("system_handler error:", e)


    # ===== LEGACY USER EXPERIENCE =====
    legacy = [
        "welcome_handler",
        "help_handler",
        "course_handlers",
        "learn_handlers",
        "econ_handler",
        "payment_handler",
        "project_commands",
        "smart_leaderboard",
    ]

    for module_name in legacy:
        try:
            module = __import__(module_name)

            # handlers with register(bot)
            if hasattr(module, "register"):
                module.register(bot)

            # welcome uses init(bot)
            elif module_name == "welcome_handler" and hasattr(module, "init"):
                module.init(bot)

            # help uses register_help(bot)
            elif module_name == "help_handler" and hasattr(module, "register_help"):
                module.register_help(bot)

            # course/economy style handlers
            elif module_name == "course_handlers" and hasattr(module, "register_course_handlers"):
                module.register_course_handlers(bot)

            elif module_name == "econ_handler" and hasattr(module, "register_econ_handlers"):
                module.register_econ_handlers(bot)

            elif module_name == "payment_handler" and hasattr(module, "register_payment_handlers"):
                module.register_payment_handlers(bot)

            elif module_name == "smart_leaderboard" and hasattr(module, "register"):
                module.register(bot)

        except Exception as e:
            print(f"{module_name} load error:", e)


    print("🧩 Modular + Legacy handlers loaded")
