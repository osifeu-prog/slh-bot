import json, os
def register(bot):
    @bot.message_handler(commands=['map'])
    def map_cmd(msg):
        devices = {}
        if os.path.exists('state/devices.json'):
            with open('state/devices.json') as f: devices = json.load(f)
        txt = "🗺️ מפת מערכת SLH\n"
        for k,v in devices.items():
            txt += f"{k}: {v.get('name')} [{v.get('status')}]\n"
        bot.reply_to(msg, txt)
