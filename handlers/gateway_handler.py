from SLH_GATEWAY import SLHGateway
from core.authority import has_permission

gateway = SLHGateway()


def register(bot):

    @bot.message_handler(commands=["gateway"])
    def gateway_command(message):
        try:
            result = gateway.send(
                source="telegram",
                cmd="status",
                payload={
                    "user_id": message.chat.id
                }
            )

            bot.reply_to(
                message,
                f"🌐 SLH Gateway Status:

{result}"
            )

        except Exception as e:
            bot.reply_to(
                message,
                f"❌ Gateway error: {e}"
            )


    @bot.message_handler(commands=["gateway_test"])
    def gateway_test(message):
        try:
            result = gateway.send(
                source="telegram",
                cmd="telegram:test",
                payload={
                    "user_id": message.chat.id
                }
            )

            bot.reply_to(
                message,
                str(result)
            )

        except Exception as e:
            bot.reply_to(
                message,
                f"❌ Gateway test failed: {e}"
            )
