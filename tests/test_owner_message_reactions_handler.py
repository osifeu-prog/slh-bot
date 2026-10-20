from types import SimpleNamespace

from handlers import owner_message_reactions_handler as reactions


def test_choose_reaction_uses_supported_emoji_for_common_cases():
    assert reactions.choose_reaction("/check_exchange") == "👀"
    assert reactions.choose_reaction("AUDIT_STATUS: BLOCKED") == "🤔"
    assert reactions.choose_reaction("SLH_DIAG_OK") == "👍"
    assert reactions.choose_reaction("Can you help?") == "🤔"
    assert reactions.choose_reaction("Hello") == "🤝"


def _register_fake_bot(monkeypatch, env_value="1", fail_reactions=False):
    events = []

    class FakeBot:
        def __init__(self):
            self._next_message_id = 100

        def send_message(self, chat_id, text, **kwargs):
            events.append(("send", chat_id, text))
            self._next_message_id += 1
            chat_type = "private" if int(chat_id) > 0 else "supergroup"
            return SimpleNamespace(
                chat=SimpleNamespace(id=chat_id, type=chat_type),
                message_id=self._next_message_id,
                text=text,
            )

        def reply_to(self, message, text, **kwargs):
            # Mirrors pyTelegramBotAPI's reply helper, which delegates to send_message.
            return self.send_message(message.chat.id, text, **kwargs)

        def set_message_reaction(self, **kwargs):
            events.append(("reaction", kwargs))
            if fail_reactions:
                raise RuntimeError("simulated Telegram reaction error")

    monkeypatch.setattr(reactions, "is_owner", lambda uid: str(uid) == "12345")
    monkeypatch.setenv("SLH_OWNER_MESSAGE_REACTIONS", env_value)
    bot = FakeBot()
    assert reactions.register(bot, {"bot_name": "Me_ad_main"}) is True
    return bot, events


def _incoming_owner_message():
    return SimpleNamespace(
        from_user=SimpleNamespace(id=12345),
        chat=SimpleNamespace(id=12345, type="private"),
        message_id=77,
        text="AUDIT_STATUS: BLOCKED",
    )


def test_reacts_to_actual_bot_reply_not_the_incoming_owner_message(monkeypatch):
    bot, events = _register_fake_bot(monkeypatch)
    incoming = _incoming_owner_message()

    # Registering the feature must not react to incoming messages.
    assert events == []

    sent = bot.reply_to(incoming, "AUDIT_STATUS: BLOCKED")

    assert sent.message_id == 101
    assert [event[0] for event in events] == ["send", "reaction"]
    reaction = events[1][1]
    assert reaction["chat_id"] == 12345
    assert reaction["message_id"] == sent.message_id
    assert reaction["reaction"][0].to_dict() == {"type": "emoji", "emoji": "🤔"}


def test_send_message_reaction_is_limited_to_owner_private_chat(monkeypatch):
    bot, events = _register_fake_bot(monkeypatch)

    bot.send_message(22222, "Hello another user")
    bot.send_message(-100123, "Group status")

    assert [event[0] for event in events] == ["send", "send"]


def test_reactions_can_be_disabled_without_affecting_message_delivery(monkeypatch):
    bot, events = _register_fake_bot(monkeypatch, env_value="0")

    sent = bot.send_message(12345, "Everything passed.")

    assert sent.message_id == 101
    assert events == [("send", 12345, "Everything passed.")]


def test_reaction_error_does_not_hide_successfully_sent_reply(monkeypatch):
    bot, events = _register_fake_bot(monkeypatch, fail_reactions=True)

    sent = bot.send_message(12345, "Everything passed.")

    assert sent.message_id == 101
    assert [event[0] for event in events] == ["send", "reaction"]


def test_reaction_wrapper_is_idempotent(monkeypatch):
    bot, events = _register_fake_bot(monkeypatch)

    assert reactions.register(bot, {"bot_name": "Me_ad_main"}) is True
    bot.send_message(12345, "Hello")

    assert [event[0] for event in events] == ["send", "reaction"]


def test_reactions_are_not_installed_for_other_bots():
    class FakeBot:
        def send_message(self, *_args, **_kwargs):
            raise AssertionError("other bots must not be wrapped")

    assert reactions.register(FakeBot(), {"bot_name": "AnotherBot"}) is False
