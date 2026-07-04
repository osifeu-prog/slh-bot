import os
import sys
import time
import signal
import threading

# =========================
# SLH SAFE LOCK (anti double-run)
# =========================
LOCK_FILE = "/tmp/slh.lock"


def is_running():
    return os.path.exists(LOCK_FILE)


def create_lock():
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))


def remove_lock():
    if os.path.exists(LOCK_FILE):
        os.remove(LOCK_FILE)


# =========================
# SAFE SHUTDOWN HANDLER
# =========================
def shutdown(sig=None, frame=None):
    print("\n🛑 SLH SAFE SHUTDOWN")
    remove_lock()
    sys.exit(0)


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)


# =========================
# CORE SYSTEM (CLEAN ENGINE)
# =========================
class CoreSystem:
    def __init__(self):
        self.running = True
        self.counter = 0

    def loop(self):
        while self.running:
            self.counter += 1
            print(f"🧠 SLH SAFE CORE RUNNING | tick={self.counter}")
            time.sleep(2)


# =========================
# WATCHDOG (future-proof hook)
# =========================
class Watchdog:
    def __init__(self, core):
        self.core = core

    def loop(self):
        while True:
            # פה בעתיד נכנסים:
            # - חוזים
            # - agents
            # - Telegram events
            # - audit checks
            time.sleep(5)


# =========================
# MAIN BOOT
# =========================
def main():

    if is_running():
        print("⛔ SLH already running — abort")
        return

    create_lock()

    print("🚀 SLH SAFE MODE BOOTING")

    core = CoreSystem()
    watchdog = Watchdog(core)

    # core thread
    t1 = threading.Thread(target=core.loop, daemon=True)
    t1.start()

    # watchdog thread
    t2 = threading.Thread(target=watchdog.loop, daemon=True)
    t2.start()

    print("🔥 SLH SAFE MODE ACTIVE")

    while True:
        time.sleep(10)


if __name__ == "__main__":
    main()
