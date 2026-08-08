import os, requests

def register(bot):
    @bot.message_handler(commands=['deploy'])
    def deploy_cmd(msg):
        if str(msg.from_user.id) != os.getenv('ADMIN_ID', '8789977826'):
            bot.reply_to(msg, '⛔️ Admin only')
            return
        token = os.getenv('RAILWAY_API_TOKEN')
        if not token:
            bot.reply_to(msg, '❌ RAILWAY_API_TOKEN not set')
            return
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        project_id = 'fd30fefb-3d35-48a5-a7cb-e05337e812c4'
        service_id = '13d97581-0199-4f6a-80d1-885c9304ffc5'
        url = f'https://backboard.railway.app/v1/projects/{project_id}/services/{service_id}/deployments'
        r = requests.post(url, headers=headers)
        if r.status_code == 201:
            bot.reply_to(msg, '🚀 Redeploy triggered! Check logs.')
        else:
            bot.reply_to(msg, f'❌ Failed ({r.status_code}): {r.text[:200]}')
