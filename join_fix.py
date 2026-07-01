import os

target_file = "learn_handlers.py"
with open(target_file, "r") as f:
    content = f.read()

if "@bot.message_handler(commands=['join'])" in content:
    print("/join already exists")
    exit(0)

new_handler = """
def join(m):
    uid = str(m.from_user.id)
    name = m.from_user.first_name or "ללא שם"
    db = json.load(open("db.json"))
    if "students" not in db:
        db["students"] = {}
    if uid in db["students"]:
        bot.reply_to(m, "אתה כבר רשום!")
        return
    db["students"][uid] = {
        "name": name,
        "referral_count": 0,
        "courses": {}
    }
    json.dump(db, open("db.json","w"), indent=2, ensure_ascii=False)
    bot.reply_to(m, f"ברוך הבא, {name}! נרשמת בהצלחה.\\nשלח /start_course להתחיל.")
"""

# Find the line where register(bot) is defined and add the handler
lines = content.split("\n")
insert_idx = None
for i, line in enumerate(lines):
    if "def register(bot):" in line:
        insert_idx = i
        break
if insert_idx is None:
    print("register function not found")
    exit(1)

# Add the handler after the register function, inside it: we need to add a message_handler decorator
handler_code = f"""    @bot.message_handler(commands=['join'])
    {new_handler.strip()}"""
# Insert after the line that starts the function, before any existing handlers? Actually, just append before the end of the function.
# Simple: insert before the last line of the file, assuming the function ends at EOF.
lines.insert(-1, handler_code)  # before last line (which is probably empty)
with open(target_file, "w") as f:
    f.write("\n".join(lines))
print("Added /join to learn_handlers.py. Restart bot.")
