import json, datetime, os, uuid

DB_PATH = os.path.expanduser("~/slh_clean/db.json")

def load_db():
    with open(DB_PATH) as f:
        return json.load(f)

def save_db(db):
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def init(bot):
    @bot.message_handler(commands=['leaderboard'])
    def smart_leaderboard(m):
        db = load_db()
        users = db.get("users", {})
        if not users:
            bot.reply_to(m, "📭 No users yet.")
            return
        sorted_users = sorted(users.items(), key=lambda x: x[1].get("points", 0), reverse=True)
        msg = "🏆 **Leaderboard:**\n"
        for i, (uid, data) in enumerate(sorted_users[:10], 1):
            name = db.get("students", {}).get(uid, {}).get("name", uid)
            points = data.get("points", 0)
            active_proj = db.get("active_projects", {}).get(uid)
            proj_info = ""
            agent_str = ""
            if active_proj:
                proj_path = os.path.expanduser(f"~/slh_clean/projects/{active_proj}")
                tasks_file = os.path.join(proj_path, "tasks", "TASKS.md")
                agents_file = os.path.join(proj_path, "agents", "AGENTS.md")
                if os.path.exists(tasks_file):
                    with open(tasks_file) as f:
                        lines = f.readlines()
                    total = len([l for l in lines if l.strip().startswith("- [ ]") or l.strip().startswith("- [x]")])
                    done = len([l for l in lines if l.strip().startswith("- [x]")])
                    proj_info = f" | Project: {done}/{total}"
                if os.path.exists(agents_file):
                    with open(agents_file) as f:
                        agent_count = f.read().count("**Agent:**")
                    agent_str = f" | Agents: {agent_count}" if agent_count else ""
            msg += f"{i}. {name} – {points} pts{proj_info}{agent_str}\n"
        bot.reply_to(m, msg, parse_mode="Markdown")

    @bot.message_handler(commands=['vote'])
    def vote_handler(m):
        args = m.text.split(maxsplit=2)
        if len(args) == 1:
            bot.reply_to(m, "Usage: /vote <question> | <opt1> | <opt2> ...\nOr: /vote <id> <option#>")
        elif len(args) == 2:
            vote_id = args[1]
            db = load_db()
            vote = db.get("votes", {}).get(vote_id)
            if not vote:
                bot.reply_to(m, "❌ Vote not found.")
                return
            msg = f"📊 {vote['question']}\n"
            total = sum(vote["options"].values()) or 1
            for opt, count in vote["options"].items():
                bar = "█" * int(count / total * 10)
                msg += f"{opt}: {count} {bar}\n"
            bot.reply_to(m, msg)
        else:
            full_text = args[2] if len(args) > 2 else ""
            parts = full_text.split("|")
            if len(parts) >= 2:
                question = parts[0].strip()
                options = [opt.strip() for opt in parts[1:]]
                db = load_db()
                vote_id = str(uuid.uuid4())[:8]
                db.setdefault("votes", {})[vote_id] = {
                    "question": question,
                    "options": {opt: 0 for opt in options},
                    "voters": {},
                    "created": datetime.datetime.now().isoformat()
                }
                save_db(db)
                msg = f"📊 **Vote started:** {question}\n"
                for i, opt in enumerate(options, 1):
                    msg += f"{i}. {opt}\n"
                msg += f"\nVote with: /vote {vote_id} <option_number>"
                bot.reply_to(m, msg, parse_mode="Markdown")
            else:
                try:
                    vote_id, choice = args[1], args[2]
                    uid = str(m.chat.id)
                    db = load_db()
                    vote = db.get("votes", {}).get(vote_id)
                    if not vote:
                        bot.reply_to(m, "❌ Vote not found.")
                        return
                    if uid in vote.get("voters", {}):
                        bot.reply_to(m, "⚠️ You already voted.")
                        return
                    choice_idx = int(choice) - 1
                    option = list(vote["options"].keys())[choice_idx]
                    vote["options"][option] += 1
                    vote["voters"][uid] = option
                    save_db(db)
                    bot.reply_to(m, f"✅ Voted: {option}")
                except:
                    bot.reply_to(m, "❌ Invalid input. Usage: /vote <id> <option#>")

    @bot.message_handler(commands=['lost'])
    def report_lost(m):
        args = m.text.split(maxsplit=1)
        if len(args) < 2:
            bot.reply_to(m, "❌ Usage: /lost <what are you stuck on?>")
            return
        uid = str(m.chat.id)
        db = load_db()
        report = {
            "user": uid,
            "text": args[1],
            "time": datetime.datetime.now().isoformat()
        }
        db.setdefault("lost_reports", []).append(report)
        save_db(db)
        bot.reply_to(m, "📝 Your struggle has been recorded. We'll help soon!")
