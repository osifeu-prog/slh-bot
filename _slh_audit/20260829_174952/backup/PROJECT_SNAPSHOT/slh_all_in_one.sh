#!/bin/bash
echo "🚀 SLH ALL-IN-ONE STARTING..."

# 1. גיבוי קבצים חיוניים
mkdir -p /tmp/slh_backups
cp handlers/advanced_ask_handler.py /tmp/slh_backups/ 2>/dev/null
cp handlers/llm_handler.py /tmp/slh_backups/ 2>/dev/null
cp handlers/loader.py /tmp/slh_backups/ 2>/dev/null
echo "✅ Backup done"

# 2. וידוא קיום קבצי לוגו ו-ESP
if [ ! -f branding/SLH_LOGO.txt ]; then
    mkdir -p branding
    cat > branding/SLH_LOGO.txt << 'LOGO'
   ███████╗██╗     ██╗  ██╗
   ██╔════╝██║     ██║  ██║
   ███████╗██║     ███████║
   ╚════██║██║     ██╔══██║
   ███████║███████╗██║  ██║
   ╚══════╝╚══════╝╚═╝  ╚═╝
      SLH OS • v3.0
      Production Ready
LOGO
fi

if [ ! -f handlers/logo_handler.py ]; then
    cat > handlers/logo_handler.py << 'PYEOF'
def register_logo_handler(bot):
    @bot.message_handler(commands=['logo'])
    def logo_cmd(msg):
        with open("branding/SLH_LOGO.txt", "r", encoding="utf-8") as f:
            bot.reply_to(msg, f"<pre>{f.read()}</pre>", parse_mode="HTML")
PYEOF
fi

if [ ! -f handlers/esp_handler.py ]; then
    cat > handlers/esp_handler.py << 'PYEOF'
import json, os, paho.mqtt.client as mqtt, time
from datetime import datetime, timezone

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
RESPONSES = {}

def on_message(client, userdata, msg):
    RESPONSES[msg.topic] = msg.payload.decode()

mqtt_client = mqtt.Client()
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.subscribe("slh/esp/response/#")
mqtt_client.loop_start()

def register_esp_handler(bot):
    @bot.message_handler(commands=["esp_ping"])
    def esp_ping(msg):
        parts = msg.text.split()
        device_id = parts[1] if len(parts) > 1 else "esp32_01"
        with open("state/db.json","r") as f:
            db = json.load(f)
        dev = db.get("devices",{}).get(device_id)
        if not dev:
            bot.reply_to(msg, f"Device {device_id} not found.")
            return
        topic = dev.get("mqtt_topic", f"slh/esp/{device_id}")
        mqtt_client.publish(topic + "/command", "ping")
        time.sleep(2)
        reply = RESPONSES.get(topic + "/response", "No response")
        dev["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
        dev["status"] = "online" if reply != "No response" else "offline"
        with open("state/db.json","w") as f:
            json.dump(db, f, indent=2)
        bot.reply_to(msg, f"ESP32 {device_id}: {reply}")

    @bot.message_handler(commands=["esp_status"])
    def esp_status(msg):
        with open("state/db.json","r") as f:
            db = json.load(f)
        devs = db.get("devices",{})
        if not devs:
            bot.reply_to(msg, "No devices registered.")
            return
        lines = [f"{did}: {d.get('status','?')} | last: {d.get('last_heartbeat','never')}" for did, d in devs.items()]
        bot.reply_to(msg, "\n".join(lines))
PYEOF
fi

# 3. רישום handlers בלואדר
grep -q "register_logo_handler" handlers/loader.py || sed -i '/def load_handlers/a\    from handlers.logo_handler import register_logo_handler\n    register_logo_handler(bot)' handlers/loader.py
grep -q "register_esp_handler" handlers/loader.py || sed -i '/register_logo_handler/a\    from handlers.esp_handler import register_esp_handler\n    register_esp_handler(bot)' handlers/loader.py

# 4. רישום מכשיר ESP32
python3 -c "
import json
with open('state/db.json','r') as f:
    db = json.load(f)
db.setdefault('devices',{})
if 'esp32_01' not in db['devices']:
    db['devices']['esp32_01'] = {
        'type': 'ESP32',
        'serial': 'ESP-20260727-001',
        'status': 'offline',
        'last_heartbeat': '',
        'mqtt_topic': 'slh/esp/esp32_01'
    }
    with open('state/db.json','w') as f:
        json.dump(db, f, indent=2)
    print('✅ esp32_01 device registered')
"

# 5. קומפילציה
python3 -m py_compile handlers/esp_handler.py handlers/logo_handler.py handlers/loader.py 2>/dev/null


# 6. דחיפה ל-Git
git add -A
git commit -m "SLH All-in-One: ensure logo, esp, loader, device" 2>/dev/null
git push origin main

echo "✅ All-in-One Complete. Railway will deploy automatically."
echo "⏳ Wait 60 seconds, then send: /logo"
