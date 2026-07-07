def register(bot, context):

    state_manager = context["state_manager"]
    agents_dict = context["agents_dict"]
    agent_store = context["agent_store"]
    is_admin = context["is_admin"]

    @bot.message_handler(commands=['agent_create'])
    def agent_create(m):
        if not is_admin(m):
            return

        parts = m.text.split()

        if len(parts) < 2:
            bot.send_message(m.chat.id, "Usage: /agent_create <name>")
            return

        name = parts[1]

        agents = state_manager.get_agents()

        if name in agents:
            bot.send_message(m.chat.id, "❌ Agent already exists")
            return

        agents[name] = {
            "name": name,
            "inbox": [],
            "outbox": [],
            "state": "idle",
            "role": "agent"
        }

        state_manager.set_agents(agents)

        bot.send_message(
            m.chat.id,
            f"✅ Agent created: {name}"
        )


    @bot.message_handler(commands=['agents'])
    def agents_list(m):

        if not agents_dict:
            bot.send_message(m.chat.id, "No agents yet")
            return

        lines = [
            f"{v.get('name','?')} [{v.get('state','idle')}] – {v.get('role','?')}"
            for k,v in agents_dict.items()
        ]

        bot.send_message(
            m.chat.id,
            "🤖 Agents:\n" + "\n".join(lines)
        )


    @bot.message_handler(commands=['agent_debug'])
    def agent_debug(m):

        if not is_admin(m):
            return

        bot.send_message(
            m.chat.id,
            f"Agents in memory: {len(agents_dict)}"
        )


    @bot.message_handler(commands=['agent_test'])
    def agent_test(m):

        if not is_admin(m):
            return

        agent_store.create("test_agent")

        bot.send_message(
            m.chat.id,
            f"Test agent created. Total agents: {len(agents_dict)}"
        )


    print("🤖 Agents handler loaded")
