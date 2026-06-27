from SLH_V6_GATEWAY import SLHGateway


class SLHBot:

    def __init__(self):
        self.gateway = SLHGateway()
        print("🤖 V6 BOT ONLINE")

    def chat(self):
        while True:
            msg = input("You: ").strip()
            if not msg:
                continue

            result = self.gateway.handle("cli", msg)
            print("\nRESULT:\n", result, "\n")


if __name__ == "__main__":
    bot = SLHBot()
    bot.chat()
