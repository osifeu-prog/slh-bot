import threading, time, subprocess, os, urllib.request

class MasterAgent:
    def __init__(self, bot, agents_dict, _KERNEL_READY, get_audit):
        self.bot = bot
        self.agents_dict = agents_dict
        self._KERNEL_READY = _KERNEL_READY
        self.get_audit = get_audit
        self._watchdog_running = False
        self._watchdog_thread = None

    def quick_check(self):
        report = ["⚡ QUICK CHECK"]
        # 1. Bot
        report.append("Bot: ✅ (responding)")
        # 2. API – try direct socket
        api_ok = False
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(("localhost", 5000))
            s.send(b"GET /api/health HTTP/1.0\r\nHost: localhost\r\n\r\n")
            resp = s.recv(1024).decode()
            api_ok = '"ok"' in resp
            s.close()
        except:
            pass
        report.append(f"API: {'✅' if api_ok else '❌'}")
        # 3. DB
        report.append(f"DB: {'✅' if os.path.exists('db.json') else '❌'}")
        # 4. Kernel
        report.append(f"Kernel: {'✅' if self._KERNEL_READY else '❌'}")
        # 5. Git
        git_ok = os.path.exists(".git")
        report.append(f"Git: {'✅' if git_ok else '❌'}")
        return "\n".join(report)

    def full_check(self, chat_id):
        from inspector import InspectorAgent
        insp = InspectorAgent(self.bot, self.agents_dict, self._KERNEL_READY, self.get_audit)
        return insp.run_all(chat_id)

    def _watchdog_loop(self, chat_id, interval_min):
        while self._watchdog_running:
            time.sleep(interval_min * 60)
            if self._watchdog_running:
                try:
                    report = self.quick_check()
                    self.bot.send_message(chat_id, f"⏰ Watchdog Report:\n{report}")
                except Exception as e:
                    print(f"Watchdog error: {e}")

    def watchdog_start(self, chat_id, interval=60):
        if self._watchdog_running:
            return "⚠️ Watchdog already running"
        self._watchdog_running = True
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop, args=(chat_id, interval), daemon=True)
        self._watchdog_thread.start()
        return f"✅ Watchdog started – report every {interval} min"

    def watchdog_stop(self):
        if not self._watchdog_running:
            return "⚠️ Watchdog not running"
        self._watchdog_running = False
        return "✅ Watchdog stopped"
