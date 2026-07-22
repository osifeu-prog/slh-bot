import json, os
from datetime import datetime

BOARD_FILE = "state/missions/board.json"

def _load():
    if not os.path.exists(BOARD_FILE):
        return []
    with open(BOARD_FILE, "r") as f:
        data = json.load(f)
    return data.get("missions", [])

def _save(missions):
    os.makedirs(os.path.dirname(BOARD_FILE), exist_ok=True)
    board = {"missions": missions}
    with open(BOARD_FILE, "w") as f:
        json.dump(board, f, indent=2, ensure_ascii=False)

def list_tasks():
    """מחזיר רק משימות במצב open (תצוגה נקייה)"""
    missions = _load()
    return [m for m in missions if m.get("status") == "open"]

def add_task(text):
    missions = _load()
    new_id = max([m.get("id", 0) for m in missions], default=0) + 1
    task = {
        "id": new_id,
        "desc": text,
        "status": "open",
        "assigned_to": None,
        "reward": 0,
        "created": datetime.now().isoformat()
    }
    missions.append(task)
    _save(missions)
    return task

def update_task_status(task_id, status):
    missions = _load()
    for m in missions:
        if m["id"] == task_id:
            m["status"] = status
            _save(missions)
            return m
    return None
