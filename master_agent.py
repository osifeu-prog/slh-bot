import threading, time, subprocess, os, urllib.request

class MasterAgent:
    def __init__(self, bot, agents_dict, _KERNEL_READY, get_audit):
        self.bot = bot
        self.agents_dict = agents_dict
        self._KERNEL_READY = _KERNEL_READY
        self.get_audit = get_audit
        self._watchdog_running = False
        self._watchdog_thread = None

    # ---------- quick check ----------
    def quick_check(self):
        report = ["⚡ QUICK CHECK"]
        # 1. Process
        procs = subprocess.run("pgrep -af 'python3.*bot'", shell=True, capture_output=True, text=True).stdout.strip()
        report.append(f"Bot: {'✅' if procs else '❌'}")
        # 2. API
        try:
            urllib.request.urlopen("http://localhost:5000/api/health", timeout=2)
            report.append("API: ✅")
        except:
            report.append("API: ❌")
        # 3. DB
        report.append(f"DB: {'✅' if os.path.exists('db.json') else '❌'}")
        # 4. Kernel
        report.append(f"Kernel: {'✅' if self._KERNEL_READY else '❌'}")
        # 5. Git
        git_ok = subprocess.run("git status", shell=True, capture_output=True).returncode == 0
        report.append(f"Git: {'✅' if git_ok else '❌'}")
        return "\n".join(report)

    # ---------- full check (uses Inspector) ----------
    def full_check(self, chat_id):
        from inspector import InspectorAgent
        insp = InspectorAgent(self.bot, self.agents_dict, self._KERNEL_READY, self.get_audit)
        return insp.run_all(chat_id)

    # ---------- watchdog ----------
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
