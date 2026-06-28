import os, re

with open("bot.py", "r") as f:
    code = f.read()

# Ensure json import
if "import json" not in code:
    code = code.replace("import os", "import os, json", 1)

# Auth block
auth_block = '''
import json
ALLOWED_FILE = os.path.expanduser("~/slh_clean/allowed_ids.json")
def load_allowed():
    if not os.path.exists(ALLOWED_FILE):
        return {"admin": None, "allowed": []}
    with open(ALLOWED_FILE, "r") as f:
        return json.load(f)

def save_allowed(data):
    with open(ALLOWED_FILE, "w") as f:
        json.dump(data, f)

def is_allowed(chat_id):
    data = load_allowed()
    return chat_id in data["allowed"]

def add_allowed(chat_id):
    data = load_allowed()
    if chat_id not in data["allowed"]:
        data["allowed"].append(chat_id)
        save_allowed(data)
        return True
    return False

def remove_allowed(chat_id):
    data = load_allowed()
    if chat_id == data["admin"]:
        return False
    if chat_id in data["allowed"]:
        data["allowed"].remove(chat_id)
        save_allowed(data)
        return True
    return False

def get_admin():
    return load_allowed()["admin"]
'''

lines = code.split('\n')
last_import = max(i for i, line in enumerate(lines) if line.startswith("import ") or line.startswith("from "))
lines.insert(last_import+1, auth_block)
code = '\n'.join(lines)

# Add auth_filter
auth_filter_def = "\nauth_filter = lambda m: is_allowed(m.chat.id)\n"
lines = code.split('\n')
for i, line in enumerate(lines):
    if "def get_admin():" in line:
        lines.insert(i+2, auth_filter_def)
        break
else:
    lines.append(auth_filter_def)
code = '\n'.join(lines)

# Modify existing handlers
pattern = r'(@bot\.message_handler\(commands=\[.*?\])\)'
replacement = r'\1, func=auth_filter)'
code = re.sub(pattern, replacement, code)

# New handlers (including open /id)
new_handlers = r'''
# --- Open to everyone ---
@bot.message_handler(commands=['id'])
def show_id(m):
    chat = m.chat
    user = m.from_user
    info = []
    info.append(f"Chat ID: {chat.id}")
    info.append(f"Chat type: {chat.type}")
    if chat.type == "private":
        info.append(f"Your user ID: {user.id}")
        if user.username:
            info.append(f"Username: @{user.username}")
    elif chat.type in ["group", "supergroup"]:
        info.append(f"Group title: {chat.title}")
        info.append(f"Your user ID: {user.id}")
        if user.username:
            info.append(f"Your username: @{user.username}")
    bot.reply_to(m, "\n".join(info), parse_mode="Markdown")

# --- Admin only ---
@bot.message_handler(commands=['users'], func=auth_filter)
def list_users(m):
    if m.chat.id != get_admin():
        bot.reply_to(m, "⛔️ Admin only")
        return
    data = load_allowed()
    users = "\n".join([str(uid) for uid in data["allowed"]])
    bot.reply_to(m, f"📋 Allowed users:\n{users}")

@bot.message_handler(commands=['allow'], func=auth_filter)
def allow_user(m):
    if m.chat.id != get_admin():
        bot.reply_to(m, "⛔️ Admin only")
        return
    parts = m.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        bot.reply_to(m, "Usage: /allow <chat_id>")
        return
    uid = int(parts[1])
    if add_allowed(uid):
        bot.reply_to(m, f"✅ User {uid} added to allowed list")
    else:
        bot.reply_to(m, "User already in list")

@bot.message_handler(commands=['revoke'], func=auth_filter)
def revoke_user(m):
    if m.chat.id != get_admin():
        bot.reply_to(m, "⛔️ Admin only")
        return
    parts = m.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        bot.reply_to(m, "Usage: /revoke <chat_id>")
        return
    uid = int(parts[1])
    if remove_allowed(uid):
        bot.reply_to(m, f"❌ User {uid} removed from allowed list")
    else:
        bot.reply_to(m, "User not in list or is admin")
@bot.message_handler(commands=['sync'], func=auth_filter)
def sync(m):
    import subprocess
    cwd = os.path.expanduser("~/slh_clean")
    output = []
    r = subprocess.run(["git", "pull"], cwd=cwd, capture_output=True, text=True)
    output.append(f"Pull: {r.stdout.strip() or 'OK'}")
    subprocess.run(["git", "add", "-A"], cwd=cwd)
    r = subprocess.run(["git", "commit", "-m", f"sync {subprocess.run(['date', '-Iseconds'], capture_output=True, text=True).stdout.strip()}"], cwd=cwd, capture_output=True, text=True)
    if "nothing to commit" in r.stdout + r.stderr:
        output.append("Commit: nothing to commit")
    else:
        output.append("Commit: OK")
    r = subprocess.run(["git", "push"], cwd=cwd, capture_output=True, text=True)
    output.append(f"Push: {r.stdout.strip() or 'OK'}")
    output.append("Railway: auto-deploy triggered (will exit due to SLH_LOCAL)")
    bot.reply_to(m, "\n".join(output))
'''

lines = code.split('\n')
poll_idx = next((i for i, line in enumerate(lines) if 'bot.infinity_polling()' in line), None)
if poll_idx is not None:
    lines.insert(poll_idx, new_handlers)
else:
    lines.append(new_handlers)
code = '\n'.join(lines)

with open("bot.py", "w") as f:
    f.write(code)

# Syntax check
import py_compile
try:
    py_compile.compile("bot.py", doraise=True)
    print("✅ Syntax OK")
except py_compile.PyCompileError as e:
    print("❌ Syntax ERROR:", e)
    exit(1)

import subprocess
subprocess.run(["git", "add", "bot.py", "allowed_ids.json"])
subprocess.run(["git", "commit", "-m", "add auth, /sync, and public /id command"])
print("✅ Changes committed (not pushed)")
