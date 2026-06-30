
import os, py_compile, re, sys, subprocess

def register(bot):
    @bot.message_handler(commands=['diagnose'])
    def diagnose_cmd(m):
        cwd = os.path.expanduser("~/slh_clean")
        issues = []
        bot_path = os.path.join(cwd, "bot.py")
        if os.path.exists(bot_path):
            issues.append("✅ bot.py exists")
            try:
                py_compile.compile(bot_path, doraise=True)
                issues.append("✅ Syntax OK")
            except py_compile.PyCompileError as e:
                issues.append(f"❌ Syntax error: {e}")
        else:
            issues.append("❌ bot.py missing")
        with open(bot_path) as f:
            code = f.read()
        loop_pos = code.find("while True:")
        if loop_pos != -1:
            after_loop = code[loop_pos:]
            if "@bot.message_handler" in after_loop:
                handlers = re.findall(r"@bot\.message_handler\(commands=\['(\w+)'\]\)", after_loop)
                if handlers:
                    issues.append(f"⚠️ Handlers after while True: {', '.join('/'+h for h in handlers)}")
                else:
                    issues.append("✅ No handlers after while True")
            else:
                issues.append("✅ No handlers after while True")
        else:
            issues.append("❌ while True loop not found")
        db_path = os.path.join(cwd, "db.json")
        issues.append("✅ db.json exists" if os.path.exists(db_path) else "❌ db.json missing")
        bot.reply_to(m, "\n".join(issues))

    @bot.message_handler(commands=['fix'])
    def fix_cmd(m):
        cwd = os.path.expanduser("~/slh_clean")
        bot_path = os.path.join(cwd, "bot.py")
        with open(bot_path) as f:
            code = f.read()
        loop_pos = code.find("while True:")
        if loop_pos == -1:
            bot.reply_to(m, "❌ No while True loop found")
            return
        after_loop = code[loop_pos:]
        if "@bot.message_handler" not in after_loop:
            bot.reply_to(m, "✅ No misplaced handlers")
            return
        handler_blocks = re.findall(r"(@bot\.message_handler\(commands=\[.*?\]\).*?)(?=\n@bot|\n\n@bot|\Z)", after_loop, re.DOTALL)
        if not handler_blocks:
            bot.reply_to(m, "❌ Could not extract handlers")
            return
        for block in handler_blocks:
            code = code.replace(block, "")
        code = code.replace("while True:", "\n".join(handler_blocks) + "\nwhile True:")
        with open(bot_path, "w") as f:
            f.write(code)
        subprocess.Popen([sys.executable, "-B", bot_path])
        os._exit(0)
        bot.reply_to(m, "✅ Handlers moved and bot restarted")
