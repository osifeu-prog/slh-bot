import json, time, os, threading
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883

def _send_cmd(device_id, payload, timeout=6):
    resp_topic = f"slh/esp/{device_id}/response"
    cmd_topic  = f"slh/esp/{device_id}/command"
    result = {"got": None}

    def on_connect(c, u, f, rc):
        c.subscribe(resp_topic)

    def on_message(c, u, msg):
        result["got"] = msg.payload.decode()
        c.disconnect()

    c = mqtt.Client()
    c.on_connect = on_connect
    c.on_message = on_message
    c.connect(MQTT_BROKER, MQTT_PORT, 60)
    c.loop_start()
    time.sleep(0.5)
    c.publish(cmd_topic, payload)
    for _ in range(timeout * 2):
        if result["got"] is not None:
            break
        time.sleep(0.5)
    c.loop_stop()
    try: c.disconnect()
    except: pass
    return result["got"]

def _load_devices():
    try:
        with open("state/devices.json", "r", encoding="utf-8") as f:
            return json.load(f).get("devices", {})
    except Exception:
        return {}

def _owner_ok(dev, uid):
    return str(dev.get("owner")) == str(uid)

def register(bot, context=None):
    @bot.message_handler(commands=["esp_msg"])
    def esp_msg(m):
        parts = m.text.split(maxsplit=2)
        if len(parts) < 3:
            bot.reply_to(m, "Usage: /esp_msg <device_id> <text>")
            return
        did, txt = parts[1], parts[2]
        dev = _load_devices().get(did)
        if not dev: bot.reply_to(m, f"Device {did} not found"); return
        if not _owner_ok(dev, m.from_user.id): bot.reply_to(m, "Not your device"); return
        r = _send_cmd(did, "msg " + txt)
        bot.reply_to(m, f"{did}: {r or 'no response'}")

    @bot.message_handler(commands=["esp_clear"])
    def esp_clear(m):
        parts = m.text.split()
        if len(parts) < 2: bot.reply_to(m, "Usage: /esp_clear <device_id>"); return
        did = parts[1]
        dev = _load_devices().get(did)
        if not dev: bot.reply_to(m, f"Device {did} not found"); return
        if not _owner_ok(dev, m.from_user.id): bot.reply_to(m, "Not your device"); return
        bot.reply_to(m, f"{did}: {_send_cmd(did, 'clear') or 'no response'}")

    @bot.message_handler(commands=["esp_reboot"])
    def esp_reboot(m):
        parts = m.text.split()
        if len(parts) < 2: bot.reply_to(m, "Usage: /esp_reboot <device_id>"); return
        did = parts[1]
        dev = _load_devices().get(did)
        if not dev: bot.reply_to(m, f"Device {did} not found"); return
        if not _owner_ok(dev, m.from_user.id): bot.reply_to(m, "Not your device"); return
        bot.reply_to(m, f"{did}: {_send_cmd(did, 'reboot') or 'no response'}")

    @bot.message_handler(commands=["esp_led"])
    def esp_led(m):
        parts = m.text.split()
        if len(parts) < 4: bot.reply_to(m, "Usage: /esp_led <device_id> <pin> <0/1>"); return
        did, pin, val = parts[1], parts[2], parts[3]
        dev = _load_devices().get(did)
        if not dev: bot.reply_to(m, f"Device {did} not found"); return
        if not _owner_ok(dev, m.from_user.id): bot.reply_to(m, "Not your device"); return
        bot.reply_to(m, f"{did}: {_send_cmd(did, f'led {pin} {val}') or 'no response'}")

    @bot.message_handler(commands=["esp_color"])
    def esp_color(m):
        parts = m.text.split()
        if len(parts) < 3: bot.reply_to(m, "Usage: /esp_color <device_id> <hex>"); return
        did, hexval = parts[1], parts[2]
        dev = _load_devices().get(did)
        if not dev: bot.reply_to(m, f"Device {did} not found"); return
        if not _owner_ok(dev, m.from_user.id): bot.reply_to(m, "Not your device"); return
        bot.reply_to(m, f"{did}: {_send_cmd(did, f'color {hexval}') or 'no response'}")

    register_sync(bot)
    _start_action_listener(bot)
    print("ESP control commands loaded")

def _handle_action(bot, uid, device_id, payload):
    """Handle an action triggered on the device."""
    parts = payload.split(":", 2)
    action = parts[0].strip().lower() if parts else ""
    print(f"[ESP_ACTION] {device_id} uid={uid} action={action}")

    if action == "sync":
        state = build_sync_payload(uid)
        import json as _j
        _send_cmd(device_id, "sync " + _j.dumps(state, ensure_ascii=False))
        return

    if action == "stake":
        amount = parts[1] if len(parts) > 1 else "100"
        bot.send_message(uid, f"\U0001F4F1 Device requested: *stake {amount}*\nUse `/stake {amount}` in chat to confirm.", parse_mode="Markdown")
        return

    if action == "invite":
        bot.send_message(uid, "\U0001F4F1 Device requested: *invite link*\nUse `/referral` to generate it.")
        return

    if action == "learn":
        bot.send_message(uid, "\U0001F4F1 Device requested: *continue course*\nUse `/courses` to see your options.")
        return

    if action == "menu":
        bot.send_message(uid, "\U0001F4F1 Device requested: *main menu*\nUse `/help`.")
        return

    bot.send_message(uid, f"\U0001F4F1 Device {device_id}: unknown action `{payload}`")


