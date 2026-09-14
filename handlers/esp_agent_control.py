"""ESP Agent control - send build/flash commands via MQTT to local agent."""
import json
import time
import paho.mqtt.client as mqtt
from core.authority import is_owner


from core.mqtt_config import BROKER as _MB
BROKER = _MB
from core.mqtt_config import PORT as _MP
PORT = _MP
DEFAULT_AGENT = "AGENT_OSIF2"


def _send_task(agent_id, action, timeout=300):
    """Send a task to the agent and wait for result."""
    task_topic = f"slh/agent/{agent_id}/task"
    result_topic = f"slh/agent/{agent_id}/result"
    task_id = f"t{int(time.time())}"
    result = {"data": None}

    def on_connect(c, u, f, rc):
        c.subscribe(result_topic)

    def on_message(c, u, msg):
        try:
            payload = json.loads(msg.payload.decode())
            if payload.get("id") == task_id:
                result["data"] = payload
        except Exception:
            pass

    c = mqtt.Client()
    c.on_connect = on_connect
    c.on_message = on_message
    __import__("core.mqtt_config",fromlist=["apply"]).apply(c)
    c.connect(BROKER, PORT, 60)
    c.loop_start()
    time.sleep(0.8)
    c.publish(task_topic, json.dumps({"id": task_id, "action": action}))

    deadline = time.time() + timeout
    while time.time() < deadline:
        if result["data"] is not None:
            break
        time.sleep(1)

    c.loop_stop()
    try:
        c.disconnect()
    except Exception:
        pass
    return result["data"]


def register(bot, context=None):

    @bot.message_handler(commands=["esp_flash"])
    def esp_flash(m):
        if not is_owner(m.from_user.id):
            bot.reply_to(m, "OWNER only")
            return
        bot.reply_to(m, f"Pushing firmware to ESP via {DEFAULT_AGENT}...\nThis takes ~30-60s.")
        r = _send_task(DEFAULT_AGENT, "esp.flash", timeout=180)
        if not r:
            bot.reply_to(m, "No response from agent (timeout or agent offline)")
            return
        ok = r.get("ok", False)
        out = r.get("output", "")[-1500:]
        prefix = "OK" if ok else "FAIL"
        bot.reply_to(m, f"[{prefix}] rc={r.get('rc')}\n\n{out}")

    @bot.message_handler(commands=["esp_compile"])
    def esp_compile(m):
        if not is_owner(m.from_user.id):
            bot.reply_to(m, "OWNER only")
            return
        bot.reply_to(m, f"Compiling via {DEFAULT_AGENT}...")
        r = _send_task(DEFAULT_AGENT, "esp.compile", timeout=180)
        if not r:
            bot.reply_to(m, "No response from agent")
            return
        ok = r.get("ok", False)
        out = r.get("output", "")[-1500:]
        prefix = "OK" if ok else "FAIL"
        bot.reply_to(m, f"[{prefix}] rc={r.get('rc')}\n\n{out}")

    @bot.message_handler(commands=["esp_ports"])
    def esp_ports(m):
        if not is_owner(m.from_user.id):
            bot.reply_to(m, "OWNER only")
            return
        r = _send_task(DEFAULT_AGENT, "esp.ports", timeout=30)
        if not r:
            bot.reply_to(m, "No response from agent")
            return
        out = r.get("output", "(empty)")
        bot.reply_to(m, f"Ports:\n{out}")

    @bot.message_handler(commands=["esp_chipid"])
    def esp_chipid(m):
        if not is_owner(m.from_user.id):
            bot.reply_to(m, "OWNER only")
            return
        bot.reply_to(m, "Reading chip info...")
        r = _send_task(DEFAULT_AGENT, "esp.chip_id", timeout=30)
        if not r:
            bot.reply_to(m, "No response from agent")
            return
        out = r.get("output", "")[-1000:]
        bot.reply_to(m, f"Chip info:\n{out}")

    @bot.message_handler(commands=["agent_status"])
    def agent_status(m):
        if not is_owner(m.from_user.id):
            bot.reply_to(m, "OWNER only")
            return
        # Ping the agent with a trivial task
        r = _send_task(DEFAULT_AGENT, "esp.ports", timeout=15)
        if r:
            bot.reply_to(m, f"{DEFAULT_AGENT}: online (responded in time)")
        else:
            bot.reply_to(m, f"{DEFAULT_AGENT}: OFFLINE or not responding")

    print("ESP agent commands loaded")