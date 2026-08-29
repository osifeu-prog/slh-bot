class Kernel:
    def route(self, event):
        return {"ok": event["cmd"]}

class Runtime:
    def __init__(self):
        self.kernel = Kernel()

    def emit(self, cmd):
        return self.kernel.route({"cmd": cmd})

rt = Runtime()

while True:
    try:
        msg = input(">> ").strip()

        if not msg:
            continue

        if msg in ["exit", "quit"]:
            break

        print(rt.emit(msg))

    except KeyboardInterrupt:
        print("\nbye")
        break
