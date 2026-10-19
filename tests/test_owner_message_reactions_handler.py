from types import SimpleNamespace

from handlers import owner_message_reactions_handler as reactions


def test_choose_reaction_uses_supported_emoji_for_common_cases():
    assert reactions.choose_reaction(SimpleNamespace(text="/check_exchange")) == "👀"
    assert reactions.choose_reaction(SimpleNamespace(text="AUDIT_STATUS: BLOCKED")) == "🤔"
    assert reactions.choose_reaction(SimpleNamespace(text="SLH_DIAG_OK")) == "👍"
    assert reactions.choose_reaction(SimpleNamespace(text="Can you help?")) == "🤔"
    assert reactions.choose_reaction(SimpleNamespace(text="Hello")) == "🤝"


def test_middleware_reacts_to_owner_private_messages_only(monkeypatch):
    registered = {}
    calls = []

    class FakeBot:
        def middleware_handler(self, **kwargs):
            def decorator(fn):
                registered.update(kwargs=kwargs, fn=fn)
                return fn
            return decorator

        def set_message_reaction(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(reactions, "is_owner", lambda uid: uid == 12345)
    monkeypatch.setenv("SLH_OWNER_MESSAGE_REACTIONS", "1")

    bot = FakeBot()
    assert reactions.register(bot, {"bot_name": "Me_ad_main"}) is True
    assert registered["kwargs"] == {"update_types": ["message"]}

    owner_private = SimpleNamespace(
        from_user=SimpleNamespace(id=12345),
        chat=SimpleNamespace(id=12345, type="private"),
        message_id=77,
        text="AUDIT_STATUS: BLOCKED",
    )
    other_private = SimpleNamespace(
        from_user=SimpleNamespace(id=22222),
        chat=SimpleNamespace(id=22222, type="private"),
        message_id=78,
        text="hello",
    )
    owner_group = SimpleNamespace(
        from_user=SimpleNamespace(id=12345),
        chat=SimpleNamespace(id=-100, type="supergroup"),
        message_id=79,
        text="hello",
    )

    registered["fn"](bot, owner_private)
    registered["fn"](bot, other_private)
    registered["fn"](bot, owner_group)

    assert len(calls) == 1
    assert calls[0]["chat_id"] == 12345
    assert calls[0]["message_id"] == 77
    assert calls[0]["reaction"][0].to_dict() == {"type": "emoji", "emoji": "🤔"}


def test_middleware_can_be_disabled(monkeypatch):
    registered = {}

    class FakeBot:
        def middleware_handler(self, **kwargs):
            def decorator(fn):
                registered["fn"] = fn
                return fn
            return decorator

        def set_message_reaction(self, **kwargs):
            raise AssertionError("reactions must be disabled")

    monkeypatch.setattr(reactions, "is_owner", lambda uid: True)
    monkeypatch.setenv("SLH_OWNER_MESSAGE_REACTIONS", "0")
    bot = FakeBot()
    assert reactions.register(bot, {"bot_name": "Me_ad_main"}) is True

    message = SimpleNamespace(
        from_user=SimpleNamespace(id=12345),
        chat=SimpleNamespace(id=12345, type="private"),
        message_id=80,
        text="hello",
    )
    registered["fn"](bot, message)


def test_middleware_is_not_registered_for_other_bots():
    class FakeBot:
        def middleware_handler(self, **kwargs):
            raise AssertionError("other bots must not register owner reactions")

    assert reactions.register(FakeBot(), {"bot_name": "AnotherBot"}) is False
