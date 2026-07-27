def load_handlers(bot):
    from handlers.logo_handler import register_logo_handler
    register_logo_handler(bot)
    
    from handlers.esp_handler import register_esp_handler
    register_esp_handler(bot)
    
    # שאר ההנדלרים הקיימים שלך
    try:
        from handlers.advanced_ask_handler import register_advanced_ask_handler
        register_advanced_ask_handler(bot)
    except Exception as e:
        print("advanced_ask_handler failed:", e)
    
    try:
        from handlers.llm_handler import register_llm_handler
        register_llm_handler(bot)
    except Exception as e:
        print("llm_handler failed:", e)
