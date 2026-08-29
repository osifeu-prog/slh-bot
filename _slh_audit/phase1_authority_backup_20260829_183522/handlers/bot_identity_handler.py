import json
from pathlib import Path

from core.authority import is_owner

DB_PATH = Path("state/db.json")


def load_db():
    with DB_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_db(db):
    with DB_PATH.open("w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def register(bot):

    @bot.message_handler(commands=["botname"])
    def botname_cmd(msg):

        if not is_owner(msg):
            bot.reply_to(msg, "⛔ OWNER only.")
            return

        parts = msg.text.split(maxsplit=1)

        db = load_db()
        system = db.setdefault("system", {})

        if len(parts) == 1:
            bot.reply_to(
                msg,
                f"Current name: {system.get('bot_name', 'SLH OS AI')}\n"
                "Usage: /botname <new name>",
            )
            return

        old = system.get("bot_name", "SLH OS AI")
        new = parts[1].strip()

        system["bot_name"] = new
        system["owner"] = "Osif"
        system["description"] = "SLH OS AI"

        save_db(db)

        bot.reply_to(
            msg,
            f"✅ Bot name changed\nOld: {old}\nNew: {new}",
        )


    @bot.message_handler(commands=["botinfo"])
    def botinfo_cmd(msg):

        db = load_db()
        system = db.get("system", {})

        bot.reply_to(
            msg,
            f"🤖 {system.get('bot_name', 'SLH OS AI')}\n"
            f"👤 Owner: {system.get('owner', 'unknown')}\n"
            f"ℹ️ {system.get('description', '')}",
        )


    print("✅ bot_identity_handler loaded")
