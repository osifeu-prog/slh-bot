def init(ctx):

    def on_command(text, chat_id, send):
        if text == "/sys":
            send(chat_id, "⚙️ SYSTEM MODULE OK")

    ctx["handlers"].append(on_command)
