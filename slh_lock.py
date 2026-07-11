import os
import sys
import atexit
import signal

import os

BASE_DIR = os.environ.get(
    "SLH_HOME",
    "/app" if os.path.exists("/app") else os.path.expanduser("~/slh_clean")
)

LOCK_FILE = os.path.join(BASE_DIR, ".bot.lock")


class SLHLock:
    def __init__(self):
        self.lock_file = LOCK_FILE
        self.current_pid = os.getpid()

        atexit.register(self.release_lock)
        signal.signal(signal.SIGINT, self._handle_exit)
        signal.signal(signal.SIGTERM, self._handle_exit)

    # -----------------------------
    # check process alive
    # -----------------------------
    def _is_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    # -----------------------------
    # read lock
    # -----------------------------
    def _read(self):
        try:
            if not os.path.exists(self.lock_file):
                return None
            with open(self.lock_file, "r") as f:
                data = f.read().strip()
                return int(data) if data else None
        except:
            return None

    # -----------------------------
    # atomic write
    # -----------------------------
    def _write(self, pid: int):
        tmp = self.lock_file + ".tmp"
        with open(tmp, "w") as f:
            f.write(str(pid))
        os.replace(tmp, self.lock_file)

    # -----------------------------
    # remove lock
    # -----------------------------
    def _remove(self):
        try:
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
        except:
            pass

    # -----------------------------
    # validate PID (resilient check)
    # -----------------------------
    def _valid_process(self, pid: int) -> bool:
        if not self._is_alive(pid):
            return False

        # best-effort verification (Termux-safe)
        try:
            with open(f"/proc/{pid}/cmdline", "r") as f:
                cmd = f.read().lower()
                return "python" in cmd or "bot" in cmd or "slh" in cmd
        except:
            return True

    # -----------------------------
    # ACQUIRE LOCK (FINAL STABLE)
    # -----------------------------
    def acquire_lock(self):
        existing = self._read()

        if existing:
            if self._valid_process(existing):
                print(f"❌ BOT ALREADY RUNNING (PID {existing})")
                sys.exit(1)
            else:
                print(f"⚠️ STALE LOCK REMOVED (PID {existing})")
                self._remove()

        # write new lock
        self._write(self.current_pid)

        # verify
        verify = self._read()
        if verify != self.current_pid:
            print("❌ LOCK FAILED (race detected)")
            sys.exit(1)

        print(f"✅ LOCK ACQUIRED (PID {self.current_pid})")

    # -----------------------------
    # RELEASE LOCK
    # -----------------------------
    def release_lock(self):
        existing = self._read()
        if existing == self.current_pid:
            self._remove()
            print("🔓 LOCK RELEASED")

    # -----------------------------
    # safe exit handler
    # -----------------------------
    def _handle_exit(self, signum, frame):
        self.release_lock()
        sys.exit(0)


slh_lock = SLHLock()

def is_locked():
    """Return False by default (no lock)"""
    return False

