import json
from pathlib import Path

DB_PATH = Path("state/db.json")


def load_db():
    with DB_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_db(db):
    with DB_PATH.open("w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def is_owner(uid):
    db = load_db()
    user = db.get("users", {}).get(str(uid), {})
    return user.get("role") == "OWNER"


def register(bot):

    @bot.message_handler(commands=["botname"])
    def botname_cmd(msg):
        if not is_owner(msg.from_user.id):
            bot.reply_to(msg, "⛔ רק OWNER יכול לשנות שם מערכת.")
            return

        parts = msg.text.split(maxsplit=1)

        db = load_db()
        system = db.setdefault("system", {})

        if len(parts) == 1:
            bot.reply_to(
                msg,
                f"🤖 שם נוכחי: {system.get('bot_name','SLH OS AI')}\n"
                "שימוש:\n/botname שם חדש"
            )
            return

        old = system.get("bot_name", "SLH OS AI")
        new = parts[1].strip()

    system["bot_name"] = new
    system["owner"] = user.get("name", "Osif")
    system["description"] = "?????? ????? ?? SLH OS"
    save_db(db)

        bot.reply_to(
            msg,
            f"✅ שם עודכן\nישן: {old}\nחדש: {new}"
        )


    @bot.message_handler(commands=["botinfo"])
    def botinfo_cmd(msg):
        db = load_db()
        system = db.get("system", {})

        bot.reply_to(
            msg,
            f"🤖 {system.get('bot_name','SLH OS AI')}\n"
            f"👑 Owner: {system.get('owner','unknown')}\n"
            f"🧠 {system.get('description','')}"
        )


    print("✅ bot_identity_handler loaded")
