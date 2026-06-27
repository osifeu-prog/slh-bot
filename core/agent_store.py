import json, os, time

class AgentStore:
    def __init__(self, path="agents.json"):
        self.path = path
        if not os.path.exists(path):
            with open(path, "w") as f:
                json.dump({}, f)

    def _load(self):
        with open(self.path) as f:
            return json.load(f)

    def _save(self, data):
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)

    def create(self, name, role="agent"):
        data = self._load()
        aid = str(int(time.time() * 1000))
        data[aid] = {
            "name": name,
            "role": role,
            "state": "idle",
            "inbox": [],
            "history": [],
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "permissions": ["read"] if role != "admin" else ["read", "write", "admin"]
        }
        self._save(data)
        return aid

    def list(self):
        return [{"id": k, **v} for k, v in self._load().items()]

    def get(self, aid):
        return self._load().get(aid)

    def update_state(self, aid, state):
        data = self._load()
        if aid in data:
            data[aid]["state"] = state
            data[aid]["history"].append({
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "action": f"state_changed_to_{state}"
            })
            self._save(data)
            return True
        return False

    def send_message(self, aid, message):
        data = self._load()
        if aid in data:
            data[aid]["inbox"].append({
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "message": message
            })
            self._save(data)
            return True
        return False
