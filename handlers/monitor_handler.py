import json, os, time, subprocess
from datetime import datetime

def load_monitors():
    try:
        with open("state/monitor_config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"monitors": {}, "settings": {"heartbeat_interval": 30, "log_retention": 7, "alert_channels": ["telegram"]}}

def save_monitors(data):
    with open("state/monitor_config.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def monitor_list(bot, m):
    data = load_monitors()
    monitors = data["monitors"]
    if not monitors:
        bot.reply_to(m, "📡 No monitors configured")
        return
    lines = ["📡 SLH Monitors:"]
    for did, d in monitors.items():
        status_icon = "🟢" if d.get("status") == "online" else "🔴"
        lines.append(f"{status_icon} **{d.get('name', did)}** ({did})")
        lines.append(f"   Type: {d.get('type', 'unknown')}")
        lines.append(f"   Last check: {d.get('last_check', 'Never')}")
        lines.append("")
    bot.reply_to(m, "\n".join(lines), parse_mode="Markdown")

def monitor_status(bot, m):
    parts = m.text.split()
    if len(parts) < 2:
        bot.reply_to(m, "Usage: /monitor_status <device_id>")
        return
    did = parts[1]
    data = load_monitors()
    monitors = data["monitors"]
    if did not in monitors:
        bot.reply_to(m, f"❌ Monitor '{did}' not found")
        return
    d = monitors[did]
    msg = f"""
📡 **Monitor Status**: {d.get('name', did)}
🆔 ID: {did}
📝 Description: {d.get('description', 'N/A')}
🟢 Status: {d.get('status', 'unknown')}
🕒 Last check: {d.get('last_check', 'Never')}
🕒 Registered: {d.get('registered', 'Never')}
👤 Owner: {d.get('owner', 'unknown')}
"""
    bot.reply_to(m, msg, parse_mode="Markdown")

def monitor_logs(bot, m):
    parts = m.text.split()
    if len(parts) < 2:
        bot.reply_to(m, "Usage: /monitor_logs <device_id>")
        return
    did = parts[1]
    data = load_monitors()
    monitors = data["monitors"]
    if did not in monitors:
        bot.reply_to(m, f"❌ Monitor '{did}' not found")
        return
    # Simulate logs - in real use, fetch from device
    logs = [
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ Device online",
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 💓 Heartbeat received",
        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 📊 CPU: 12% | RAM: 47% | Disk: 68%"
    ]
    bot.reply_to(m, "📋 **Logs for " + did + "**:\n" + "\n".join(logs), parse_mode="Markdown")

def register(bot, context):
    @bot.message_handler(commands=['monitor_list'])
    def monitor_list_cmd(m): monitor_list(bot, m)
    @bot.message_handler(commands=['monitor_status'])
    def monitor_status_cmd(m): monitor_status(bot, m)
    @bot.message_handler(commands=['monitor_logs'])
    def monitor_logs_cmd(m): monitor_logs(bot, m)
    print("📡 Monitor handler loaded")