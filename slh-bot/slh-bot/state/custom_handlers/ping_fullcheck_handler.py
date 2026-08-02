import json, random, time
import state_manager
from core.event_bus import EventBus

def register(bot):
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
        agents = state_manager.get_agents()
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
