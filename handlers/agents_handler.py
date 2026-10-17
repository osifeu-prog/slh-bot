from core.agent_registry import (
    list_agents, get_agent, create_agent, update_agent,
    delete_agent, send_message, get_inbox, get_outbox,
)
from core.authority import get_visible_agents, normalize_uid, is_owner

# Only exact commands are interpreted as worker operations. Free-form text is
# always sent through the assistant fallback chain, never as a command string.
_READ_ONLY_AGENT_COMMANDS = {"whoami", "status", "uptime"}
_OWNER_AGENT_COMMANDS = {"dbsize", "sysinfo", "logs", "errors"}


def _agent_task(uid, text):
    uid = normalize_uid(uid)
    raw = str(text or "").strip()
    lowered = raw.casefold()

    # Preserve the documented explicit form: /sendagent <agent> ask <question>.
    # The prefix is syntax, not part of the natural-language prompt.
    if lowered.startswith("ask "):
        raw = raw.split(None, 1)[1].strip()
        lowered = raw.casefold()

    if is_owner(uid):
        if lowered in (_READ_ONLY_AGENT_COMMANDS | _OWNER_AGENT_COMMANDS):
            return {"command": lowered, "uid": uid}
        parts = raw.split(maxsplit=1)
        if len(parts) == 2 and parts[0].casefold() == "complete":
            return {"command": "complete", "task_id": parts[1].strip(), "uid": uid}

    # Ordinary users' text such as "whoami" is a question, never a host action.
    return {"command": "ask", "prompt": raw, "uid": uid}


def _agent_sort_key(item):
    created = str(item[1].get("created", ""))
    try:
        numeric_id = int(item[0])
    except (TypeError, ValueError):
        numeric_id = 10**18
    return (created, numeric_id, str(item[0]))


def format_agent_list(uid, all_agents):
    """Return per-user display numbering without changing canonical agent IDs."""
    uid = normalize_uid(uid)
    visible = get_visible_agents(uid, all_agents)

    # /agents is a personal view. OWNER sees their own agents here; privileged
    # Control Plane tools continue to expose canonical IDs separately.
    if is_owner(uid):
        visible = {
            aid: agent
            for aid, agent in all_agents.items()
            if str(agent.get("owner_id", "")) == uid
        }

    ordered = sorted(visible.items(), key=_agent_sort_key)
    mapping = {}
    lines = ["הסוכנים שלך:"]
    for index, (agent_id, data) in enumerate(ordered, start=1):
        mapping[str(index)] = str(agent_id)
        lines.append(
            f"{index}. {data.get('name', agent_id)} "
            f"[{data.get('state', 'unknown')}] - {data.get('role', 'agent')}"
        )
    return "\n".join(lines), mapping


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
        text, _mapping = format_agent_list(uid, all_agents)
        if text == "הסוכנים שלך:":
            bot.reply_to(m, "אין לך סוכנים רשומים")
            return
        bot.reply_to(m, text)

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
            task = _agent_task(uid, parts[2])
            chat_id = str(getattr(getattr(m, "chat", None), "id", "") or "").strip()
            message_id = str(getattr(m, "message_id", "") or "").strip()
            if chat_id and message_id:
                task["request_id"] = f"telegram:{uid}:{chat_id}:{message_id}"
                task["source"] = f"telegram:{uid}"
            send_message(agent_id, task)
            bot.reply_to(
                m,
                "📨 המשימה נשלחה לתור הסוכן. "
                "לצפייה בתוצאה: /agent_outbox " + str(agent_id)
                + " (alias: /agentoutbox " + str(agent.get("name", agent_id)) + ")",
            )
        except Exception as e:
            bot.reply_to(m, "Agent task submission failed: " + type(e).__name__)

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
        _, inbox = get_inbox(agent_id)
        display_name = agent.get("name", agent_id)
        if not inbox:
            bot.reply_to(m, "Inbox (" + str(display_name) + "): empty")
            return
        lines = ["Inbox (" + str(display_name) + "):"]
        for message in inbox:
            if isinstance(message, dict):
                command = str(message.get("command") or "task")
                detail = str(message.get("prompt") or message.get("task_id") or "").strip()
                line = "- " + command + ((": " + detail[:220]) if detail else "")
                lines.append(line + " [command: " + command + "]")
            else:
                lines.append("- " + str(message)[:250])
        bot.reply_to(m, "\n".join(lines))

    @bot.message_handler(commands=["agentoutbox", "agent_outbox"])
    def agentoutbox_cmd(m):
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /agentoutbox <name>")
            return
        uid = normalize_uid(m.from_user.id)
        agent_id, agent = _check_access(uid, parts[1])
        if agent is None:
            bot.reply_to(m, "Agent not found or access denied")
            return
        try:
            _, outbox = get_outbox(agent_id, limit=8)
        except Exception as e:
            bot.reply_to(m, "Agent outbox unavailable: " + type(e).__name__)
            return
        if not outbox:
            bot.reply_to(m, "Outbox (" + str(agent.get("name", agent_id)) + "): empty")
            return
        lines = ["Outbox (" + str(agent.get("name", agent_id)) + ") — newest first:"]
        for entry in reversed(outbox):
            lines.append(str(entry)[:900])
        bot.reply_to(m, "\n\n".join(lines)[-3800:])

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
