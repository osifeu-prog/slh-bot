"""Canonical Bot Factory orchestration.

This layer owns bot lifecycle metadata and delegates Railway operations to the
existing Railway control plane. It never stores Telegram secrets.
"""

from core import bot_registry
from core import railway_control


def create_bot(name, owner_id, bot_key=None, template="generic"):
    return bot_registry.create_bot(
        name=name,
        owner_id=owner_id,
        bot_key=bot_key,
        template=template,
    )


def get_bot(identifier):
    return bot_registry.get_bot(identifier)


def list_bots(owner_id=None):
    return bot_registry.list_bots(owner_id=owner_id)


def update_bot(identifier, **changes):
    return bot_registry.update_bot(identifier, **changes)


def delete_bot(identifier):
    return bot_registry.delete_bot(identifier)


def status_bot(identifier):
    bot = get_bot(identifier)
    if bot is None:
        raise KeyError(f"Bot '{identifier}' not found")

    result = dict(bot)
    if bot.get("railway_service_id") and bot.get("railway_environment_id"):
        # The registry stores an explicit Railway target binding. Live
        # deployment state belongs to Railway's deployment API; do not call
        # an optional/nonexistent helper and misreport a bot as unavailable.
        result["railway"] = {
            "status": "bound",
            "service_id": bot["railway_service_id"],
            "environment_id": bot["railway_environment_id"],
        }

    return result


def deploy_bot(identifier):
    bot = get_bot(identifier)
    if bot is None:
        raise KeyError(f"Bot '{identifier}' not found")

    service_id = bot.get("railway_service_id")
    environment_id = bot.get("railway_environment_id")
    if not service_id or not environment_id:
        raise ValueError(
            "Bot has no Railway service/environment binding; "
            "bind a managed Railway target before deployment"
        )

    result = railway_control.deploy(
        service_id,
        environment_id,
    )
    updated = update_bot(identifier, status="deploying")
    return {"bot": updated, "deployment": result}
