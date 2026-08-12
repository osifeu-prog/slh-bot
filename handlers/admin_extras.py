import json, os, subprocess, glob, tempfile, time

def register(bot, context):
    @bot.message_handler(commands=['health'])
    def health(m):
        try:
            with open('state/db.json') as f:
                d = json.load(f)
            users = len(d.get('users', {}))
            agents = len(d.get('agents', {}))
            bot.reply_to(m, f"ג… Health OK ג€“ Users: {users}, Agents: {agents}")
        except:
            bot.reply_to(m, "ג DB check failed")

    @bot.message_handler(commands=['status'])
    def status(m):
        env = os.environ.get("RAILWAY_ENVIRONMENT", "local")
        bot.reply_to(m, f"נ¢ SLH Bot Online | Railway: {env} | /admin for more")

    @bot.message_handler(commands=['megadiag'])
    def megadiag(m):
        lines = ["נ“ MEGA DIAGNOSTICS", ""]
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
            bot.reply_to(m, f"ג Backup failed: {e}")

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
        bot.reply_to(m, f"נ§¹ Cleaned {count} temp files")

    @bot.message_handler(commands=['results'])
    def results(m):
        bot.reply_to(m, "נ“ No active vote. (voting engine not connected)")

    print("ג… admin_extras loaded")

