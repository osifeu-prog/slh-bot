import json, time
from core.event_bus import EventBus

def register(bot):
    @bot.message_handler(commands=['verify_agents'])
    def verify_agents(m):
        if EventBus._instance is None:
            bus = EventBus(workers=2)
            bus.start()
            from state.custom_handlers.ai_event_handler import register as ra; ra()
            from state.custom_handlers.task_listener import register as rt; rt()
        with open('state/agents.json') as f:
            agents = json.load(f)
        count = 0
        for name, data in agents.items():
            if data.get('role') == 'ai_assistant':
                EventBus.publish('agent_task', {
                    'agent': name,
                    'task': 'VERIFY: אשור שאין לך מידע קודם על הפרויקט, או דווח מה ידוע לך'
                })
                count += 1
        bot.reply_to(m, f'📨 Verification tasks sent to {count} AI agents')

    @bot.message_handler(commands=['verify_status'])
    def verify_status(m):
        with open('state/agents.json') as f:
            agents = json.load(f)
        reply = '📊 Verification status:\n'
        for name, data in agents.items():
            if data.get('role') == 'ai_assistant':
                inbox = data.get('inbox', [])
                verified = any('VERIFIED' in msg.get('message','') for msg in inbox)
                reply += f'• {name}: {"✅ Verified" if verified else "⏳ Pending"}\n'
        bot.reply_to(m, reply)

    @bot.message_handler(commands=['delegate'])
    def delegate(m):
        parts = m.text.split()
        if len(parts) < 3:
            bot.reply_to(m, 'Usage: /delegate <from_agent> <to_agent>')
            return
        from_agent, to_agent = parts[1], parts[2]
        with open('state/agents.json') as f:
            agents = json.load(f)
        if from_agent not in agents or to_agent not in agents:
            bot.reply_to(m, 'One of the agents not found.')
            return
        # Transfer permissions
        perms = agents[from_agent].get('permissions', [])
        agents[to_agent]['permissions'] = list(set(agents[to_agent].get('permissions', []) + perms))
        with open('state/agents.json', 'w') as f:
            json.dump(agents, f, indent=2, ensure_ascii=False)
        EventBus.publish('authority_delegated', {'from': from_agent, 'to': to_agent, 'permissions': perms})
        bot.reply_to(m, f'🔑 Permissions {perms} delegated from {from_agent} to {to_agent}')

    @bot.message_handler(commands=['confirm_verification'])
    def confirm_verification(m):
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, 'Usage: /confirm_verification <agent_name>')
            return
        agent_name = parts[1]
        with open('state/agents.json') as f:
            agents = json.load(f)
        if agent_name not in agents:
            bot.reply_to(m, 'Agent not found.')
            return
        # Add VERIFIED message to inbox
        agents[agent_name].setdefault('inbox', []).append({
            'time': time.time(),
            'message': 'VERIFIED: No prior project information'
        })
        with open('state/agents.json', 'w') as f:
            json.dump(agents, f, indent=2, ensure_ascii=False)
        bot.reply_to(m, f'✅ {agent_name} marked as verified')
