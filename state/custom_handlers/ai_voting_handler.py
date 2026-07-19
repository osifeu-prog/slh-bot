import json, time

DB = "state/db.json"

def load_db():
    with open(DB) as f:
        return json.load(f)
def save_db(db):
    with open(DB, "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def register(bot):
    @bot.message_handler(commands=['register_ai'])
    def register_ai(m):
        uid = str(m.from_user.id)
        if uid != "8789977826":
            bot.reply_to(m, "❌ Only owner can register AI agents")
            return
        db = load_db()
        agents = db.setdefault("agents", {})
        ai_agents = [
            ("ClaudeAgent", "Anthropic Claude AI assistant"),
            ("GroqAgent", "Groq-powered AI agent"),
            ("GeminiAgent", "Google Gemini AI agent"),
            ("OpenAI_Agent", "OpenAI GPT agent")
        ]
        created = []
        for name, desc in ai_agents:
            if name not in [a.get("name") for a in agents.values()]:
                nid = str(max([int(k) for k in agents.keys() if k.isdigit()] + [0]) + 1)
                agents[nid] = {"name": name, "role": "ai_assistant", "state": "idle", "inbox": [], "description": desc, "permissions": ["read", "vote", "propose"]}
                created.append(name)
        db["agents"] = agents
        save_db(db)
        bot.reply_to(m, f"✅ AI agents created: {', '.join(created)}" if created else "ℹ️ All AI agents already exist")

    @bot.message_handler(commands=['propose'])
    def propose(m):
        parts = m.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /propose <text>")
            return
        proposal_text = parts[1]
        db = load_db()
        votes = db.setdefault("votes", {})
        pid = str(len(votes) + 1)
        votes[pid] = {"text": proposal_text, "by": str(m.from_user.id), "time": time.time(), "yes": 0, "no": 0, "voters": {}}
        save_db(db)
        bot.reply_to(m, f"📢 Proposal #{pid} created: {proposal_text}")

    @bot.message_handler(commands=['vote'])
    def vote(m):
        parts = m.text.split()
        if len(parts) < 3:
            bot.reply_to(m, "Usage: /vote <id> <yes/no>")
            return
        pid = parts[1]
        choice = parts[2].lower()
        if choice not in ("yes", "no"):
            bot.reply_to(m, "Only 'yes' or 'no' allowed")
            return
        db = load_db()
        proposal = db.get("votes", {}).get(pid)
        if not proposal:
            bot.reply_to(m, "❌ Proposal not found")
            return
        voter = str(m.from_user.id)
        if voter in proposal["voters"]:
            bot.reply_to(m, "❌ You already voted")
            return
        proposal["voters"][voter] = choice
        proposal[choice] = proposal.get(choice, 0) + 1
        save_db(db)
        bot.reply_to(m, f"✅ Voted {choice} on proposal #{pid}")

    @bot.message_handler(commands=['tally'])
    def tally(m):
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /tally <id>")
            return
        pid = parts[1]
        db = load_db()
        proposal = db.get("votes", {}).get(pid)
        if not proposal:
            bot.reply_to(m, "❌ Proposal not found")
            return
        bot.reply_to(m, f"📊 Proposal #{pid}: {proposal['text']}\n✅ Yes: {proposal.get('yes',0)} | ❌ No: {proposal.get('no',0)}")
