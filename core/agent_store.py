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
