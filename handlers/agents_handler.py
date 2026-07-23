
@bot.message_handler(commands=['agent_delete'])
def agent_delete_cmd(m):
    parts = m.text.split()
    if len(parts) < 2:
        bot.reply_to(m, "Usage: /agent_delete <name>")
        return
    name = parts[1]
    import json, os
    db_path = "state/db.json"
    with open(db_path, 'r', encoding='utf-8') as f:
        db = json.load(f)
    agents = db.get("agents", {})
    if name not in agents:
        bot.reply_to(m, f"? Agent '{name}' not found")
        return
    # Delete
    del agents[name]
    db["agents"] = agents
    with open(db_path, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    # Sync with agents.json
    with open("state/agents.json", 'w', encoding='utf-8') as f:
        json.dump(agents, f, indent=2, ensure_ascii=False)
    bot.reply_to(m, f"? Agent '{name}' deleted successfully")

def register(bot, context):
    import state_manager
    is_admin = context["is_admin"]

    @bot.message_handler(commands=['agent_create'])
    def agent_create(m):
        if not is_admin(m): return
        parts = m.text.split()
        if len(parts) < 2:
            bot.send_message(m.chat.id, "Usage: /agent_create <name>")
            return
        name = parts[1]
        agents = state_manager.get_agents()
        if name in agents:
            bot.send_message(m.chat.id, "❌ Agent already exists")
            return
        agents[name] = {"name": name, "inbox": [], "outbox": [], "state": "idle", "role": "agent"}
        state_manager.set_agents(agents)
        bot.send_message(m.chat.id, f"✅ Agent created: {name}")

    @bot.message_handler(commands=['agents'])
    def agents_list(m):
        agents = state_manager.get_agents()
        if not agents:
            bot.send_message(m.chat.id, "No agents yet")
            return
        lines = [f"{v.get('name')} [{v.get('state','idle')}] – {v.get('role','?')}" for v in agents.values()]
        bot.send_message(m.chat.id, "🤖 Agents:\n" + "\n".join(lines))

    @bot.message_handler(commands=['agentstate'])
    def agentstate_cmd(m):
        parts = m.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(m, 'Usage: /agentstate <name> <state>')
            return
        name, state = parts[1], parts[2]
        agents = state_manager.get_agents()
        if name not in agents:
            bot.reply_to(m, '❌ Agent not found')
            return
        agents[name]["state"] = state
        state_manager.set_agents(agents)
        bot.reply_to(m, f"✅ {name} → {state}")

    @bot.message_handler(commands=['sendagent'])
    def sendagent_cmd(m):
        parts = m.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(m, 'Usage: /sendagent <name> <msg>')
            return
        name, msg = parts[1], parts[2]
        agents = state_manager.get_agents()
        if name not in agents:
            bot.reply_to(m, '❌ Agent not found')
            return
        agents[name].setdefault("inbox", []).append(msg)
        state_manager.set_agents(agents)
        bot.reply_to(m, f"✅ Sent to {name}")

    @bot.message_handler(commands=['inbox'])
    def inbox_cmd(m):
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, 'Usage: /inbox <name>')
            return
        name = parts[1]
        agents = state_manager.get_agents()
        if name not in agents:
            bot.reply_to(m, '❌ Agent not found')
            return
        inbox = agents[name].get("inbox", [])
        bot.reply_to(m, f"📬 {name} Inbox:\n" + ("\n".join(f"• {msg}" for msg in inbox) if inbox else "Empty"))


    @bot.message_handler(commands=['agent_audit'])
    def agent_audit_cmd(m):
        if not is_admin(m):
            return

        agents = state_manager.get_agents()

        if not agents:
            bot.reply_to(m, "🤖 No agents")
            return

        lines = ["🤖 AGENT AUDIT"]

        for name, agent in agents.items():
            inbox = len(agent.get("inbox", []))
            history = len(agent.get("history", []))
            state = agent.get("state", "unknown")

            lines.append(
                f"\n{name}\n"
                f"STATE: {state}\n"
                f"INBOX: {inbox}\n"
                f"HISTORY: {history}"
            )

        bot.reply_to(m, "\n".join(lines))

    print("🤖 Agents handler loaded (full)")