def _start_action_listener(bot):
    """Start a background MQTT listener for device actions."""
    def worker():
        import time as _t
        while True:
            try:
                import paho.mqtt.client as mqtt
                import json as _j
                from pathlib import Path as _P

                def on_connect(c, u, f, rc):
                    c.subscribe("slh/esp/+/action")
                    print("[ESP_ACTION] listener connected")

                def on_message(c, u, msg):
                    try:
                        topic = msg.topic
                        payload = msg.payload.decode("utf-8", "ignore")
                        parts = topic.split("/")
                        if len(parts) < 4 or parts[0] != "slh" or parts[1] != "esp" or parts[3] != "action":
                            return
                        device_id = parts[2]
                        try:
                            raw = _j.loads(_P("state/devices.json").read_text(encoding="utf-8"))
                            dev = (raw.get("devices", {}) or {}).get(device_id)
                        except Exception as e:
                            print(f"[ESP_ACTION] read error: {e}")
                            return
                        if not dev:
                            print(f"[ESP_ACTION] unknown device {device_id}")
                            return
                        uid = str(dev.get("owner", ""))
                        if not uid:
                            print(f"[ESP_ACTION] no owner on {device_id}")
                            return
                        _handle_action(bot, uid, device_id, payload)
                    except Exception as e:
                        print(f"[ESP_ACTION] handler error: {e}")

                c = mqtt.Client()
                c.on_connect = on_connect
                c.on_message = on_message
                c.connect("broker.hivemq.com", 1883, 60)
                c.loop_forever()
            except Exception as e:
                print(f"[ESP_ACTION] listener died: {e}, restart in 10s")
                _t.sleep(10)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    print("[ESP_ACTION] listener started")


def build_sync_payload(uid):
    """Build the full wallet state for a device."""
    import json
    from pathlib import Path
    try:
        db = json.loads(Path("state/db.json").read_text(encoding="utf-8"))
    except Exception:
        return {"error": "db_unavailable"}

    user = db.get("users", {}).get(str(uid), {})
    wallet = user.get("wallet", {})
    credits = float(wallet.get("credits", 0) or 0)
    slh = float(wallet.get("token_balance", 0) or 0)
    staked = float(wallet.get("staked", 0) or 0)

    gamif = user.get("gamification", {})
    points = int(gamif.get("points", 0) or 0)
    level = int(gamif.get("level", 0) or 0)

    addrs = user.get("payment_addresses", {})
    ton_addr = addrs.get("ton_usdt", "-") or "-"
    bnb_addr = addrs.get("bnb", "") or "not bound"

    devices = user.get("devices", []) or []
    devices_list = ", ".join([str(d) for d in devices[:3]]) if devices else "none"

    active_course = user.get("active_course")
    referral = user.get("referral", {}) or {}
    has_referral = bool(referral.get("referred_by"))

    if credits > 1000 and staked == 0:
        nba = "Stake Now"
    elif not has_referral:
        nba = "Invite Friend"
    elif active_course:
        nba = "Continue Course"
    else:
        nba = "Explore Market"

    return {
        "credits": round(credits, 2),
        "slh": round(slh, 2),
        "staked": round(staked, 2),
        "points": points,
        "level": level,
        "ton": ton_addr,
        "bnb": bnb_addr,
        "devices_list": devices_list,
        "next_action": nba,
    }


def register_sync(bot):
    @bot.message_handler(commands=["esp_sync"])
    def esp_sync(m):
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /esp_sync <device_id>")
            return
        did = parts[1]
        dev = _load_devices().get(did)
        if not dev: bot.reply_to(m, f"Device {did} not found"); return
        if not _owner_ok(dev, m.from_user.id): bot.reply_to(m, "Not your device"); return
        state = build_sync_payload(m.from_user.id)
        import json as _j
        r = _send_cmd(did, "sync " + _j.dumps(state, ensure_ascii=False))

        # Mirror: same data shown on the device, sent to Telegram
        mirror = (
            "\U0001F4CA *SLH Wallet Mirror*\n"
            f"\U0001F4B0 Credits: `{state.get('credits', 0)}`\n"
            f"\U0001F4B5 SLH: `{state.get('slh', 0)}`\n"
            f"\U0001F512 Staked: `{state.get('staked', 0)}`\n"
            f"\U0001F3AF Next: `{state.get('next_action', '-')}`\n"
            f"\U0001F4F1 Device: `{did}`\n"
            f"\U0001F4E1 Response: `{r or 'no response'}`"
        )
        try:
            bot.send_message(m.chat.id, mirror, parse_mode="Markdown")
        except Exception:
            bot.send_message(m.chat.id, mirror)
