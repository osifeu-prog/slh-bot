@bot.message_handler(commands=['diagnose'])
def diagnose(m):
    import re
    issues = []
    with open("bot.py", "r") as f:
        code = f.read()
    try:
        compile(code, "bot.py", "exec")
    except SyntaxError as e:
        issues.append(f"❌ Syntax error at line {e.lineno}: {e.msg}")
    loop_pos = code.find("while True:")
    if loop_pos != -1:
        after_loop = code[loop_pos:]
        if "@bot.message_handler" in after_loop:
            handlers = re.findall(r"@bot\.message_handler\(commands=\['(\w+)'\]\)", after_loop)
            if handlers:
    all_handlers = re.findall(r"@bot\.message_handler\(commands=\['(\w+)'\]\)", code)
    dupes = [h for h in set(all_handlers) if all_handlers.count(h) > 1]
    if dupes:
        issues.append(f"⚠️ Duplicate handlers: {', '.join('/'+h for h in dupes)}")
    if issues:
        bot.reply_to(m, "🔍 Issues found:\n" + "\n".join(issues))
    else:
        bot.reply_to(m, "✅ No issues detected.")
