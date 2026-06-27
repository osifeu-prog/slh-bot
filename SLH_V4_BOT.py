import time


class SLHBot:

    def __init__(self, gateway):
        self.gateway = gateway
        print("🤖 BOT ONLINE")

    def send(self, text):
        return self.gateway.handle("cli", text)

    def chat(self):
        while True:
            msg = input("You: ").strip()
            if not msg:
                continue

            result = self.send(msg)
            print("Bot:", result)


if __name__ == "__main__":
    from SLH_V4_GATEWAY import SLHGateway

    gw = SLHGateway()
    bot = SLHBot(gw)

    bot.chat()
