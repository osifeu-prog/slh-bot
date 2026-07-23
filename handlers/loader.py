def load_handlers(bot, context):
    print("🔄 Loading modular handlers...")
    for name, mod in [
        ("dashboard", "handlers.dashboard_handler"),
        ("onboarding", "handlers.onboarding_v2"),
        ("voting", "handlers.voting_handler"),
        ("agents", "handlers.agents_handler"),
    ]:
        try:
            m = __import__(mod, fromlist=["register"])
            m.register(bot, context) if name=="agents" else m.register(bot)
            print(f"✅ {name}_handler loaded")
        except Exception as e:
            print(f"{name} error:", str(e)[:100])
    print("✅ All handlers loaded")

# === DEVICE BRIDGE API ===
try:
    from handlers.device_bridge import register_api
    register_api(app) # app מגיע מ-bot_stable
    print("✅ device_bridge API loaded")
except Exception as e:
    print("device_bridge error:", e)
