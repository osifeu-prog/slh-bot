import json, os, time

PLUGINS_FILE = "plugins.json"

def load_plugins():
    try:
        with open(PLUGINS_FILE) as f:
            return json.load(f)
    except:
        return {"installed": {}, "available": [
            {"id": "health_check", "name": "Health Check", "description": "Adds /health command", "url": "https://raw.githubusercontent.com/osifeu-prog/slh-bot/main/plugins/health.py", "price": 0},
            {"id": "task_plugin", "name": "Task Plugin", "description": "Adds /task create/list", "url": "https://raw.githubusercontent.com/osifeu-prog/slh-bot/main/plugins/task.py", "price": 0},
            {"id": "agent_os", "name": "Agent OS", "description": "Full agent management system", "url": "https://raw.githubusercontent.com/osifeu-prog/slh-bot/main/plugins/agent_os.py", "price": 0}
        ]}

def save_plugins(data):
    with open(PLUGINS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def install_plugin(plugin_id):
    """Install a plugin from available list"""
    plugins = load_plugins()
    
    # Find in available
    for p in plugins["available"]:
        if p["id"] == plugin_id:
            plugins["installed"][plugin_id] = {
                **p,
                "installed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "active": True
            }
            save_plugins(plugins)
            return f"✅ Plugin '{p['name']}' installed successfully"
    
    return f"❌ Plugin '{plugin_id}' not found in store"

def uninstall_plugin(plugin_id):
    """Remove an installed plugin"""
    plugins = load_plugins()
    if plugin_id in plugins["installed"]:
        name = plugins["installed"][plugin_id]["name"]
        del plugins["installed"][plugin_id]
        save_plugins(plugins)
        return f"✅ Plugin '{name}' uninstalled"
    return f"❌ Plugin '{plugin_id}' not found"

def list_plugins():
    """List all installed plugins"""
    plugins = load_plugins()
    return plugins["installed"]

def search_plugins(query):
    """Search available plugins"""
    plugins = load_plugins()
    query = query.lower()
    return [p for p in plugins["available"] if query in p["name"].lower() or query in p["description"].lower()]

def get_store():
    """Get all available plugins"""
    return load_plugins()["available"]

def get_plugin_info(plugin_id):
    """Get plugin details"""
    plugins = load_plugins()
    return plugins["installed"].get(plugin_id) or next((p for p in plugins["available"] if p["id"] == plugin_id), None)
