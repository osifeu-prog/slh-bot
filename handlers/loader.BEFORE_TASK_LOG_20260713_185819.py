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



    # ===== CHAT REGISTRY =====
    try:
        from handlers.chat_registry_handler import register as register_chat_registry
        register_chat_registry(bot)
        print("💬 Chat registry handler loaded")
    except Exception as e:
        print("chat_registry error:", e)


    # ===== SLH GATEWAY BRIDGE =====
    try:
        from handlers.gateway_handler import register as register_gateway
        register_gateway(bot)
        print("🌐 SLH Gateway handler loaded")
    except Exception as e:
        print("gateway_handler error:", e)


    # ===== ONBOARDING SYSTEM =====
    try:
        import onboarding_handler
        onboarding_handler.init(bot)
        print("🚀 onboarding_handler loaded")
    except Exception as e:
        print("onboarding_handler error:", e)


    # ===== SINGLE SOURCE LEGACY HANDLERS =====

    handlers = [
        ("welcome_handler", "init"),
        ("help_handler", "register_help"),
        ("course_handlers", "register_course_handlers"),
        ("learn_handlers", "register"),
        ("econ_handler", "register_econ_handlers"),
        ("payment_handler", "register_payment_handlers"),
        ("staking_handler", "register_staking_handlers"),
        ("project_commands", "register"),
        ("smart_leaderboard", "register"),
        ("viewfile_handler", "register"),
        ("tutorial_handler", "register"),
    ]

    for module_name, fn_name in handlers:
        try:
            module = __import__(module_name)
            fn = getattr(module, fn_name)
            fn(bot)
            print(f"✅ {module_name} loaded")
        except Exception as e:
            print(f"{module_name} load error:", e)


    # ===== EXTRA MODULAR HANDLERS =====

    try:
        from handlers.academy_menu_handler import register as register_academy_menu
        register_academy_menu(bot)
        print("✅ academy_menu_handler loaded")
    except Exception as e:
        print("academy_menu_handler error:", e)

    try:
        from handlers.lesson_handler import register as register_lesson
        register_lesson(bot)
        print("✅ lesson_handler loaded")
    except Exception as e:
        print("lesson_handler error:", e)

    try:
        from handlers.academy_handler import register as register_academy
        register_academy(bot)
        print("✅ academy_handler loaded")
    except Exception as e:
        print("academy_handler error:", e)

    try:
        from advanced_ask_handler import register_ask_handler
        register_ask_handler(bot)
        print("✅ advanced_ask_handler loaded")
    except Exception as e:
        print("advanced_ask_handler error:", e)

    try:
        from doctor_handler import register_doctor_handlers
        register_doctor_handlers(bot)
        print("✅ doctor_handler loaded")
    except Exception as e:
        print("doctor_handler error:", e)

    print("🧩 Modular + Legacy handlers loaded")
