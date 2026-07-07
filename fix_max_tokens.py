path = "advanced_ask_handler.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

old = '"max_tokens": 500, "temperature": 0.7'
new = '"max_tokens": 1200, "temperature": 0.7'

count = content.count(old)
if count != 1:
    print(f"ERROR: expected 1 occurrence, found {count}, aborting")
else:
    content = content.replace(old, new)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Replacement done")
