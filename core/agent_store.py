class InMemoryAgentStore:
    def __init__(self):
        self._data = {}

    def create(self, name, role="agent"):
        import time
        aid = str(int(time.time() * 1000))
        self._data[aid] = {
            "name": name,
            "role": role,
            "state": "idle",
            "inbox": [],
            "history": [],
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "permissions": ["read"] if role != "admin" else ["read", "write", "admin"]
        }
        return aid

    def list(self):
        return [{"id": k, **v} for k, v in self._data.items()]

    def get(self, aid):
        return self._data.get(aid)

    def update_state(self, aid, state):
        import time
        agent = self._data.get(aid)
        if agent:
            agent["state"] = state
            agent["history"].append({
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "action": f"state_changed_to_{state}"
            })
            return True
        return False

    def send_message(self, aid, message):
        import time
        agent = self._data.get(aid)
        if agent:
            agent["inbox"].append({
                "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "message": message
            })
            return True
        return False
