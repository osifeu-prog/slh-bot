import json

def register(bot, context=None):
    @bot.message_handler(commands=['cleanup'])
    def cleanup(m):
        try:
            with open('state/db.json', encoding='utf-8') as f:
                d = json.load(f)

            agents = d.get('agents', {})
            tasks = d.get('tasks', {})

            active = [
                v.get('name', k)
                for k, v in agents.items()
                if v.get('state') == 'active'
            ]
            idle = [
                v.get('name', k)
                for k, v in agents.items()
                if v.get('state') != 'active'
            ]

            open_tasks = [
                v.get('title', k)
                for k, v in tasks.items()
                if v.get('status') in ('open', 'in_progress')
            ]
            archive = [
                v.get('title', k)
                for k, v in tasks.items()
                if v.get('status') not in ('open', 'in_progress')
            ]

            lines = []
            lines.append('🧹 SLH Cleanup Center')
            lines.append('')
            lines.append('🤖 Active agents: ' + str(len(active)))
            lines.extend(active)
            lines.append('')
            lines.append('📦 Idle candidates: ' + str(len(idle)))
            lines.extend(idle)
            lines.append('')
            lines.append('📋 Active tasks: ' + str(len(open_tasks)))
            lines.extend(open_tasks)
            lines.append('')
            lines.append('🗄 Archive candidates: ' + str(len(archive)))
            lines.extend(archive)
            lines.append('')
            lines.append('Preview only - no changes made.')

            bot.reply_to(m, '\n'.join(lines))

        except Exception as e:
            bot.reply_to(m, 'Cleanup error: ' + str(e))

    print('cleanup handler loaded')
