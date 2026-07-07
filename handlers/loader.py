def load_handlers(bot, context):

    from handlers.agents_handler import register as register_agents
    from handlers.task_handler import register as register_task
    from handlers.morning_handler import register as register_morning
    from handlers.system_handler import register as register_system

    register_agents(bot, context)
    register_task(bot, context)
    register_morning(bot, context)
    register_system(bot, context)

    print("🧩 Modular handlers loaded")
