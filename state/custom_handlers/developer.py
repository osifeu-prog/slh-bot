import json, os, time

DEV_FILE = os.path.join(os.path.dirname(file), '..', 'developers.json')
USERS_FILE = os.path.join(os.path.dirname(file), '..', 'users.json')

def get_owner_id():
    if not os.path.exists(USERS_FILE):
        return None
    with open(USERS_FILE) as f:
        users = json.load(f)
    for uid, data in users.items():
        if data.get('role') == 'OWNER':
            return uid
    return None

def is_owner(uid):
    return str(uid) == get_owner_id()

def load_devs():
    if not os.path.exists(DEV_FILE):
        return {}
    with open(DEV_FILE) as f:
        return json.load(f)

def save_devs(devs):
    with open(DEV_FILE, 'w') as f:
        json.dump(devs, f, indent=2)

def register(bot):
    @bot.message_handler(commands=['developer_join'])
    def dev_join(m):
        uid = str(m.chat.id)
        devs = load_devs()
        if uid in devs:
            bot.reply_to(m, 'Already registered as developer')
            return
        devs[uid] = {
            'name': m.from_user.first_name or 'Dev',
            'role': 'CONTRIBUTOR',
            'joined': time.time(),
            'reputation': 0,
            'wallet': None
        }
        save_devs(devs)
        bot.reply_to(m, '✅ Welcome, developer! Role: CONTRIBUTOR')

    @bot.message_handler(commands=['developer_list'])
    def dev_list(m):
        devs = load_devs()
        if not devs:
            bot.reply_to(m, 'No developers registered yet')
            return
        lines = ['🧑‍💻 SLH Developers:']
        for uid, d in devs.items():
            lines.append(f"• {d['name']} [{d['role']}] – ⭐️ {d['reputation']}")
        bot.reply_to(m, '\n'.join(lines))

    @bot.message_handler(commands=['developer_promote'])
    def dev_promote(m):
        if not is_owner(m.chat.id):
            bot.reply_to(m, '⛔️ OWNER only')
            return
        parts = m.text.split()
        if len(parts) < 3:
            bot.reply_to(m, 'Usage: /developer_promote <user_id> <role>')
            return
        target_uid, new_role = parts[1], parts[2].upper()
        devs = load_devs()
        if target_uid not in devs:
            bot.reply_to(m, 'Developer not found')
            return
        devs[target_uid]['role'] = new_role
        save_devs(devs)
        bot.reply_to(m, f'✅ {devs[target_uid]["name"]} promoted to {new_role}')
