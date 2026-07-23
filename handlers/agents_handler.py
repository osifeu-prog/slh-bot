import json
import os

def register(bot, context):
    @bot.message_handler(commands=['agent_create'])
    def agent_create_cmd(m):
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /agent_create <name>")
            return
        name = parts[1]
        db_path = "state/db.json"
        with open(db_path, 'r', encoding='utf-8') as f:
            db = json.load(f)
        agents = db.get("agents", {})
        if name in agents:
            bot.reply_to(m, f"❌ Agent '{name}' already exists")
            return
        agents[name] = {"name": name, "state": "idle", "role": "agent", "inbox": [], "outbox": []}
        db["agents"] = agents
        with open(db_path, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        with open("state/agents.json", 'w', encoding='utf-8') as f:
            json.dump(agents, f, indent=2, ensure_ascii=False)
        bot.reply_to(m, f"✅ Agent '{name}' created")

    @bot.message_handler(commands=['agents'])
    def agents_list_cmd(m):
        db_path = "state/db.json"
        with open(db_path, 'r', encoding='utf-8') as f:
            db = json.load(f)
        agents = db.get("agents", {})
        if not agents:
            bot.reply_to(m, "🤖 No agents found")
            return
        lines = []
        for name, data in agents.items():
            state = data.get('state', 'unknown')
            role = data.get('role', 'agent')
            lines.append(f"{name} [{state}] – {role}")
        bot.reply_to(m, "🤖 Agents:\n" + "\n".join(lines))

    @bot.message_handler(commands=['agentstate'])
    def agentstate_cmd(m):
        parts = m.text.split()
        if len(parts) < 3:
            bot.reply_to(m, "Usage: /agentstate <name> <state>")
            return
        name = parts[1]
        state = parts[2]
        db_path = "state/db.json"
        with open(db_path, 'r', encoding='utf-8') as f:
            db = json.load(f)
        agents = db.get("agents", {})
        if name not in agents:
            bot.reply_to(m, f"❌ Agent '{name}' not found")
            return
        agents[name]['state'] = state
        db["agents"] = agents
        with open(db_path, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        with open("state/agents.json", 'w', encoding='utf-8') as f:
            json.dump(agents, f, indent=2, ensure_ascii=False)
        bot.reply_to(m, f"✅ {name} → {state}")

    @bot.message_handler(commands=['sendagent'])
    def sendagent_cmd(m):
        parts = m.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(m, "Usage: /sendagent <name> <msg>")
            return
        name = parts[1]
        msg = parts[2]
        db_path = "state/db.json"
        with open(db_path, 'r', encoding='utf-8') as f:
            db = json.load(f)
        agents = db.get("agents", {})
        if name not in agents:
            bot.reply_to(m, f"❌ Agent '{name}' not found")
            return
        agents[name].setdefault("inbox", []).append(msg)
        db["agents"] = agents
        with open(db_path, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        with open("state/agents.json", 'w', encoding='utf-8') as f:
            json.dump(agents, f, indent=2, ensure_ascii=False)
        bot.reply_to(m, f"✅ Sent to {name}")

    @bot.message_handler(commands=['inbox'])
    def inbox_cmd(m):
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /inbox <name>")
            return
        name = parts[1]
        db_path = "state/db.json"
        with open(db_path, 'r', encoding='utf-8') as f:
            db = json.load(f)
        agents = db.get("agents", {})
        if name not in agents:
            bot.reply_to(m, f"❌ Agent '{name}' not found")
            return
        inbox = agents[name].get("inbox", [])
        if not inbox:
            bot.reply_to(m, f"📬 {name} Inbox: (empty)")
            return
        lines = [f"📬 {name} Inbox:"]
        for i, msg in enumerate(inbox, 1):
            lines.append(f"• {msg}")
        bot.reply_to(m, "\n".join(lines))

    @bot.message_handler(commands=['agent_delete'])
    def agent_delete_cmd(m):
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /agent_delete <name>")
            return
        name = parts[1]
        db_path = "state/db.json"
        with open(db_path, 'r', encoding='utf-8') as f:
            db = json.load(f)
        agents = db.get("agents", {})
        if name not in agents:
            bot.reply_to(m, f"❌ Agent '{name}' not found")
            return
        del agents[name]
        db["agents"] = agents
        with open(db_path, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        with open("state/agents.json", 'w', encoding='utf-8') as f:
            json.dump(agents, f, indent=2, ensure_ascii=False)
        bot.reply_to(m, f"✅ Agent '{name}' deleted successfully")