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
            bot.reply_to(m, 'no projects.json')
            return
        lines = ['PROJECTS:']
        for k, v in p.items():
            lines.append(k + ' -> ' + str(v.get('github_repo','?')))
        bot.reply_to(m, chr(10).join(lines))

    @bot.message_handler(commands=['deploy'])
    def deploy_cmd(m):
        if not is_owner(m):
            return
        token = os.getenv('RAILWAY_API_TOKEN')
        if not token:
            bot.reply_to(m, 'RAILWAY_API_TOKEN not set')
            return
        parts = m.text.split()
        name = parts[1] if len(parts) > 1 else 'slh_main'
        p = _load().get(name)
        if not p:
            bot.reply_to(m, 'project not found: ' + name)
            return
        q = 'mutation(:String!,:String!){serviceInstanceDeploy(serviceId:,environmentId:)}'
        headers = {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'}
        r = requests.post('https://backboard.railway.app/graphql/v2',
                          json={'query': q, 'variables': {'s': p['railway_service_id'], 'e': p['railway_environment_id']}},
                          headers=headers, timeout=20)
        if r.status_code == 200:
            bot.reply_to(m, 'deploy sent: ' + name)
        else:
            bot.reply_to(m, 'failed: ' + str(r.status_code) + ' ' + r.text[:200])
