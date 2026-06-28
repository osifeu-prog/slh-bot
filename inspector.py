import socket, os, urllib.request

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
        report.append("Bot: ✅ (responding)")
        # 2. API
        report.append("🔍 [2/8] API")
        api_ok = False
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(("localhost", 5000))
            s.send(b"GET /api/health HTTP/1.0\r\nHost: localhost\r\n\r\n")
            resp = s.recv(1024).decode()
            api_ok = '"ok"' in resp
            s.close()
        except:
            pass
        report.append(f"✅ API health OK" if api_ok else "❌ API health FAIL")
        # 3. Dashboard
        report.append("🔍 [3/8] Dashboard")
        dash_ok = False
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(("localhost", 8000))
            s.send(b"GET / HTTP/1.0\r\nHost: localhost\r\n\r\n")
            resp = s.recv(1024).decode()
            dash_ok = "SLH" in resp or "Dashboard" in resp
            s.close()
        except:
            pass
        report.append(f"Dashboard: {'✅' if dash_ok else '❌'}")
        # 4. Database
        report.append("🔍 [4/8] Database")
        report.append(f"DB: {'✅' if os.path.exists('db.json') else '❌'}")
        # 5. Agent OS
        report.append("🔍 [5/8] Agent OS")
        agents = self.agents_dict if self.agents_dict else {}
        report.append(f"Agents: {'✅' if len(agents)>0 else '⚠️'} ({len(agents)} agents)")
        # 6. Kernel
        report.append("🔍 [6/8] Kernel")
        report.append(f"Kernel: {'✅' if self._KERNEL_READY else '❌'}")
        # 7. Audit
        report.append("🔍 [7/8] Audit")
        audit_entries = len(self.get_audit(1000))
        report.append(f"Audit: {'✅' if audit_entries>0 else '⚠️'} ({audit_entries} entries)")
        # 8. Git
        report.append("🔍 [8/8] Git")
        report.append(f"Git: {'✅' if os.path.exists('.git') else '❌'}")
        return "\n".join(report)
