def load_handlers(bot, context):

    @bot.message_handler(commands=['register'])
    def register_redirect(m):
        bot.reply_to(m, '👋 נא להשתמש ב־/join להרשמה:')
        from handlers.join_handler import register as jr
        jr(bot)
        # call join_start manually
        for h in bot.message_handlers:
            if hasattr(h, 'name') and h.name == 'join_start':
                h(m)
                break

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
        from state.custom_handlers.ai_voting_handler import register as register_ai_voting
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


    # ===== LEGACY USER EXPERIENCE =====
    legacy = [
        "welcome_handler",
        "onboarding_handler",
        "help_handler",
        "course_handlers",
        "learn_handlers",
        "econ_handler",
        "payment_handler",
        "project_commands",
        "smart_leaderboard",
        "report_handler",
    ]

    for module_name in legacy:
        try:
            module = __import__(module_name)

            # handlers with register(bot)
            if hasattr(module, "register"):
                module.register(bot)

            # report uses init(bot)
            elif module_name == "report_handler" and hasattr(module, "init"):
                module.init(bot)

            # welcome uses init(bot)
            elif module_name == "welcome_handler" and hasattr(module, "init"):
                module.init(bot)

            # onboarding uses init(bot)
            elif module_name == "onboarding_handler" and hasattr(module, "init"):
                print(">>> LOADING ONBOARDING HANDLER")
                module.init(bot)
                print(">>> ONBOARDING HANDLER LOADED")

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
    register_ai_voting(bot)
    try:
        from handlers.join_handler import register as register_join
        register_join(bot)
        print("👤 join_handler loaded")
    except Exception as e:
        print("join_handler error:", e)
    try:
        from advanced_ask_handler import register_ask_handler
        register_ask_handler(bot)
        print("🔥 ASK HANDLER REGISTERED ON BOT:", id(bot))
        print("✅ advanced_ask_handler loaded")
    except Exception as e:
        print("advanced_ask_handler error:", e)
try:
    import json
    @bot.message_handler(commands=['economy'])
    def economy_cmd(m):
        uid = str(m.from_user.id)
        db = json.load(open('state/db.json'))
        user = db.get('users', {}).get(uid, {})
        credits = user.get('wallet', {}).get('credits', 0)
        points = user.get('gamification', {}).get('points', 0)
        token = db.get('token', {}).get('balances', {}).get(uid, 0)
        bot.reply_to(m, f'💰 Economy Dashboard\n🔹 Credits: {credits}\n🔹 Points: {points}\n🔹 SLH: {token}')
except Exception as e:
    print("economy_handler error:", e)
