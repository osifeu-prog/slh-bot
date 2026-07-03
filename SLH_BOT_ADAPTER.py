class SLHBotAdapter:
    def __init__(self, gateway):
        self.gateway = gateway

    def chat(self):
        print("🤖 SLH BOT READY")

        while True:
            try:
                msg = input(">> ").strip()

                if not msg:
                    continue

                if msg in ["/exit", "exit", "quit"]:
                    print("🛑 STOPPED")
                    break

                result = self.gateway.send(
                    source="cli",
                    cmd=msg,
                    payload={}
                )

                print(result)

            except KeyboardInterrupt:
                print("\n🛑 STOPPED (manual interrupt)")
                break
