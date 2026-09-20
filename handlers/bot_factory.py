"""Canonical Telegram Bot Factory commands.

Bot metadata is stored in the canonical DB. Telegram/Railway secrets are never
accepted as command arguments and are never written to the DB.
"""

from core.authority import is_owner
from core import bot_factory


def _owner_id(message):
    return str(message.from_user.id)


def register(bot):
    @bot.message_handler(commands=["botfactory", "botlist"])
    def botlist_cmd(m):
        if not is_owner(m):
            return
        bots = bot_factory.list_bots(owner_id=_owner_id(m))
        if not bots:
            bot.reply_to(m, "BOT FACTORY\n\nNo bots registered.")
            return
        lines = ["BOT FACTORY", ""]
        for item in bots:
            lines.append(
                f"• {item['id']} · {item['name']} · "
                f"{item.get('template', 'generic')} · {item.get('status', 'unknown')}"
            )
        bot.reply_to(m, "\n".join(lines)[:3900])

    @bot.message_handler(commands=["botcreate"])
    def botcreate_cmd(m):
        if not is_owner(m):
            return
        parts = (m.text or "").split()
        if len(parts) < 2:
            bot.reply_to(m, "usage: /botcreate <name> [template]")
            return
        name = parts[1]
        template = parts[2] if len(parts) > 2 else "generic"
        try:
            record = bot_factory.create_bot(
                name=name,
                owner_id=_owner_id(m),
                template=template,
            )
            bot.reply_to(
                m,
                "BOT CREATED\n"
                f"id={record['id']}\n"
                f"name={record['name']}\n"
                f"template={record['template']}\n"
                f"status={record['status']}",
            )
        except Exception as exc:
            bot.reply_to(m, f"botcreate failed: {type(exc).__name__}: {str(exc)[:250]}")

    @bot.message_handler(commands=["botstatus"])
    def botstatus_cmd(m):
        if not is_owner(m):
            return
        parts = (m.text or "").split()
        if len(parts) < 2:
            bot.reply_to(m, "usage: /botstatus <bot-id|name|bot-key>")
            return
        try:
            record = bot_factory.status_bot(parts[1])
            bot.reply_to(
                m,
                "BOT STATUS\n"
                f"id={record['id']}\n"
                f"name={record['name']}\n"
                f"template={record['template']}\n"
                f"status={record['status']}\n"
                f"railway={record.get('railway', 'not-bound')}",
            )
        except Exception as exc:
            bot.reply_to(m, f"botstatus failed: {type(exc).__name__}: {str(exc)[:250]}")

    @bot.message_handler(commands=["botdeploy"])
    def botdeploy_cmd(m):
        if not is_owner(m):
            return
        parts = (m.text or "").split()
        if len(parts) < 2:
            bot.reply_to(m, "usage: /botdeploy <bot-id|name|bot-key>")
            return
        try:
            result = bot_factory.deploy_bot(parts[1])
            bot.reply_to(
                m,
                "BOT DEPLOY QUEUED\n"
                f"id={result['bot']['id']}\n"
                f"deployment={result['deployment']}",
            )
        except Exception as exc:
            bot.reply_to(m, f"botdeploy failed: {type(exc).__name__}: {str(exc)[:300]}")
