import json, os

def register(bot):
    @bot.message_handler(commands=['map'])
    def map_cmd(msg):
        devices = {}
        if os.path.exists('state/devices.json'):
            with open('state/devices.json', encoding='utf-8') as f:
                data = json.load(f)
            devices = data.get('devices', {})

        txt = "🗺 מפת מערכת SLH\n"
        if not devices:
            txt += "אין מכשירים רשומים."
        else:
            for k, v in devices.items():
                txt += f"{k}: {v.get('name', '?')} [{v.get('status', '?')}]\n"

        bot.reply_to(msg, txt)
