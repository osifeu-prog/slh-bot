import json
import os
from datetime import datetime

TASK_FILE = "state/tasks.json"

def _load():
    if not os.path.exists(TASK_FILE):
        return []
    try:
        with open(TASK_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def _save(tasks):
    os.makedirs("state", exist_ok=True)
    with open(TASK_FILE, "w") as f:
        json.dump(tasks, f, indent=2, ensure_ascii=False)

def add_task(text):
    tasks = _load()
    task = {
        "id": len(tasks) + 1,
        "text": text,
        "created": datetime.now().isoformat(),
        "status": "open"
    }
    tasks.append(task)
    _save(tasks)
    return task

def list_tasks():
    return _load()
