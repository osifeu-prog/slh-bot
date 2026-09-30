from SLH_GATEWAY import SLHGateway
from core.authority import has_permission

gateway = SLHGateway()

MAX_TELEGRAM_MESSAGE = 3500


def _send_chunked(bot, message, text):
    text = str(text or "(no output)")
    if len(text) <= MAX_TELEGRAM_MESSAGE:
        bot.reply_to(message, text)
        return

    chunks = [
        text[i:i + MAX_TELEGRAM_MESSAGE]
        for i in range(0, len(text), MAX_TELEGRAM_MESSAGE)
    ]
    total = len(chunks)
    for index, chunk in enumerate(chunks, 1):
        prefix = f"🌐 Gateway Status · {index}/{total}\n\n"
        if len(prefix) + len(chunk) > 4096:
            chunk = chunk[: 4096 - len(prefix)]
        if index == 1:
            bot.reply_to(message, prefix + chunk)
        else:
            bot.send_message(message.chat.id, prefix + chunk)


def register(bot):
    @bot.message_handler(commands=["gateway"])
    def gateway_command(message):
        uid = getattr(getattr(message, "from_user", None), "id", None)
        if not has_permission(uid, "exec.audit"):
            bot.reply_to(message, "Control Plane access denied.")
            return
        try:
            result = gateway.send(
                source="telegram",
                cmd="status",
                payload={"user_id": message.chat.id},
            )
            _send_chunked(bot, message, f"🌐 SLH Gateway Status:\n\n{result}")
        except Exception as e:
            _send_chunked(bot, message, f"❌ Gateway error: {e}")


    @bot.message_handler(commands=["gateway_test"])
    def gateway_test(message):
        uid = getattr(getattr(message, "from_user", None), "id", None)
        if not has_permission(uid, "exec.audit"):
            bot.reply_to(message, "Control Plane access denied.")
            return
        try:
            result = gateway.send(
                source="telegram",
                cmd="telegram:test",
                payload={"user_id": message.chat.id},
            )
            _send_chunked(bot, message, result)
        except Exception as e:
            _send_chunked(bot, message, f"❌ Gateway test failed: {e}")
