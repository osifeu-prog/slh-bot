import json, time
import state_manager
from core.event_bus import EventBus

def on_agent_task(payload):
    agent_name = payload.get("agent")
    task_text = payload.get("task")
    print(f"📋 Handling task for {agent_name}: {task_text}")
    try:
        agents = state_manager.get_agents()
        if agent_name in agents:
            agents[agent_name].setdefault("inbox", []).append({
                "time": time.time(),
                "message": f"📋 New task: {task_text}"
            })
            state_manager.set_agents(agents)
            print(f"Updated agent inbox for {agent_name}")
    except Exception as e:
        print("agent update error:", e)

def register(bot=None):
    EventBus.subscribe("agent_task", on_agent_task)
    print("✅ Task listener registered (dual write)")
