import time


class SLHBotAdapter:

    def __init__(self, gateway):
        self.gateway = gateway
        print("🤖 BOT ADAPTER ONLINE")

    def receive_message(self, source, text):
        event = {
            "source": source,
            "cmd": text,
            "payload": {},
            "timestamp": time.time()
        }

        result = self.gateway.handle_event(event)
        print(f"Bot: {result}")
        return result

    def chat(self):
        while True:
            msg = input("You: ").strip()
            if not msg:
                continue
            self.receive_message("cli", msg)


if __name__ == "__main__":
    from SLH_GATEWAY import SLHGateway

    gateway = SLHGateway()
    bot = SLHBotAdapter(gateway)

    bot.chat()
