class CLIAdapter:
    def __init__(self, runtime):
        self.runtime = runtime

    def run(self):
        print("🧠 OS MODE v2 ACTIVE")

        self.runtime.set_callback(lambda r: print("📦", r))

        while True:
            msg = input(">> ").strip()

            if not msg:
                continue

            if msg in ["exit", "quit"]:
                print("🛑 STOPPED")
                self.runtime.stop()
                break

            self.runtime.emit({
                "source": "cli",
                "cmd": msg,
                "payload": {}
            })
