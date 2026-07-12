from pathlib import Path

p = Path("bot_stable.py")
s = p.read_text()

marker = "@bot.message_handler(commands=['system_visibility'])"

if "@bot.message_handler(commands=['sync'])" in s:
    print("SYNC already exists")
    exit(0)

insert = r'''

@bot.message_handler(commands=['sync'])
def sync_command(m):
    import os
    import subprocess
    import json
    from datetime import datetime

    try:
        uid = str(m.from_user.id)

        if uid != str(SUPER_ADMIN):
            bot.reply_to(m, "❌ Admin only")
            return

        try:
            commit = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                text=True
            ).strip()
        except:
            commit = "unknown"

        try:
            db = load_db()
            users = len(db.get("users", {}))
            agents = len(db.get("agents", {}))
            tasks = len(db.get("tasks", {}))
            memory = len(db.get("memory", {}))
        except:
            users = agents = tasks = memory = "?"

        msg = f"""
🔄 SLH SYNC REPORT

🕒 Time:
{datetime.now().isoformat()}

🟢 Bot:
ONLINE

📦 Git:
{commit}

👥 Users:
{users}

🤖 Agents:
{agents}

📋 Tasks:
{tasks}

🧠 Memory:
{memory}

📁 Runtime:
{os.getcwd()}

✅ System snapshot synced
"""

        bot.reply_to(m, msg)

    except Exception as e:
        bot.reply_to(m, f"❌ SYNC ERROR\n{e}")

'''

s = s.replace(marker, insert + "\n" + marker)

p.write_text(s)

print("SYNC PATCH ADDED")
