import subprocess, json, os

def init(bot):
    @bot.message_handler(commands=['monitor'])
    def monitor(m):
        if str(m.chat.id) != "8789977826":  # admin only
            bot.reply_to(m, "❌ Admin only")
            return
        lines = ["📊 **SYSTEM MONITOR**", ""]
        # תהליכים
        try:
            ps_out = subprocess.check_output(["ps", "aux", "--sort=-%mem"], text=True).splitlines()
            lines.append("**🔹 Processes (top 5 by memory):**")
            for l in ps_out[1:6]:
                parts = l.split()
                if len(parts) >= 11:
                    lines.append(f"`{parts[1]:>6} {parts[2]:>4} {parts[10][:30]}`")
        except:
            lines.append("❌ ps failed")
        lines.append("")
        # זיכרון
        try:
            mem = subprocess.check_output(["free", "-m"], text=True).splitlines()
            lines.append("**🔹 Memory:**")
            for l in mem[0:3]:
                lines.append(f"`{l}`")
        except:
            lines.append("❌ free failed")
        lines.append("")
        # דיסק
        try:
            disk = subprocess.check_output(["df", "-h", "."], text=True).splitlines()
            if len(disk) > 1:
                lines.append("**🔹 Disk:**")
                lines.append(f"`{disk[1]}`")
        except:
            lines.append("❌ df failed")
        lines.append("")
        # Ollama
        try:
            ollama_ps = subprocess.check_output(["pgrep", "-f", "ollama"], text=True).strip()
            if ollama_ps:
                ollama_list = subprocess.check_output(["ollama", "list"], text=True)
                lines.append("**🔹 Ollama:** ✅ Running")
                lines.append(f"```\n{ollama_list[:300]}\n```")
            else:
                lines.append("**🔹 Ollama:** ❌ Not running")
        except:
            lines.append("**🔹 Ollama:** ❌ Not running")
        lines.append("")
        # סוכנים
        try:
            with open("db.json") as f:
                db = json.load(f)
            agents = db.get("agents", {})
            if agents:
                lines.append("**🔹 Agents:**")
                for name, data in agents.items():
                    inbox = len(data.get("inbox", []))
                    outbox = len(data.get("outbox", []))
                    lines.append(f"- {name}: inbox={inbox}, outbox={outbox}")
            else:
                lines.append("**🔹 Agents:** None")
        except:
            lines.append("**🔹 Agents:** Error")
        lines.append("")
        # לוג אחרון
        try:
            tail = subprocess.check_output(["tail", "-n", "5", "logs/bot.log"], text=True)
            lines.append("**🔹 Last bot logs:**")
            lines.append(f"```\n{tail[:500]}\n```")
        except:
            lines.append("**🔹 Logs:** unavailable")
        lines.append("")
        # שגיאות אחרונות
        try:
            err = subprocess.check_output(["tail", "-n", "3", "logs/error.log"], text=True)
            if err.strip():
                lines.append("**🔹 Last errors:**")
                lines.append(f"```\n{err[:500]}\n```")
        except:
            pass
        bot.reply_to(m, "\n".join(lines), parse_mode="Markdown")
