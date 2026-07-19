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
        register_ai_voting(bot)
