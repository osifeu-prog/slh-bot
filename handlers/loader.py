"""Safe loader - loads only working handlers"""
import importlib, os, sys

def load_handlers(bot, kernel):
    handlers_dir = os.path.dirname(__file__)
    safe_list = [
        'ask_handler', 'terminal_handler', 'map_handler',
        'admin_handler', 'help_handler', 'device_bridge',
        'voting_handler'  # הפלייסהולדר החדש
    ]

    for name in safe_list:
        try:
            mod = importlib.import_module(f'handlers.{name}')
            if hasattr(mod, 'register_handlers'):
                mod.register_handlers(bot, kernel)
                print(f"✅ Loaded: {name}")
        except Exception as e:
            print(f"⚠️ Skip {name}: {e}")

    # טוען API
    try:
        from handlers.device_bridge import register_api
        from flask import Flask
        app = Flask("SLH_API")
        register_api(app)
        print("✅ API loaded")
    except Exception as e:
        print(f"⚠️ API failed: {e}")

print("✅ Safe loader active")
