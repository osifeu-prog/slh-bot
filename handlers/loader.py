def load_handlers(bot, context):

    from handlers.agents_handler import register as register_agents

    register_agents(
        bot,
        context
    )

    print("🧩 Modular handlers loaded")
