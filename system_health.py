import state_manager
import os, json, subprocess, sys
from datetime import datetime, timezone


def _llm_config():
    return {
        "gemini": bool((os.getenv("GEMINI_API_KEY") or "").strip()),
        "groq": bool((os.getenv("GROQ_API_KEY") or "").strip()),
        "ollama": bool((os.getenv("OLLAMA_BASE_URL") or "").strip()),
    }


def get_health():
    """Return configuration-level health without making paid/provider calls."""
    llm = _llm_config()
    return {
        "ok": any(llm.values()),
        "components": {
            "bot": "running",
            "db": "connected",
            "llm": "configured" if any(llm.values()) else "missing",
            "llm_providers": llm,
            "disk": "ok",
        },
    }


def check_bot():
    token = (os.getenv("BOT_TOKEN") or "").strip()
    if not token:
        return "⚠️ Bot token not configured"
    try:
        import requests
        resp = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        if resp.json().get("ok"):
            return f"✅ Bot @{resp.json()['result']['username']} online"
    except Exception:
        pass
    return "❌ Bot verification failed"


def check_db():
    try:
        with open("state/db.json", encoding="utf-8") as f:
            db = json.load(f)
        users = len(db.get("users", {}))
        agents = len(state_manager.get_agents())
        txs = len(db.get("transactions", []))
        return f"✅ DB: {users} users, {agents} agents, {txs} transactions"
    except Exception:
        return "❌ DB error"


def check_files():
    required = ["bot_gateway.py", "handlers/loader.py", "state_manager.py"]
    missing = [f for f in required if not os.path.exists(f)]
    if missing:
        return f"❌ Missing: {missing}"
    return "✅ Core runtime files present"


def check_python():
    try:
        for f in ["bot_gateway.py", "state_manager.py"]:
            subprocess.check_call(
                [sys.executable, "-m", "py_compile", f],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        return "✅ Python core compiles clean"
    except Exception:
        return "❌ Python compilation errors"


def check_git():
    try:
        out = subprocess.check_output(["git", "status", "--short"], text=True)
        if out.strip():
            return "⚠️ Git has uncommitted changes"
        return "✅ Git clean"
    except Exception:
        return "⚪ Git not available"


def main():
    print("╔══════════════════════════════╗")
    print("║   SLH OS System Health      ║")
    print("╚══════════════════════════════╝")
    print(check_bot())
    print(check_db())
    print(check_files())
    print(check_python())
    print(check_git())
    llm = _llm_config()
    print(
        "LLM config: "
        + ", ".join(f"{name}={'configured' if ok else 'missing'}" for name, ok in llm.items())
    )
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")


def check_system_health():
    """Backward-compatible health payload for legacy callers."""
    health = get_health()
    return {
        "status": "ok" if health.get("ok") else "degraded",
        "components": health.get("components", {}),
    }


if __name__ == "__main__":
    main()
