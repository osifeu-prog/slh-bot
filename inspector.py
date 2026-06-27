import subprocess, os, urllib.request

class InspectorAgent:
    def __init__(self, bot, agents_dict, _KERNEL_READY, get_audit):
        self.bot = bot
        self.agents_dict = agents_dict
        self._KERNEL_READY = _KERNEL_READY
        self.get_audit = get_audit

    def run_all(self, chat_id):
        report = []
        # 1. Process
        report.append("🔍 [1/8] Processes")
        procs = subprocess.run("pgrep -af 'python3.*bot'", shell=True, capture_output=True, text=True).stdout.strip()
        report.append(f"Bot: {'✅' if procs else '❌'} ({len(procs.splitlines())} instances)")
        # 2. API
        report.append("🔍 [2/8] API")
        try:
            with urllib.request.urlopen("http://localhost:5000/api/health", timeout=5) as resp:
                report.append("✅ API health OK")
        except:
            report.append("❌ API health FAIL")
        # 3. Dashboard
        report.append("🔍 [3/8] Dashboard")
        dash = subprocess.run("curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/", shell=True, capture_output=True, text=True).stdout.strip()
        report.append(f"Dashboard HTTP: {'✅' if dash in ('200','304') else '❌'} ({dash})")
        # 4. Database
        report.append("🔍 [4/8] Database")
        db_ok = os.path.exists("db.json")
        report.append(f"DB: {'✅' if db_ok else '❌'}")
        # 5. Agent OS
        report.append("🔍 [5/8] Agent OS")
        agents = self.agents_dict if self.agents_dict else {}
        report.append(f"Agents: {'✅' if len(agents)>0 else '⚠️'} ({len(agents)} agents)")
        # 6. Kernel
        report.append("🔍 [6/8] Kernel")
        kernel_ok = self._KERNEL_READY if self._KERNEL_READY else False
        report.append(f"Kernel: {'✅' if kernel_ok else '❌'}")
        # 7. Audit
        report.append("🔍 [7/8] Audit")
        audit_entries = len(self.get_audit(1000))
        report.append(f"Audit: {'✅' if audit_entries>0 else '⚠️'} ({audit_entries} entries)")
        # 8. Git
        report.append("🔍 [8/8] Git")
        git_ok = subprocess.run("git status", shell=True, capture_output=True).returncode == 0
        report.append(f"Git: {'✅' if git_ok else '❌'}")
        return "\n".join(report)
