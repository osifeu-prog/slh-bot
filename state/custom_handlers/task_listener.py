import json, time
from core.event_bus import EventBus

def on_agent_task(payload):
    agent_name = payload.get("agent")
    task_text = payload.get("task")
    print(f"📋 Handling task for {agent_name}: {task_text}")
    try:
        with open("state/agents.json", "r") as f:
            agents = json.load(f)
        if agent_name in agents:
            agents[agent_name].setdefault("inbox", []).append({
                "time": time.time(),
                "message": f"📋 New task: {task_text}"
            })
            with open("state/agents.json", "w") as f:
                json.dump(agents, f, indent=2, ensure_ascii=False)
            print(f"Updated agents.json inbox for {agent_name}")
    except Exception as e:
        print("agents.json update error:", e)

def register(bot=None):
    EventBus.subscribe("agent_task", on_agent_task)
    print("✅ Task listener registered (dual write)")
