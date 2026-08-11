import json
import time

DB = "state/db.json"


def load_db():
    with open(DB, encoding="utf-8") as f:
        db = json.load(f)

    # Canonical voting state is a dict keyed by proposal id.
    # Older state may contain votes as [] or another list-based structure.
    votes = db.get("votes")

    if isinstance(votes, list):
        normalized = {}

        for item in votes:
            if not isinstance(item, dict):
                continue

            pid = str(item.get("id") or len(normalized) + 1)

            normalized[pid] = {
                "text": item.get("text") or item.get("title") or "",
                "by": str(item.get("by") or item.get("creator") or ""),
                "time": item.get("time", time.time()),
                "yes": int(item.get("yes", 0) or 0),
                "no": int(item.get("no", 0) or 0),
                "voters": item.get("voters", {})
                if isinstance(item.get("voters", {}), dict)
                else {},
            }

        db["votes"] = normalized

    elif votes is None:
        db["votes"] = {}

    elif not isinstance(votes, dict):
        db["votes"] = {}

    return db


def save_db(db):
    with open(DB, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


def register(bot):
    @bot.message_handler(commands=["register_ai"])
    def register_ai(m):
        uid = str(m.from_user.id)

        if uid != "8789977826":
            bot.reply_to(m, "Only owner can register AI agents")
            return

        db = load_db()
        agents = db.setdefault("agents", {})

        ai_agents = [
            ("ClaudeAgent", "Anthropic Claude AI assistant"),
            ("GroqAgent", "Groq-powered AI agent"),
            ("GeminiAgent", "Google Gemini AI agent"),
            ("OpenAI_Agent", "OpenAI GPT agent"),
        ]

        created = []

        for name, desc in ai_agents:
            if name not in [a.get("name") for a in agents.values()]:
                numeric_ids = [
                    int(k) for k in agents.keys() if str(k).isdigit()
                ]

                nid = str(max(numeric_ids + [0]) + 1)

                agents[nid] = {
                    "name": name,
                    "role": "ai_assistant",
                    "state": "idle",
                    "inbox": [],
                    "description": desc,
                    "permissions": ["read", "vote", "propose"],
                }

                created.append(name)

        db["agents"] = agents
        save_db(db)

        if created:
            bot.reply_to(
                m,
                f"AI agents created: {', '.join(created)}"
            )
        else:
            bot.reply_to(
                m,
                "All AI agents already exist"
            )

    @bot.message_handler(commands=["propose"])
    def propose(m):
        parts = m.text.split(maxsplit=1)

        if len(parts) < 2:
            bot.reply_to(m, "Usage: /propose <text>")
            return

        proposal_text = parts[1]

        db = load_db()
        votes = db.setdefault("votes", {})

        if not isinstance(votes, dict):
            votes = {}
            db["votes"] = votes

        numeric_ids = [
            int(k) for k in votes.keys() if str(k).isdigit()
        ]

        pid = str(max(numeric_ids + [0]) + 1)

        votes[pid] = {
            "text": proposal_text,
            "by": str(m.from_user.id),
            "time": time.time(),
            "yes": 0,
            "no": 0,
            "voters": {},
        }

        save_db(db)

        bot.reply_to(
            m,
            f"Proposal #{pid} created: {proposal_text}"
        )

    @bot.message_handler(commands=["vote"])
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
            bot.reply_to(m, "Proposal not found")
            return

        voter = str(m.from_user.id)

        if voter in proposal["voters"]:
            bot.reply_to(m, "You already voted")
            return

        proposal["voters"][voter] = choice
        proposal[choice] = proposal.get(choice, 0) + 1

        save_db(db)

        bot.reply_to(
            m,
            f"Voted {choice} on proposal #{pid}"
        )

    @bot.message_handler(commands=["tally"])
    def tally(m):
        parts = m.text.split()

        if len(parts) < 2:
            bot.reply_to(m, "Usage: /tally <id>")
            return

        pid = parts[1]

        db = load_db()
        proposal = db.get("votes", {}).get(pid)

        if not proposal:
            bot.reply_to(m, "Proposal not found")
            return

        bot.reply_to(
            m,
            f"Proposal #{pid}: {proposal['text']}\n"
            f"Yes: {proposal.get('yes', 0)} | "
            f"No: {proposal.get('no', 0)}"
        )
