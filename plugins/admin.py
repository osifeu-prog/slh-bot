def init(ctx):

    def on_command(text, chat_id, send):
        if text == "/admin":
            send(chat_id, "🔧 ADMIN PANEL ACTIVE")

    ctx["handlers"].append(on_command)
