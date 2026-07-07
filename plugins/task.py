class TaskPlugin:
    name = "task"

    def on_start(self, k):
        self.k = k
        self.bot = getattr(k, 'bot', None)
        k.state.setdefault("tasks", [])
        k.bus.register("task_create", self.create)
        k.bus.register("task_list", self.list)

    def create(self, p):
        task = p.get("task") or p.get("value") or str(p)
        self.k.state["tasks"].append(task)
        chat = p.get("chat")
        if chat and self.bot:
            self.bot.send_message(chat, f"✅ נוצרה משימה: {task}")

    def list(self, p):
        chat = p.get("chat")
        tasks = self.k.state.get("tasks", [])
        if tasks:
            msg = "📋 המשימות שלך:\n" + "\n".join(f"• {t}" for t in tasks)
        else:
            msg = "📭 אין משימות עדיין. /task create <טקסט>"
        if chat and self.bot:
            self.bot.send_message(chat, msg)
