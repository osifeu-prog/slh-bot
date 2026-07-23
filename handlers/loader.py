def load_handlers(bot, context):
    print("🔄 Loading modular handlers...")
    for name, mod in [
        ("dashboard", "handlers.dashboard_handler"),
        ("onboarding", "handlers.onboarding_v2"),
        ("agents", "handlers.agents_handler"),
    ]:
        try:
            m = __import__(mod, fromlist=["register"])
            m.register(bot, context) if name=="agents" else m.register(bot)
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

    print("✅ All handlers loaded")
