from core.authority import is_owner
import state_manager


def register(bot):

    @bot.message_handler(commands=["botname"])
    def botname_cmd(msg):

        if not is_owner(msg):
            bot.reply_to(msg, "⛔ OWNER only.")
            return

        parts = msg.text.split(maxsplit=1)

        if len(parts) == 1:
            db = state_manager.load_db()
            system = db.get("system", {})
            bot.reply_to(
                msg,
                f"Current name: {system.get('bot_name', 'SLH OS AI')}\n"
                "Usage: /botname <new name>",
            )
            return

        new = parts[1].strip()

        def mutate(db):
            system = db.setdefault("system", {})
            old = system.get("bot_name", "SLH OS AI")
            system["bot_name"] = new
            system["owner"] = "Osif"
            system["description"] = "SLH OS AI"
            return old

        old = state_manager.atomic_update(mutate)

        bot.reply_to(
            msg,
            f"✅ Bot name changed\nOld: {old}\nNew: {new}",
        )


    @bot.message_handler(commands=["botinfo"])
    def botinfo_cmd(msg):

        db = state_manager.load_db()
        system = db.get("system", {})

        bot.reply_to(
            msg,
            f"🤖 {system.get('bot_name', 'SLH OS AI')}\n"
            f"👤 Owner: {system.get('owner', 'unknown')}\n"
            f"ℹ️ {system.get('description', '')}",
        )


    print("✅ bot_identity_handler loaded")
