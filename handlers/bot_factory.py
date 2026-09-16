import os, json, requests
from core.authority import is_owner

def _load():
    try:
        return json.load(open('projects.json'))
    except Exception:
        return {}

def register(bot):
    @bot.message_handler(commands=['projects'])
    def projects_cmd(m):
        if not is_owner(m):
            return
        p = _load()
        if not p:
            bot.reply_to(m, 'no projects')
            return
        lines = ['PROJECTS:']
        for k, v in p.items():
            lines.append(k + ' -> ' + str(v.get('github_repo', '?')))
        bot.reply_to(m, chr(10).join(lines))
print('bot_factory loaded')
