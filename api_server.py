import os, telebot, json
from pathlib import Path
from handlers.loader import load_handlers

STATE_DIR = Path("state")
STATE_DIR.mkdir(exist_ok=True)
BOTS_FILE = STATE_DIR / "bots.json"

def load_bots():
    if BOTS_FILE.exists():
        return json.load(open(BOTS_FILE))
    return {"Me_ad_main": os.getenv("BOT_TOKEN")}

app = None
bots = {}

def init():
    global app
    try:
        from flask import Flask, request, Response
        app = Flask(__name__)
    except ImportError:
        import bottle
        app = bottle.Bottle()

    data = load_bots()
    for name, token in data.items():
        if not token: continue
        bot = telebot.TeleBot(token, parse_mode="HTML")
        load_handlers(bot, {"bot_name": name})
        bots[name] = bot

    if hasattr(app, 'route'):
        @app.route('/')
        def home():
            return "SLH Bot Webhook OK"

        @app.route('/webhook/<name>', methods=['POST'])
        def webhook(name):
            if name in bots:
                json_str = request.get_data().decode('utf-8')
                update = telebot.types.Update.de_json(json_str)
                bots[name].process_new_updates([update])
                return Response(status=200)
            return Response(status=404)
    else:
        @app.get('/')
        def home():
            return "SLH Bot Webhook OK"

        @app.post('/webhook/<name>')
        def webhook(name):
            if name in bots:
                json_str = bottle.request.body.read().decode('utf-8')
                update = telebot.types.Update.de_json(json_str)
                bots[name].process_new_updates([update])
                return "OK"
            return bottle.HTTPError(404, "Not found")

    print("✅ api_server initialized")

init()
if __name__ == "__main__":
    if hasattr(app, 'run'):
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
    else:
        from bottle import run
        run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
