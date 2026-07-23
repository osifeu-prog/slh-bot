#!/usr/bin/env python3
"""
SLH Device Bridge
מחבר מכשירים (PC, ESP32, Mobile) ל-SLH OS דרך Telegram API
"""
import json, os, time, requests, socket, threading, sys
from datetime import datetime

CONFIG_FILE = "state/bridge_config.json"
DEVICES_FILE = "state/devices.json"
TELEGRAM_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID", "YOUR_CHAT_ID")

class DeviceManager:
    def __init__(self):
        self.devices = self.load_devices()
    def load_devices(self):
        try:
            with open(DEVICES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("devices", {})
        except:
            return {}
    def save_devices(self, devices):
        with open(DEVICES_FILE, "w", encoding="utf-8") as f:
            json.dump({"devices": devices}, f, indent=2, ensure_ascii=False)
    def register_device(self, name, device_type="pc", capabilities=None):
        if capabilities is None:
            capabilities = ["compute", "network", "storage"]
        device_id = f"BRIDGE_{name.upper().replace(' ', '_')}_{int(time.time())}"
        self.devices[device_id] = {
            "name": name,
            "type": device_type,
            "status": "offline",
            "capabilities": capabilities,
            "registered": time.time(),
            "last_seen": None,
            "bridge": True
        }
        self.save_devices(self.devices)
        return device_id
    def update_status(self, device_id, status="online"):
        if device_id in self.devices:
            self.devices[device_id]["status"] = status
            self.devices[device_id]["last_seen"] = time.time()
            self.save_devices(self.devices)
            return True
        return False

class TelegramBridge:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{token}"
    def send_message(self, text):
        url = f"{self.base_url}/sendMessage"
        data = {"chat_id": self.chat_id, "text": text}
        try:
            requests.post(url, json=data, timeout=10)
        except Exception as e:
            print(f"❌ Send error: {e}")
    def send_device_heartbeat(self, device_id, status="online"):
        self.send_message(f"/device_heartbeat {device_id} {status}")

class LocalComputerAgent:
    def __init__(self, bridge):
        self.bridge = bridge
        self.device_manager = DeviceManager()
        self.device_id = None
        self.hostname = socket.gethostname()
        self.local_ip = socket.gethostbyname(self.hostname)
    def register(self):
        name = f"PC_{self.hostname}"
        self.device_id = self.device_manager.register_device(name, "pc", ["compute", "network", "storage", "ai"])
        print(f"✅ Registered as: {self.device_id}")
        return self.device_id
    def heartbeat(self):
        if self.device_id:
            self.device_manager.update_status(self.device_id, "online")
            self.bridge.send_device_heartbeat(self.device_id, "online")
            print(f"💓 Heartbeat sent: {self.device_id}")
    def run_forever(self, interval=30):
        print(f"🔄 Local Computer Agent running on {self.local_ip}")
        print(f"📡 Device ID: {self.device_id}")
        while True:
            self.heartbeat()
            time.sleep(interval)

if __name__ == "__main__":
    print("==========================================")
    print("     SLH Device Bridge")
    print("==========================================")
    print()
    print("Choose mode:")
    print("1. Local Computer Agent (register this PC)")
    print("2. Bridge Server (accept connections)")
    print("3. Bridge Client (connect to server)")
    choice = sys.argv[1] if len(sys.argv) > 1 else input("Enter choice (1/2/3): ").strip()
    if choice == "1":
        bridge = TelegramBridge(TELEGRAM_TOKEN, CHAT_ID)
        agent = LocalComputerAgent(bridge)
        agent.register()
        print("\n🚀 Starting Local Computer Agent...")
        agent.run_forever(30)
    elif choice == "2":
        # Server mode - simple TCP listener (not fully implemented here)
        print("Server mode not fully implemented – use Client mode to connect.")
    elif choice == "3":
        host = input("Enter bridge server IP: ").strip()
        print(f"Client mode connecting to {host}... (implement later)")
    else:
        print("❌ Invalid choice")