from core.agent_registry import (
    list_agents,
    get_agent,
    create_agent,
    update_agent,
    delete_agent,
    send_message,
    get_inbox,
)


def register(bot, context):

    @bot.message_handler(commands=["agent_create"])
    def agent_create_cmd(m):
        parts = m.text.split()

        if len(parts) < 2:
            bot.reply_to(m, "Usage: /agent_create <name>")
            return

        name = parts[1]

        try:
            agent_id, agent = create_agent(name)

            bot.reply_to(
                m,
                f"✅ Agent '{name}' created\n"
                f"🆔 ID: {agent_id}"
            )

        except ValueError as e:
            bot.reply_to(m, f"❌ {e}")

        except Exception as e:
            bot.reply_to(
                m,
                f"❌ Agent creation failed: {type(e).__name__}"
            )


    @bot.message_handler(commands=["agents"])
    def agents_list_cmd(m):

        agents = list_agents()

        if not agents:
            bot.reply_to(m, "🤖 No agents found")
            return

        lines = []

        for agent_id, data in agents.items():
            name = data.get("name", agent_id)
            state = data.get("state", "unknown")
            role = data.get("role", "agent")

            lines.append(
                f"{agent_id} — {name} [{state}] – {role}"
            )

        bot.reply_to(
            m,
            "🤖 Agents:\n" + "\n".join(lines)
        )


    @bot.message_handler(commands=["agentstate"])
    def agentstate_cmd(m):

        parts = m.text.split()

        if len(parts) < 3:
            bot.reply_to(
                m,
                "Usage: /agentstate <name> <state>"
            )
            return

        identifier = parts[1]
        state = parts[2]

        try:
            agent_id, agent = update_agent(
                identifier,
                state=state
            )

            bot.reply_to(
                m,
                f"✅ {agent.get('name', agent_id)} → {state}"
            )

        except KeyError as e:
            bot.reply_to(m, f"❌ {e}")

        except Exception as e:
            bot.reply_to(
                m,
                f"❌ State update failed: {type(e).__name__}"
            )


    @bot.message_handler(commands=["sendagent"])
    def sendagent_cmd(m):

        parts = m.text.split(maxsplit=2)

        if len(parts) < 3:
            bot.reply_to(
                m,
                "Usage: /sendagent <name> <msg>"
            )
            return

        identifier = parts[1]
        message = parts[2]

        try:
            agent_id = send_message(
                identifier,
                message
            )

            bot.reply_to(
                m,
                f"✅ Sent to agent {agent_id}"
            )

        except KeyError as e:
            bot.reply_to(m, f"❌ {e}")

        except Exception as e:
            bot.reply_to(
                m,
                f"❌ Message delivery failed: {type(e).__name__}"
            )


    @bot.message_handler(commands=["inbox"])
    def inbox_cmd(m):

        parts = m.text.split()

        if len(parts) < 2:
            bot.reply_to(
                m,
                "Usage: /inbox <name>"
            )
            return

        identifier = parts[1]

        try:
            inbox = get_inbox(identifier)

            _, agent = get_agent(identifier)

            display_name = (
                agent.get("name", identifier)
                if agent
                else identifier
            )

            if not inbox:
                bot.reply_to(
                    m,
                    f"📬 {display_name} Inbox: (empty)"
                )
                return

            lines = [
                f"📬 {display_name} Inbox:"
            ]

            for message in inbox:
                lines.append(
                    f"• {message}"
                )

            bot.reply_to(
                m,
                "\n".join(lines)
            )

        except KeyError as e:
            bot.reply_to(m, f"❌ {e}")

        except Exception as e:
            bot.reply_to(
                m,
                f"❌ Inbox read failed: {type(e).__name__}"
            )


    @bot.message_handler(commands=["agent_delete"])
    def agent_delete_cmd(m):

        parts = m.text.split()

        if len(parts) < 2:
            bot.reply_to(
                m,
                "Usage: /agent_delete <name>"
            )
            return

        identifier = parts[1]

        try:
            agent_id, agent = delete_agent(identifier)

            bot.reply_to(
                m,
                f"✅ Agent '{agent.get('name', agent_id)}' "
                f"deleted successfully"
            )

        except KeyError as e:
            bot.reply_to(m, f"❌ {e}")

        except Exception as e:
            bot.reply_to(
                m,
                f"❌ Agent deletion failed: {type(e).__name__}"
            )
