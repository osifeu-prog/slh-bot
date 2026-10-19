from types import SimpleNamespace

from telebot.handler_backends import ContinueHandling

from handlers import owner_message_reactions_handler as reactions


def test_choose_reaction_uses_supported_emoji_for_common_cases():
    assert reactions.choose_reaction(SimpleNamespace(text="/check_exchange")) == "👀"
    assert reactions.choose_reaction(SimpleNamespace(text="AUDIT_STATUS: BLOCKED")) == "🤔"
    assert reactions.choose_reaction(SimpleNamespace(text="SLH_DIAG_OK")) == "👍"
    assert reactions.choose_reaction(SimpleNamespace(text="Can you help?")) == "🤔"
    assert reactions.choose_reaction(SimpleNamespace(text="Hello")) == "🤝"


def _register_fake_bot(monkeypatch, env_value="1"):
    registered = {}
    calls = []

    class FakeBot:
        def message_handler(self, **kwargs):
            def decorator(fn):
                registered.update(kwargs=kwargs, fn=fn)
                return fn
            return decorator

        def set_message_reaction(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(reactions, "is_owner", lambda uid: uid == 12345)
    monkeypatch.setenv("SLH_OWNER_MESSAGE_REACTIONS", env_value)
    bot = FakeBot()
    assert reactions.register(bot, {"bot_name": "Me_ad_main"}) is True
    return bot, registered, calls


def _message(uid, chat_id, chat_type, message_id, text):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=uid),
        chat=SimpleNamespace(id=chat_id, type=chat_type),
        message_id=message_id,
        text=text,
    )


def test_first_handler_reacts_to_owner_private_message_and_continues(monkeypatch):
    bot, registered, calls = _register_fake_bot(monkeypatch)
    owner_private = _message(12345, 12345, "private", 77, "AUDIT_STATUS: BLOCKED")
    other_private = _message(22222, 22222, "private", 78, "hello")
    owner_group = _message(12345, -100, "supergroup", 79, "hello")

    assert registered["kwargs"]["content_types"]
    assert registered["kwargs"]["func"](owner_private) is True
    assert registered["fn"](owner_private).__class__ is ContinueHandling

    registered["fn"](other_private)
    registered["fn"](owner_group)

    assert len(calls) == 1
    assert calls[0]["chat_id"] == 12345
    assert calls[0]["message_id"] == 77
    assert calls[0]["reaction"][0].to_dict() == {"type": "emoji", "emoji": "🤔"}


def test_reactions_can_be_disabled_without_blocking_handlers(monkeypatch):
    bot, registered, calls = _register_fake_bot(monkeypatch, env_value="0")
    message = _message(12345, 12345, "private", 80, "hello")

    assert registered["fn"](message).__class__ is ContinueHandling
    assert calls == []


def test_reaction_handler_is_not_registered_for_other_bots():
    class FakeBot:
        def message_handler(self, **kwargs):
            raise AssertionError("other bots must not register owner reactions")

    assert reactions.register(FakeBot(), {"bot_name": "AnotherBot"}) is False
