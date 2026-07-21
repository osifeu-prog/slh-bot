import os

# הזרקת /me, /askdebug, /join לתוך bot_stable.py
with open('/app/bot_stable.py', 'r') as f:
    content = f.read()

injection = '''
# Injected handlers for /me and /askdebug
@bot.message_handler(commands=['me'])
def me_cmd(m):
    uid = str(m.from_user.id)
    try:
        import json
        with open('state/db.json') as f:
            users = json.load(f).get('users', {})
        user = users.get(uid, {})
        if not user:
            bot.reply_to(m, "❌ לא נמצאה הרשמה. השתמש ב־/join")
        else:
            txt = f"👤 *פרופיל SLH*\\n• ID: {uid}\\n• שם: {user.get('name','לא ידוע')}\\n• תפקיד: {user.get('role','user')}\\n• הצטרף: {user.get('joined','לא ידוע')}"
            bot.reply_to(m, txt, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(m, f"שגיאה: {e}")

@bot.message_handler(commands=['askdebug'])
def askdebug_cmd(m):
    try:
        text = m.text.split(' ', 1)[1]
        from core.ask_debug import debug_ask
        import json
        bot.reply_to(m, '<pre>' + json.dumps(debug_ask(text), indent=2, ensure_ascii=False) + '</pre>', parse_mode='HTML')
    except:
        bot.reply_to(m, 'Usage: /askdebug <question>')

from handlers.join_handler import register as reg_join; reg_join(bot)
'''

if '# Injected handlers for /me and /askdebug' not in content:
    import re
    match = re.search(r'^bot\s*=\s*.*?TeleBot\(.*?\)', content, re.MULTILINE)
    if match:
        pos = match.end()
        content = content[:pos] + injection + content[pos:]

with open('/app/bot_stable.py', 'w') as f:
    f.write(content)

# ASK Router patch ב־advanced_ask_handler.py
with open('/app/advanced_ask_handler.py', 'r') as f:
    ask_content = f.read()

router_patch = '''    # ASK Router integration
    from core.ask_router import route as ask_route
    local_answer = ask_route(question)
    if local_answer:
        bot.reply_to(m, local_answer)
        return
'''

if '# ASK Router integration' not in ask_content:
    old = '    context = get_bot_context'
    if old in ask_content:
        ask_content = ask_content.replace(old, router_patch + old, 1)

with open('/app/advanced_ask_handler.py', 'w') as f:
    f.write(ask_content)

print('Patches applied.')
