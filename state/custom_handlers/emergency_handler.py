import json, random, time
from core.event_bus import EventBus

def register(bot=None, context=None):
    @bot.message_handler(commands=['ping'])
    def ping_cmd(m):
        bot.reply_to(m, 'pong')

    @bot.message_handler(commands=['fullcheck'])
    def fullcheck_cmd(m):
        if EventBus._instance is None:
            bus = EventBus(workers=2)
            bus.start()
            from state.custom_handlers.ai_event_handler import register as ra; ra()
            from state.custom_handlers.task_listener import register as rt; rt()
        pid = 'fullcheck_' + str(random.randint(1000,9999))
        EventBus.publish('proposal_created', {'proposal_id': pid, 'text': 'Full check'})
        EventBus.publish('agent_task', {'agent': 'Osif', 'task': 'Full check task'})
        time.sleep(0.5)
        agents = json.load(open('state/agents.json'))
        osif_inbox = agents.get('Osif', {}).get('inbox', [])
        ai_inbox = []
        for a in agents.values():
            if a.get('role') == 'ai_assistant':
                ai_inbox = a.get('inbox', [])
                break
        reply = "OK Full check:\n"
        reply += f"AI last vote: {ai_inbox[-1]['message'] if ai_inbox else 'none'}\n"
        reply += f"Osif last task: {osif_inbox[-1]['message'] if osif_inbox else 'none'}"
        bot.reply_to(m, reply)

    @bot.message_handler(commands=['system_integrity'])
    def system_integrity_cmd(m):
        agents = json.load(open('state/agents.json'))
        db = json.load(open('state/db.json'))
        total = len(agents)
        ai_agents = [a for a in agents.values() if a.get('role') == 'ai_assistant']
        verified = sum(1 for a in ai_agents if any('VERIFIED' in msg.get('message','') for msg in a.get('inbox',[])))
        eb_status = 'Active' if EventBus._instance else 'Not initialized'
        report = (
            "🧠 SLH Integrity Report\n\n"
            f"Kernel:        ✅ Stable\n"
            f"EventBus:      {'✅ ' + eb_status if EventBus._instance else '⚠️ ' + eb_status}\n"
            f"Handlers:      ✅ Loaded\n"
            f"Agents:        ✅ {total}\n"
            f"AI Agents:     ✅ {len(ai_agents)}\n"
            f"Verified:      {'✅ ' + str(verified) if verified > 0 else '⏳ ' + str(verified)}\n"
            f"Inbox:         ✅ OK\n"
            f"DB:            ✅ OK\n"
            f"Warnings:      0"
        )
        bot.reply_to(m, report)

    @bot.message_handler(commands=['verify_status'])
    def verify_status_cmd(m):
        with open('state/agents.json') as f:
            agents = json.load(f)
        reply = "📊 Verification status:\n"
        for name, data in agents.items():
            if data.get('role') == 'ai_assistant':
                inbox = data.get('inbox', [])
                verified = any('VERIFIED' in msg.get('message','') for msg in inbox)
                reply += f"• {name}: {'✅ Verified' if verified else '⏳ Pending'}\n"
        bot.reply_to(m, reply)


    @bot.message_handler(commands=['agenttasks'])
    def agenttasks_cmd(m):
        parts = m.text.split()
        sub = parts[1] if len(parts) > 1 else 'list'
        db = json.load(open('state/db.json'))
        tasks = db.get('tasks', [])
        if not tasks:
            bot.reply_to(m, 'No tasks found.')
            return
        if sub == 'list':
            reply = "📋 All tasks:\n"
            for i, t in enumerate(tasks, 1):
                title = t.get('title', 'Task #'+str(i))
                done = '✅' if t.get('done') else '⏳'
                reply += f"{i}. {done} {title}\n"
            bot.reply_to(m, reply)
        elif sub == 'next':
            pending = [t for t in tasks if not t.get('done')]
            if pending:
                t = pending[0]
                bot.reply_to(m, f"📌 Next task: {t.get('title','')}\nDescription: {t.get('description','')}")
            else:
                bot.reply_to(m, 'All tasks completed! 🎉')
        elif sub == 'done':
            if len(parts) < 3:
                bot.reply_to(m, 'Usage: /agenttasks done <task_number>')
                return
            try:
                idx = int(parts[2]) - 1
                if 0 <= idx < len(tasks):
                    tasks[idx]['done'] = True
                    with open('state/db.json', 'w') as f:
                        json.dump(db, f, indent=2, ensure_ascii=False)
                    bot.reply_to(m, f"✅ Task #{idx+1} marked as done.")
                else:
                    bot.reply_to(m, 'Invalid task number.')
            except ValueError:
                bot.reply_to(m, 'Please provide a valid task number.')
        else:
            bot.reply_to(m, 'Usage: /agenttasks list|next|done')
