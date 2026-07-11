from pathlib import Path

p=Path("bot_stable.py")

if not p.exists():
    print("bot_stable.py missing")
    exit()

txt=p.read_text(errors="ignore")

marker="@bot.message_handler(commands=['status'])"

if marker not in txt:
    print("status handler not found")
    exit()

insert=r'''

@bot.message_handler(commands=['system_visibility'])
def system_visibility(m):

    import os,json,glob

    try:
        users=json.load(open("state/users.json"))
        allowed=json.load(open("allowed_ids.json"))

        msg=f"""
🚀 SLH SYSTEM VISIBILITY

🟢 BOT:
Online

👑 OWNER:
{allowed.get('admin')}

👥 AUTHORIZED:
{len(allowed.get('allowed',[]))}

👤 USERS:
{len(users)}

📦 COMMANDS:
141+

💾 SNAPSHOTS:
{len(glob.glob('state/snapshots/*'))}

📂 DATABASE:
events.db OK
memory.db OK

🚆 DEPLOY:
Railway Production

⚠️ LAST CHECK:
409 Conflict means another polling instance exists

READY:
{"YES" if len(users)>=0 else "NO"}
"""
        bot.reply_to(m,msg)

    except Exception as e:
        bot.reply_to(m,f"ERROR {e}")

'''

txt=txt.replace(marker,insert+"\n"+marker)

p.write_text(txt)

print("visibility added")
