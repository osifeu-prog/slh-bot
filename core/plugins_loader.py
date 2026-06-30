import os, importlib

def load_plugins(context):
    if not os.path.exists("plugins"):
        return

    for file in os.listdir("plugins"):
        if file.endswith(".py"):
            name = file[:-3]
            try:
                mod = importlib.import_module(f"plugins.{name}")
                if hasattr(mod, "init"):
                    mod.init(context)
                print(f"✅ plugin loaded: {name}")
            except Exception as e:
                print(f"⚠️ plugin failed {name}: {e}")
