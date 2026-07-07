path = "bot_stable.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = "ask_handler.init(bot)"
new = "# ask_handler.init(bot)  # DISABLED 2026-07-07: uses local ollama which doesn't exist on Railway, causes duplicate/broken responses alongside advanced_ask_handler"

count = content.count(old)
if count != 1:
    print(f"ERROR: expected 1 occurrence, found {count}, aborting")
else:
    content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Replacement done")
