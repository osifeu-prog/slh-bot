"""SLH OS Marketplace"""
import json, os

STORE_FILE = "marketplace.json"

def load_store():
    try:
        with open(STORE_FILE) as f:
            return json.load(f)
    except:
        return {
            "plugins": [
                {"id": "health_check", "name": "Health Check", "desc": "Adds /health command", "price": 0, "installs": 0},
                {"id": "task_plugin", "name": "Task Plugin", "desc": "Adds /task create/list", "price": 0, "installs": 0},
                {"id": "agent_os", "name": "Agent OS", "desc": "Full agent system", "price": 49, "installs": 0}
            ],
            "installed": []
        }

def save_store(data):
    with open(STORE_FILE, "w") as f:
        json.dump(data, f, indent=2)
