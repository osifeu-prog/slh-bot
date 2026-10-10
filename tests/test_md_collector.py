from types import SimpleNamespace

import handlers.md_collector as md


OWNER_ID = 8789977826


def test_append_and_render_markdown_preserve_text_and_safe_code_fences():
    data = md._empty_buffer()
    data["active"] = True
    tick = chr(96)
    source = "print('ok')\n" + tick * 3 + "inside" + tick * 3
    assert md._append_message(
        data, text=source, kind="code", timestamp=1, message_id=7
    ) is None

    rendered = md.render_markdown(data["messages"])

    assert "Messages: 1" in rendered
    assert "print('ok')" in rendered
    assert tick * 3 + "inside" + tick * 3 in rendered
    # A code block containing three backticks must use a longer outer fence.
    assert tick * 4 + "python" in rendered
    assert "message_id" not in rendered


def test_append_enforces_message_limit_without_truncation(monkeypatch):
    monkeypatch.setattr(md, "MAX_MESSAGES", 1)
    data = md._empty_buffer()
    data["active"] = True

    assert md._append_message(data, text="first", kind="text") is None
    result = md._append_message(data, text="second", kind="text")

    assert result == "BUFFER_MESSAGE_LIMIT"
    assert data["active"] is False
    assert [item["text"] for item in data["messages"]] == ["first"]


def test_append_enforces_total_character_limit(monkeypatch):
    monkeypatch.setattr(md, "MAX_BUFFER_CHARS", 5)
    data = md._empty_buffer()
    data["active"] = True

    assert md._append_message(data, text="1234", kind="text") is None
    result = md._append_message(data, text="56", kind="text")

    assert result == "BUFFER_SIZE_LIMIT"
    assert data["active"] is False
    assert [item["text"] for item in data["messages"]] == ["1234"]


def test_buffer_round_trip_is_scoped_to_uid_and_storage_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(md, "STATE_DIR", tmp_path)
    original = md._empty_buffer()
    original.update(
        active=True,
        started_at="2026-10-10T00:00:00+00:00",
        messages=[{"t": 1, "kind": "text", "text": "hello", "message_id": 4}],
    )

    md._save_buffer(OWNER_ID, original)
    loaded = md._load_buffer(OWNER_ID)

    assert loaded == original
    assert md._buffer_path(OWNER_ID).exists()
    assert not md._buffer_path(9999999999).exists()


def test_buffer_rejects_non_numeric_uid():
    try:
        md._buffer_path("../other")
    except ValueError as exc:
        assert str(exc) == "INVALID_UID"
    else:
        raise AssertionError("non-numeric UID was accepted")


def test_capture_only_matches_active_owner_private_non_command_message(tmp_path, monkeypatch):
    monkeypatch.setattr(md, "STATE_DIR", tmp_path)
    data = md._empty_buffer()
    data["active"] = True
    md._save_buffer(OWNER_ID, data)

    owner_private = SimpleNamespace(
        from_user=SimpleNamespace(id=OWNER_ID),
        chat=SimpleNamespace(type="private"),
        text="save this",
    )
    owner_command = SimpleNamespace(
        from_user=SimpleNamespace(id=OWNER_ID),
        chat=SimpleNamespace(type="private"),
        text="/md_stop",
    )
    group_message = SimpleNamespace(
        from_user=SimpleNamespace(id=OWNER_ID),
        chat=SimpleNamespace(type="group"),
        text="do not capture",
    )
    other_user = SimpleNamespace(
        from_user=SimpleNamespace(id=12345),
        chat=SimpleNamespace(type="private"),
        text="do not capture",
    )

    assert md._is_capture_message(owner_private) is True
    assert md._is_capture_message(owner_command) is False
    assert md._is_capture_message(group_message) is False
    assert md._is_capture_message(other_user) is False


def test_registration_installs_capture_handler_before_command_handlers():
    class FakeBot:
        def __init__(self):
            self.handlers = []

        def message_handler(self, **kwargs):
            def decorate(fn):
                self.handlers.append((kwargs, fn))
                return fn
            return decorate

    bot = FakeBot()
    md.register(bot)

    assert bot.handlers[0][0].get("func") is md._is_capture_message
    commands = {
        command
        for kwargs, _fn in bot.handlers
        for command in (kwargs.get("commands") or [])
    }
    assert {"md", "md_start", "md_stop", "md_add", "md_last", "md_status", "md_cancel", "md_clear"} <= commands


def test_secret_redaction_catches_common_credentials_before_storage():
    groq_token = "gsk_" + ("A" * 40)
    bot_token = "123456789:" + ("B" * 35)
    sample = (
        f"GROQ_API_KEY={groq_token}\n"
        f"BOT_TOKEN={bot_token}\n"
        "Authorization: Bearer abc.def.ghi\n"
        "-----BEGIN PRIVATE KEY-----\nexample-private-material\n-----END PRIVATE KEY-----"
    )
    safe = md._redact_secrets(sample)

    assert groq_token not in safe
    assert bot_token not in safe
    assert "abc.def.ghi" not in safe
    assert "example-private-material" not in safe
    assert safe.count("[REDACTED") >= 4


def test_append_redacts_before_persistence():
    data = md._empty_buffer()
    secret = "gsk_" + ("Z" * 40)

    assert md._append_message(data, text=f"GROQ_API_KEY={secret}", kind="text") is None

    assert secret not in data["messages"][0]["text"]
    assert "[REDACTED]" in data["messages"][0]["text"]


def test_capture_continues_to_later_handlers_after_saving(tmp_path, monkeypatch):
    from telebot.handler_backends import ContinueHandling

    monkeypatch.setattr(md, "STATE_DIR", tmp_path)
    data = md._empty_buffer()
    data["active"] = True
    md._save_buffer(OWNER_ID, data)

    class FakeBot:
        def __init__(self):
            self.handlers = []

        def message_handler(self, **kwargs):
            def decorate(fn):
                self.handlers.append((kwargs, fn))
                return fn
            return decorate

        def reply_to(self, *_args, **_kwargs):
            return None

    bot = FakeBot()
    md.register(bot)
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=OWNER_ID),
        chat=SimpleNamespace(type="private", id=OWNER_ID),
        text="ordinary conversation message",
        caption=None,
        entities=[],
        caption_entities=[],
        date=1,
        message_id=9,
    )

    result = bot.handlers[0][1](message)

    assert isinstance(result, ContinueHandling)
    assert md._load_buffer(OWNER_ID)["messages"][-1]["text"] == "ordinary conversation message"
