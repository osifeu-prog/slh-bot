def load_handlers(bot, context=None):
    print("🔄 Loading modular handlers...")
    handlers = [
        ("dashboard", "handlers.dashboard_handler"),
        ("onboarding", "handlers.onboarding_v2"),
        ("voting", "handlers.voting_handler"),
        ("agents", "handlers.agents_handler"),
        ("ask", "handlers.advanced_ask_handler"),
    ]
    for name, mod in handlers:
        try:
            m = __import__(mod, fromlist=["register"])
            if name == "agents": m.register(bot, context)
            elif name == "ask": m.register_ask_handler(bot)
            else: m.register(bot)
            print(f"✅ {name}_handler loaded")
        except Exception as e:
            print(f"❌ {name} error:", str(e)[:100])

    # API נטען רק אם יש app
    if context and 'app' in context:
        try:
            from handlers.device_bridge import register_api
            register_api(context['app'])
            print("✅ device_bridge API loaded")
        except Exception as e:
            print("device_bridge error:", e)
    print("✅ All handlers loaded")
