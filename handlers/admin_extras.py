import json, os, subprocess, glob, tempfile, time

def register(bot, context):
    @bot.message_handler(commands=['health'])
    def health(m):
        try:
            with open('state/db.json') as f:
                d = json.load(f)
            users = len(d.get('users', {}))
            agents = len(d.get('agents', {}))
            bot.reply_to(m, f"✅ Health OK – Users: {users}, Agents: {agents}")
        except:
            bot.reply_to(m, "❌ DB check failed")

    @bot.message_handler(commands=['status'])
    def status(m):
        env = os.environ.get("RAILWAY_ENVIRONMENT", "local")
        bot.reply_to(m, f"🟢 SLH Bot Online | Railway: {env} | /admin for more")

    @bot.message_handler(commands=['megadiag'])
    def megadiag(m):
        from system_diagnostics import check_logo_presence
        lines = ["📊 MEGA DIAGNOSTICS", ""]
        lines.append("Disk usage:")
        try:
            import shutil
            total, used, free = shutil.disk_usage("/app" if os.path.isdir("/app") else ".")
            lines.append(f"  Total: {total//1024//1024} MB, Used: {used//1024//1024} MB, Free: {free//1024//1024} MB")
        except:
            lines.append("  (not available)")
        bot.reply_to(m, "\n".join(lines))

    @bot.message_handler(commands=['backup'])
    def backup(m):
        try:
            with open('state/db.json', 'rb') as f:
                bot.send_document(m.chat.id, f, visible_file_name='db_backup.json')
        except Exception as e:
            bot.reply_to(m, f"❌ Backup failed: {e}")

    @bot.message_handler(commands=['clean'])
    def clean(m):
        patterns = ['*.pyc', '__pycache__']
        count = 0
        for pattern in patterns:
            for f in glob.glob(f'**/{pattern}', recursive=True):
                try:
                    if os.path.isdir(f):
                        os.rmdir(f)
                    else:
                        os.remove(f)
                    count += 1
                except:
                    pass
        bot.reply_to(m, f"🧹 Cleaned {count} temp files")

    @bot.message_handler(commands=['vote'])
    def vote(m):
        parts = m.text.split(' ', 1)
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /vote <topic>|<option1,option2>")
            return
        topic, opts = parts[1].split('|')
        opts = [o.strip() for o in opts.split(',')]
        bot.reply_to(m, f"🗳 Vote \"{topic}\" created with options: {', '.join(opts)}. Not yet implemented.")

    @bot.message_handler(commands=['results'])
    def results(m):
        bot.reply_to(m, "📊 No active vote. (voting engine not connected)")

    print("✅ admin_extras loaded")
