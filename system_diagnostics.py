#!/usr/bin/env python3
"""
SLH OS Advanced System Diagnostics Framework
Usage:
  python3 system_diagnostics.py
  python3 system_diagnostics.py --json   # output as JSON
"""
import os, sys, json, subprocess, importlib, time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

class SystemDiagnostics:
    def __init__(self):
        self.results: Dict[str, Any] = {}
        self.token: Optional[str] = None
        self._load_env()

    def _load_env(self):
        """Load BOT_TOKEN from state/.env if available."""
        env_path = "state/.env"
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("export BOT_TOKEN="):
                        self.token = line.split('"')[1]
                        break

    def check_bot_connection(self) -> str:
        """Verify Telegram Bot API connectivity."""
        if not self.token:
            return "❌ BOT_TOKEN not found in state/.env"
        try:
            import requests
            resp = requests.get(f"https://api.telegram.org/bot{self.token}/getMe", timeout=10)
            if resp.ok and resp.json().get("ok"):
                username = resp.json()["result"]["username"]
                return f"✅ Bot @{username} online"
            else:
                return f"❌ Bot API error: {resp.text[:200]}"
        except Exception as e:
            return f"❌ Exception: {str(e)}"

    def check_database(self) -> str:
        """Check db.json integrity and stats."""
        try:
            with open("state/db.json") as f:
                db = json.load(f)
            users = len(db.get("users", {}))
            agents = len(db.get("agents", {}))
            transactions = len(db.get("transactions", []))
            return f"✅ DB OK | Users: {users}, Agents: {agents}, Transactions: {transactions}"
        except Exception as e:
            return f"❌ DB error: {str(e)}"

    def check_core_files(self) -> str:
        """Ensure required Python files are present."""
        required = [
            "bot_stable.py", "payment_handler.py", "ton_handler.py",
            "econ_handler.py", "language_handler.py", "help_handler.py",
            "welcome_handler.py"
        ]
        missing = [f for f in required if not os.path.exists(f)]
        if missing:
            return f"❌ Missing files: {', '.join(missing)}"
        return f"✅ All {len(required)} core files present"

    def check_python_syntax(self) -> str:
        """Compile all core .py files."""
        files = [f for f in os.listdir('.') if f.endswith('.py') and not f.startswith('test_')]
        errors = []
        for f in files:
            try:
                subprocess.check_call([sys.executable, "-m", "py_compile", f],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except subprocess.CalledProcessError:
                errors.append(f)
        if errors:
            return f"❌ Syntax errors in: {', '.join(errors)}"
        return f"✅ All {len(files)} Python files compile clean"

    def check_git_status(self) -> str:
        """Check Git branch, unpushed commits, uncommitted changes."""
        try:
            branch = subprocess.check_output(["git", "branch", "--show-current"], text=True).strip()
            status = subprocess.check_output(["git", "status", "--short"], text=True)
            if status.strip():
                changes = len(status.strip().splitlines())
                return f"⚠️ Git branch '{branch}': {changes} uncommitted changes"
            else:
                behind = subprocess.check_output(["git", "rev-list", "--count", f"{branch}..origin/{branch}"], text=True).strip()
                if int(behind) > 0:
                    return f"⚠️ Git branch '{branch}': {behind} commits behind origin"
                return f"✅ Git branch '{branch}' up to date, clean"
        except Exception as e:
            return f"❌ Git error: {str(e)}"

    def check_railway_service(self) -> str:
        """Check Railway project status (if CLI available)."""
        try:
            import shutil
            if not shutil.which("railway"):
                return "ℹ️ Railway CLI not installed (expected if running on Railway)"
            # We are in Termux; railway CLI may not be linked; skip detailed check
            # but try to run 'railway status'
            out = subprocess.check_output(["railway", "status"], text=True, timeout=15)
            if "Online" in out:
                return "✅ Railway service online"
            elif "Crashed" in out:
                return "❌ Railway service crashed"
            else:
                return f"⚠️ Railway status unknown"
        except subprocess.CalledProcessError:
            return "❌ Railway CLI error (maybe not logged in)"
        except Exception as e:
            return f"ℹ️ Railway check skipped: {str(e)}"

    def check_agents(self) -> str:
        """Check agents heartbeat from local cron/PS and from db."""
        # Check cron
        cron_heartbeat = False
        try:
            cron_out = subprocess.check_output(["crontab", "-l"], text=True)
            if "agent_heartbeat" in cron_out:
                cron_heartbeat = True
        except:
            pass
        # Check if gotty is running
        gotty_running = False
        try:
            ps_out = subprocess.check_output(["ps", "aux"], text=True)
            if "gotty" in ps_out:
                gotty_running = True
        except:
            pass
        parts = []
        if cron_heartbeat:
            parts.append("Cron heartbeat active")
        if gotty_running:
            parts.append("Gotty remote terminal active")
        if parts:
            return f"✅ Agents: {', '.join(parts)}"
        return "⚠️ No local agent processes detected"

    def check_disk_usage(self) -> str:
        """Check disk usage of state/ and ."""
        try:
            state_size = subprocess.check_output(["du", "-sh", "state"], text=True).split()[0]
            total_size = subprocess.check_output(["du", "-sh", "."], text=True).split()[0]
            return f"ℹ️ Disk: state/ {state_size}, total {total_size}"
        except:
            return "❌ Could not measure disk usage"

    def check_logo_presence(self) -> str:
        """Ensure logo.txt exists."""
        if os.path.exists("logo.txt"):
            return "✅ logo.txt present"
        return "❌ logo.txt missing (use cat > logo.txt ...)"

    def run_all(self):
        methods = [
            ("Bot Connection", self.check_bot_connection),
            ("Database", self.check_database),
            ("Core Files", self.check_core_files),
            ("Python Syntax", self.check_python_syntax),
            ("Git Status", self.check_git_status),
            ("Railway Service", self.check_railway_service),
            ("Local Agents", self.check_agents),
            ("Disk Usage", self.check_disk_usage),
            ("Logo", self.check_logo_presence),
        ]
        for name, method in methods:
            try:
                result = method()
            except Exception as e:
                result = f"❌ Exception: {str(e)}"
            self.results[name] = result
            print(f"  {result}")

    def generate_report(self, as_json: bool = False):
        print("╔══════════════════════════════════════╗")
        print("║     SLH OS System Diagnostics        ║")
        print("╚══════════════════════════════════════╝")
        print(f"Time: {datetime.now(timezone.utc).isoformat()}")
        if os.path.exists("logo.txt"):
            print(open("logo.txt").read())
        print("")
        self.run_all()
        print("")
        if as_json:
            print(json.dumps(self.results, indent=2))
        else:
            print("Diagnostics complete.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()
    diag = SystemDiagnostics()
    diag.generate_report(as_json=args.json)
