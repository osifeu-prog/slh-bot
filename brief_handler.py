import json
import state_manager

def init(bot):
    @bot.message_handler(commands=['brief'])
    def brief(m):
        lines = ["📋 SLH OS — Brief\n"]

        try:
            with open("journal.json", encoding="utf-8") as f:
                journal = json.load(f)
            lines.append("🕒 Last 3 journal entries:")
            for entry in journal[-3:]:
                text = entry.get("text", "")
                short = text[:200] + "..." if len(text) > 200 else text
                lines.append(f"• {entry.get('time','')}\n  {short}")
        except Exception as e:
            lines.append(f"Journal error: {e}")

        try:
            with open("ROADMAP.md", encoding="utf-8") as f:
                roadmap = f.read()
            open_items = roadmap.count("- [ ]")
            done_items = roadmap.count("- [x]")
            lines.append(f"\n📌 Roadmap: {open_items} open items, {done_items} done")
        except Exception as e:
            lines.append(f"Roadmap error: {e}")

        try:
            db = state_manager.load_db()
            users = len(db.get("students", {}))
            agents = len(db.get("agents", {}))
            tasks = len(db.get("tasks", {}))
            lines.append(f"\n📊 Status: Users {users}, Agents {agents}, Tasks {tasks}")
        except Exception as e:
            lines.append(f"Status error: {e}")

        lines.append("\nUse /roadmap for full plan, /journal_read for full history.")

        msg = "\n".join(lines)
        for i in range(0, len(msg), 3800):
            bot.send_message(m.chat.id, msg[i:i+3800])
