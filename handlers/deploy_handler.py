import os
import requests

def register(bot):

    @bot.message_handler(commands=['deploy'])
    def deploy_cmd(msg):

        if str(msg.from_user.id) != os.getenv('ADMIN_ID', '8789977826'):
            bot.reply_to(msg, '⛔ Admin only')
            return

        token = os.getenv('RAILWAY_API_TOKEN')

        if not token:
            bot.reply_to(msg, '❌ RAILWAY_API_TOKEN not set')
            return

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        query = """
        mutation {
          serviceInstanceRedeploy(
            serviceId: "13d97581-0199-4f6a-80d1-885c9304ffc5",`n        environmentId: "661caa13-83cb-4197-8825-943bebf96c5a"
          )
        }
        """

        url = "https://backboard.railway.app/graphql/v2"

        r = requests.post(
            url,
            json={"query": query},
            headers=headers
        )

        if r.status_code == 200:
            bot.reply_to(msg, "🚀 Redeploy request sent")
        else:
            bot.reply_to(msg, f"❌ Failed ({r.status_code}): {r.text[:200]}")
