import json
import state_manager

def register(bot, agents_dict):
    @bot.message_handler(commands=['demo'])
    def demo(m):
        parts = m.text.split()
        if len(parts) < 2:
            bot.send_message(m.chat.id, "📋 /demo tasks | agents | guide")
            return
        sub = parts[1].lower()
        if sub == "agents":
            agents = state_manager.get_agents()
            if "helper" not in agents:
                agents["helper"] = {"name": "helper", "inbox": [], "outbox": [], "state": "idle", "role": "assistant"}
            if "tutor" not in agents:
                agents["tutor"] = {"name": "tutor", "inbox": [], "outbox": [], "state": "idle", "role": "teacher"}
            state_manager.set_agents(agents)
            agents_dict.clear()
            agents_dict.update(agents)
            bot.send_message(m.chat.id, "✅ Demo agents created: helper, tutor")
        elif sub == "tasks":
            try:
                with open("state/demo_tasks.json") as f:
                    demo = json.load(f)
                proj = demo.get("demo_project", {})
                msg = f"📋 {proj.get('title','')}\n"
                for t in proj.get("tasks", []):
                    msg += f"  {t['id']}. {t['desc']}\n"
            except Exception as e:
                msg = f"Error: {e}"
            bot.send_message(m.chat.id, msg)
        elif sub == "guide":
            bot.send_message(m.chat.id, "📖 מדריך מהיר:\n1. /agent_create <name>\n2. /sendagent <name> <msg>\n3. /inbox <name>\n4. /agentstate <name> busy\n\nהשתמש ב-/demo tasks למשימות מסודרות.")
        else:
            bot.send_message(m.chat.id, "תת-פקודה לא מוכרת. נסה tasks, agents, guide")
