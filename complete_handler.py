from internal_agent import complete_task as agent_complete

def init(bot):
    @bot.message_handler(commands=['complete'])
    def complete(m):
        uid = str(m.chat.id)
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /complete <task_id>")
            return
        task_id = parts[1]
        res = agent_complete(uid, task_id)
        bot.reply_to(m, res)
