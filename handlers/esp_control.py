import json, time, os, threading
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

from core.mqtt_config import BROKER as _MB
MQTT_BROKER = _MB
from core.mqtt_config import PORT as _MP
MQTT_PORT = _MP

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
    __import__("core.mqtt_config",fromlist=["apply"]).apply(c)
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
    register_screen(bot)
    print("ESP control commands loaded")

def _handle_action(bot, uid, device_id, payload):
    """Handle an action triggered on the device."""
    parts = payload.split(":", 2)
    action = parts[0].strip().lower() if parts else ""
    print(f"[ESP_ACTION] {device_id} uid={uid} action={action}")

    if action == "sync":
        state = build_sync_payload(uid)
        import json as _j
        r = _send_cmd(device_id, "sync " + _j.dumps(state, ensure_ascii=False))
        mirror = (
            "\U0001F4CA *SLH Wallet (via device)*\n"
            f"\U0001F4B0 Credits: `{state.get('credits', 0)}`\n"
            f"\U0001F4B5 SLH: `{state.get('slh', 0)}`\n"
            f"\U0001F512 Staked: `{state.get('staked', 0)}`\n"
            f"\U0001F3AE Points: `{state.get('points', 0)}` (L{state.get('level', 0)})\n"
            f"\U0001F48E TON: `{state.get('ton', '-')}`\n"
            f"\U0001F3AF Next: `{state.get('next_action', '-')}`\n"
            f"\U0001F4E1 Response: `{r or 'no response'}`"
        )
        try:
            bot.send_message(uid, mirror, parse_mode="Markdown")
        except Exception:
            bot.send_message(uid, mirror)
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
                __import__("core.mqtt_config",fromlist=["apply"]).apply(c)
                c.connect(_MB, _MP, 60)
                c.loop_forever()
            except Exception as e:
                print(f"[ESP_ACTION] listener died: {e}, restart in 10s")
                _t.sleep(10)

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    print("[ESP_ACTION] listener started")




_BAL_CACHE_FILE = "state/esp_balance_cache.json"


