import os, subprocess

def register(bot):
    @bot.message_handler(commands=['git'])
    def git_cmd(msg):
        if str(msg.from_user.id) != os.getenv("ADMIN_ID", "8789977826"):
            bot.reply_to(msg, "⛔ Admin only")
            return
        args = msg.text.split()
        if len(args) < 2 or args[1] not in ("commit", "status"):
            bot.reply_to(msg, "Usage: /git commit <message>")
            return
        if args[1] == "status":
            out = subprocess.check_output("git status --short", shell=True, text=True)
            bot.reply_to(msg, f"📋 Git status:\n{out or 'clean'}")
            return
        # commit & push
        msg_text = " ".join(args[2:])
        if not msg_text:
            bot.reply_to(msg, "Missing commit message")
            return
        try:
            subprocess.run("git add -A", shell=True, check=True)
            subprocess.run(f'git commit -m "{msg_text}"', shell=True, check=True)
            token = os.getenv("GIT_TOKEN")
            if not token:
                bot.reply_to(msg, "❌ GIT_TOKEN not set")
                return
            # push using token
            remote_url = f"https://{token}@github.com/osifeu-prog/slh-bot.git"
            subprocess.run(f"git remote set-url origin {remote_url}", shell=True, check=True)
            subprocess.run("git push origin main", shell=True, check=True)
            bot.reply_to(msg, f"✅ Pushed: {msg_text}")
        except subprocess.CalledProcessError as e:
            bot.reply_to(msg, f"❌ Git error: {e}")
