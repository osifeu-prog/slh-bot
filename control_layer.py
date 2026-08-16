import time
import json
import threading
from queue import Queue

# =========================
# CONTROL LAYER (INTERFACE)
# =========================

class ControlLayer:
    def __init__(self, core):
        self.core = core
        self.commands = {}
        self.audit_log = []

        self.register_defaults()

    # ---------------- REGISTER ----------------
    def register(self, name, fn, admin_only=False):
        self.commands[name] = {
            "fn": fn,
            "admin": admin_only
        }

    # ---------------- DEFAULT COMMANDS ----------------
    def register_defaults(self):

        self.register("status", self.status)
        self.register("test", self.test)
        self.register("help", self.help)
        self.register("reload", self.reload_config, admin_only=True)

    # ---------------- EXECUTE ----------------
    def execute(self, user_id, command, args=None):

        if command not in self.commands:
            return "❌ Unknown command"

        cmd = self.commands[command]

        # ADMIN CHECK (simple for now)
        if cmd["admin"] and user_id != self.core.admin_id:
            return "⛔ Unauthorized"

        result = cmd["fn"](args)

        self.audit_log.append({
            "time": time.time(),
            "user": user_id,
            "cmd": command,
            "args": args
        })

        return result

    # ---------------- COMMANDS ----------------
    def status(self, args=None):
        return self.core.exec.run("ps aux | grep python | grep -v grep")

    def test(self, args=None):
        return self.core.exec.run("python3 --version")

    def help(self, args=None):
        return "Commands: status, test, help, reload"

    def reload_config(self, args=None):
        self.core.reload()
        return "🔄 Config reloaded"

