class TaskPlugin:
    name = "task"

    def on_start(self, k):
        self.k = k
        k.state.setdefault("tasks", [])
        k.bus.register("task_create", self.create)
        k.bus.register("task_list", self.list)

    def create(self, p):
        task = p.get("task") or p.get("value") or str(p)
        self.k.state["tasks"].append(task)
        if hasattr(self.k, 'telegram') and self.k.telegram and p.get("chat"):
            self.k.telegram.reply(p["chat"], f"✅ {task}")

    def list(self, p):
        chat = p.get("chat")
        tasks = self.k.state.get("tasks", [])
        msg = "📋 Tasks:\n" + "\n".join(tasks) if tasks else "No tasks"
        if hasattr(self.k, 'telegram') and self.k.telegram and chat:
            self.k.telegram.reply(chat, msg)
