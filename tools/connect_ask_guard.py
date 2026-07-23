from pathlib import Path

p = Path("advanced_ask_handler.py")
s = p.read_text(encoding="utf-8")

if "core.ask_guard import" not in s:
    s = s.replace(
        "from core.ask_router import route as ask_route",
        "from core.ask_router import route as ask_route\nfrom core.ask_guard import allow_request, guarded_message"
    )

old = '''        question = msg.text.replace('/ask', '').strip()
        if not question:
            bot.reply_to(msg, "Usage: /ask <your question>")
            return
'''

new = '''        question = msg.text.replace('/ask', '').strip()
        if not question:
            bot.reply_to(msg, "Usage: /ask <your question>")
            return

        if not allow_request(question):
            bot.reply_to(msg, guarded_message())
            return
'''

if old in s:
    s = s.replace(old, new)
    p.write_text(s, encoding="utf-8")
    print("ASK guard connected")
else:
    print("ASK block not found")
