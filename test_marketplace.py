import sys
sys.path.insert(0, '.')
from plugins_store import *

print("=== Marketplace Demo Tests ===\n")
errors = 0

# 1. Load plugins
plugins = load_plugins()
assert "available" in plugins and "installed" in plugins
print("✅ Plugin store structure OK")
print(f"   Available: {len(plugins['available'])} plugins")
print(f"   Installed: {len(plugins['installed'])} plugins\n")

# 2. Install a plugin
result = install_plugin("health_check")
assert "✅" in result
print(result)
assert "health_check" in list_plugins()
print("✅ Installation verified\n")

# 3. List installed
installed = list_plugins()
assert len(installed) == 1
print(f"✅ Installed plugins count: {len(installed)}")

# 4. Search
results = search_plugins("task")
assert len(results) == 1
print(f"✅ Search 'task': found {len(results)} plugin(s)")

# 5. Get info
info = get_plugin_info("health_check")
assert info and info["name"] == "Health Check"
print(f"✅ Plugin info OK: {info['name']}")

# 6. Uninstall
result = uninstall_plugin("health_check")
assert "✅" in result
assert "health_check" not in list_plugins()
print(result)

print("\n=== ALL MARKETPLACE TESTS PASSED ===")
