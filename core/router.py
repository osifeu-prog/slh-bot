import json

class Router:
    def __init__(self):
        self.routes = {}

    def register(self, event_type, handler):
        self.routes.setdefault(event_type, []).append(handler)

    def dispatch(self, event_type, payload, kernel):
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except:
                payload = {"value": payload}
        for h in self.routes.get(event_type, []):
            try:
                h(payload, kernel)
            except Exception as e:
                print("[ROUTER ERROR]", event_type, e)
