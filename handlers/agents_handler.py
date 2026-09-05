from core.agent_registry import (
    list_agents, get_agent, create_agent, update_agent,
    delete_agent, send_message, get_inbox,
)
from core.authority import get_visible_agents, normalize_uid, is_owner


def _check_access(uid, identifier):
    agent_id, agent = get_agent(identifier)
    if agent is None:
        return None, None
    visible = get_visible_agents(uid, {agent_id: agent})
    if agent_id not in visible and not is_owner(uid):
        return None, None
    return agent_id, agent


def register(bot, context):

    @bot.message_handler(commands=["agent_create"])
    def agent_create_cmd(m):
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /agent_create <name>")
            return
        name = parts[1]
        owner_id = normalize_uid(m.from_user.id)
        try:
            agent_id, agent = create_agent(name, owner_id=owner_id)
            bot.reply_to(m, "Agent '" + name + "' created\nID: " + agent_id)
        except ValueError as e:
            bot.reply_to(m, "Error: " + str(e))
        except Exception as e:
            bot.reply_to(m, "Agent creation failed: " + type(e).__name__)

    @bot.message_handler(commands=["agents"])
    def agents_list_cmd(m):
        uid = normalize_uid(m.from_user.id)
        all_agents = list_agents()
        agents = get_visible_agents(uid, all_agents)
        if not agents:
            bot.reply_to(m, "No agents found")
            return
        lines = []
        for aid, d in agents.items():
            lines.append(aid + " - " + str(d.get("name", aid)) + " [" + str(d.get("state", "unknown")) + "] - " + str(d.get("role", "agent")))
        bot.reply_to(m, "Agents:\n" + "\n".join(lines))

    @bot.message_handler(commands=["agentstate"])
    def agentstate_cmd(m):
        parts = m.text.split()
        if len(parts) < 3:
            bot.reply_to(m, "Usage: /agentstate <name> <state>")
            return
        uid = normalize_uid(m.from_user.id)
        agent_id, agent = _check_access(uid, parts[1])
        if agent is None:
            bot.reply_to(m, "Agent not found or access denied")
            return
        try:
            agent_id, agent = update_agent(agent_id, state=parts[2])
            bot.reply_to(m, str(agent.get("name", agent_id)) + " -> " + parts[2])
        except Exception as e:
            bot.reply_to(m, "State update failed: " + type(e).__name__)

    @bot.message_handler(commands=["sendagent"])
    def sendagent_cmd(m):
        parts = m.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(m, "Usage: /sendagent <name> <msg>")
            return
        uid = normalize_uid(m.from_user.id)
        agent_id, agent = _check_access(uid, parts[1])
        if agent is None:
            bot.reply_to(m, "Agent not found or access denied")
            return
        try:
            send_message(agent_id, parts[2])
            bot.reply_to(m, "Sent to agent " + agent_id)
        except Exception as e:
            bot.reply_to(m, "Message delivery failed: " + type(e).__name__)

    @bot.message_handler(commands=["inbox"])
    def inbox_cmd(m):
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /inbox <name>")
            return
        uid = normalize_uid(m.from_user.id)
        agent_id, agent = _check_access(uid, parts[1])
        if agent is None:
            bot.reply_to(m, "Agent not found or access denied")
            return
        inbox = get_inbox(agent_id)
        display_name = agent.get("name", agent_id)
        if not inbox:
            bot.reply_to(m, "Inbox (" + str(display_name) + "): empty")
            return
        lines = ["Inbox (" + str(display_name) + "):"]
        for message in inbox:
            lines.append("- " + str(message))
        bot.reply_to(m, "\n".join(lines))

    @bot.message_handler(commands=["agent_delete"])
    def agent_delete_cmd(m):
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /agent_delete <name>")
            return
        uid = normalize_uid(m.from_user.id)
        agent_id, agent = _check_access(uid, parts[1])
        if agent is None:
            bot.reply_to(m, "Agent not found or access denied")
            return
        try:
            _, deleted = delete_agent(agent_id)
            bot.reply_to(m, "Agent '" + str(deleted.get("name", agent_id)) + "' deleted successfully")
        except Exception as e:
            bot.reply_to(m, "Agent deletion failed: " + type(e).__name__)