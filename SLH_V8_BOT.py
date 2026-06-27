from SLH_V8_GATEWAY import SLHGateway


class SLHBot:

    def __init__(self):
        self.gateway = SLHGateway()

    def chat(self):
        print("🤖 V8 SWARM BOT ONLINE")

        while True:
            msg = input("You: ").strip()
            if not msg:
                continue

            result = self.gateway.handle("cli", msg)
            print("\n🏁 RESULT:\n", result, "\n")


if __name__ == "__main__":
    bot = SLHBot()
    bot.chat()