def _get_balance_cache():
    try:
        with open(_BAL_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_balance_cache(cache):
    try:
        with open(_BAL_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f)
    except Exception:
        pass


def _fetch_ton_balance(address):
    """Fetch TON balance from public API."""
    if not address: return None
    try:
        import requests
        r = requests.get("https://tonapi.io/v2/accounts/" + address, timeout=5)
        if r.status_code == 200:
            return round(float(r.json().get("balance", 0)) / 1e9, 4)
    except Exception as e:
        print(f"[BAL] ton error: {e}")
    return None


def _fetch_ton_usdt_balance(address):
    """Fetch USDT (jetton) balance on TON."""
    if not address: return None
    try:
        import requests
        # USDT jetton master on TON
        USDT_MASTER = "EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs"
        url = f"https://tonapi.io/v2/accounts/{address}/jettons/{USDT_MASTER}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            bal = data.get("balance", 0)
            decimals = int(data.get("jetton", {}).get("decimals", 6))
            return round(float(bal) / (10 ** decimals), 4)
    except Exception as e:
        print(f"[BAL] usdt error: {e}")
    return None


def _fetch_bnb_balance(address):
    """Fetch BNB balance via public BSC RPC."""
    if not address: return None
    try:
        from web3 import Web3
        w3 = Web3(Web3.HTTPProvider("https://bsc-dataseed.binance.org/"))
        bal = w3.eth.get_balance(Web3.to_checksum_address(address))
        return round(bal / 1e18, 6)
    except Exception as e:
        print(f"[BAL] bnb error: {e}")
    return None


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

    # Fetch on-chain balances (cached to avoid slow responses)
    now_ts = time.time()
    cache_key = str(uid)
    cache = _get_balance_cache()
    if cache.get(cache_key) and now_ts - cache[cache_key].get("ts", 0) < 120:
        cached = cache[cache_key]
        ton_bal = cached.get("ton")
        usdt_bal = cached.get("usdt")
        bnb_bal = cached.get("bnb")
    else:
        ton_bal = _fetch_ton_balance(ton_addr) if ton_addr and ton_addr != "-" else None
        usdt_bal = _fetch_ton_usdt_balance(ton_addr) if ton_addr and ton_addr != "-" else None
        bnb_bal = _fetch_bnb_balance(bnb_addr) if bnb_addr and bnb_addr != "not bound" else None
        cache[cache_key] = {"ts": now_ts, "ton": ton_bal, "usdt": usdt_bal, "bnb": bnb_bal}
        _save_balance_cache(cache)

    return {
        "credits": round(credits, 2),
        "slh": round(slh, 2),
        "staked": round(staked, 2),
        "points": points,
        "level": level,
        "ton": ton_addr,
        "bnb": bnb_addr,
        "ton_bal": ton_bal if ton_bal is not None else 0,
        "usdt_bal": usdt_bal if usdt_bal is not None else 0,
        "bnb_bal": bnb_bal if bnb_bal is not None else 0,
        "eth_bal": 0,
        "btc_bal": 0,
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


def _ascii_wallet(state):
    """Render wallet as ASCII art."""
    t = state.get("tab", 0)
    mode = state.get("mode", "active")
    if mode == "screensaver":
        return (
            "```\n"
            "+--------------------------------+\n"
            "|  [*]                    [*]   |\n"
            "|   o    o                      |\n"
            "|        -                      |\n"
            "|     = SLH =                   |\n"
            "|   SECURE EDGE DEVICE          |\n"
            "|   touch to wake               |\n"
            "+--------------------------------+\n"
            "```"
        )
    tab_names = ["Wallet", "Earn", "Devices", "Info"]
    top = f"| {tab_names[0]:<7}|{tab_names[1]:<6}|{tab_names[2]:<8}|{tab_names[3]:<6}|"
    sep = "+--------------------------------+"
    if t == 0:
        body = (
            f"| SLH SYSTEM                     |\n"
            f"| Credits  {state.get('credits', 0):>18} |\n"
            f"| SLH      {state.get('slh', 0):>18} |\n"
            f"| Staked   {state.get('staked', 0):>12} P:{state.get('points', 0):<3}L{state.get('level', 0)}|\n"
            f"+--------------------------------+\n"
            f"| OTHER ASSETS                   |\n"
            f"| TON   {state.get('ton_bal', 0):<10} USDT  {state.get('usdt_bal', 0):<8}|\n"
            f"| BNB   {state.get('bnb_bal', 0):<10} ETH   {state.get('eth_bal', 0):<8}|\n"
            f"| BTC   {state.get('btc_bal', 0):<10}              |\n"
            f"|                                |\n"
            f"| [Next: {state.get('nba', '-'):<22}] |"
        )
    elif t == 1:
        body = (
            f"| EARN - Tap to act              |\n"
            f"|   > Stake Credits              |\n"
            f"|   > Invite Friend              |\n"
            f"|   > Continue Course            |\n"
            f"|   > Refresh Wallet             |\n"
            f"|                                |\n"
            f"| [Next: {state.get('nba', '-'):<22}] |"
        )
    elif t == 2:
        body = (
            f"| DEVICES                        |\n"
            f"| This: ESP32_14335C6C32C0       |\n"
            f"| IP:   {state.get('ip', '-'):<24} |\n"
            f"| RSSI: {state.get('rssi', 0)} dBm                  |\n"
            f"| Uptime: {state.get('uptime', 0)}s                    |"
        )
    else:
        body = (
            f"| INFO                           |\n"
            f"| Firmware: SLH OS v0.5          |\n"
            f"| IP: {state.get('ip', '-'):<27} |\n"
            f"| RSSI: {state.get('rssi', 0)} dBm                  |\n"
            f"| Uptime: {state.get('uptime', 0)}s                    |"
        )
    return f"```\n{sep}\n{top}\n{sep}\n{body}\n{sep}\n```"


def register_screen(bot):
    @bot.message_handler(commands=["esp_view"])
    def esp_view(m):
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /esp_view <device_id>")
            return
        did = parts[1]
        dev = _load_devices().get(did)
        if not dev: bot.reply_to(m, f"Device {did} not found"); return
        if not _owner_ok(dev, m.from_user.id): bot.reply_to(m, "Not your device"); return

        # send screen command and wait for response
        resp_topic = f"slh/esp/{did}/response"
        cmd_topic = f"slh/esp/{did}/command"
        import paho.mqtt.client as mqtt
        import json as _j
        result = {"data": None}
        def on_connect(c, u, f, rc):
            c.subscribe(resp_topic)
        def on_message(c, u, msg):
            try:
                result["data"] = _j.loads(msg.payload.decode())
            except Exception:
                pass
            try: c.disconnect()
            except: pass
        c = mqtt.Client()
        c.on_connect = on_connect
        c.on_message = on_message
        __import__("core.mqtt_config",fromlist=["apply"]).apply(c)
        c.connect(_MB, _MP, 60)
        c.loop_start()
        import time as _t
        _t.sleep(0.5)
        c.publish(cmd_topic, "screen")
        for _ in range(12):
            if result["data"] is not None: break
            _t.sleep(0.5)
        c.loop_stop()
        try: c.disconnect()
        except: pass
        if result["data"] is None:
            bot.reply_to(m, "No response from device")
            return
        ascii_art = _ascii_wallet(result["data"])
        try:
            bot.send_message(m.chat.id, f"*Screen on {did}*\n{ascii_art}", parse_mode="Markdown")
        except Exception as e:
            bot.send_message(m.chat.id, f"Screen on {did}\n{ascii_art}")


