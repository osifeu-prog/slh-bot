import types
from datetime import datetime, timedelta, timezone

import handlers.music_academy_invite_handler as target
from core.identity import OWNER_TELEGRAM_ID


class FakeBot:
    def __init__(self, member_status="administrator"):
        self.handlers = {}
        self.sent = []
        self.replies = []
        self.member_status = member_status

    def message_handler(self, commands):
        def decorator(fn):
            for command in commands:
                self.handlers[command] = fn
            return fn
        return decorator

    def reply_to(self, message, text):
        self.replies.append((message, text))

    def send_message(self, chat_id, text, **kwargs):
        self.sent.append((str(chat_id), text, kwargs))

    def get_chat_member(self, chat_id, user_id):
        return types.SimpleNamespace(status=self.member_status)


def message(command_text, *, uid=None, chat_type="private", chat_id=12345, title=None):
    return types.SimpleNamespace(
        text=command_text,
        from_user=types.SimpleNamespace(id=int(OWNER_TELEGRAM_ID) if uid is None else uid),
        chat=types.SimpleNamespace(id=chat_id, type=chat_type, title=title, username=None),
    )


def install_db(monkeypatch, initial=None):
    db = initial if initial is not None else {}
    monkeypatch.setattr(target.state_manager, "load_db", lambda: db)

    def atomic_update(fn):
        result = fn(db)
        return result
    monkeypatch.setattr(target.state_manager, "atomic_update", atomic_update)
    return db


def test_preview_does_not_send_and_shows_recipient_counts(monkeypatch):
    db = install_db(monkeypatch, {
        target.OPTED_USERS_KEY: {"111": {"opted_in": True}, "222": {"opted_in": False}},
        target.OPTED_GROUPS_KEY: {"-1001": {"opted_in": True}},
    })
    bot = FakeBot()
    target.register(bot)

    bot.handlers["music_invite"](message("/music_invite preview"))

    assert bot.sent == []
    reply = bot.replies[-1][1]
    assert "לא נשלחה הודעה" in reply
    assert "נמענים פרטיים שהסכימו: 1" in reply
    assert "קבוצות שאישרו: 1" in reply
    assert db[target.CAMPAIGN_KEY]["status"] == "PREPARED"


def test_confirm_sends_only_to_explicit_opt_ins_and_marks_campaign(monkeypatch):
    db = install_db(monkeypatch, {
        target.OPTED_USERS_KEY: {
            "111": {"opted_in": True},
            "222": {"opted_in": False},
        },
        target.OPTED_GROUPS_KEY: {
            "-1001": {"opted_in": True},
            "-1002": {"opted_in": False},
        },
    })
    bot = FakeBot()
    target.register(bot)

    bot.handlers["music_invite"](message("/music_invite preview"))
    preview = bot.replies[-1][1]
    token = preview.split("אסימון אישור חד־פעמי: ")[1].splitlines()[0]
    bot.handlers["music_invite"](message("/music_invite confirm " + token))

    assert [entry[0] for entry in bot.sent] == ["111", "-1001"]
    assert all("Exchange" not in entry[1] and "מסחר" not in entry[1] for entry in bot.sent)
    assert db[target.CAMPAIGN_KEY]["status"] == "SENT"
    assert db[target.CAMPAIGN_KEY]["last_result"] == {
        "sent_users": 1, "sent_groups": 1, "failed_users": 0, "failed_groups": 0
    }


def test_unsubscribed_after_preview_is_not_sent(monkeypatch):
    db = install_db(monkeypatch, {
        target.OPTED_USERS_KEY: {"111": {"opted_in": True}},
        target.OPTED_GROUPS_KEY: {},
    })
    bot = FakeBot()
    target.register(bot)
    bot.handlers["music_invite"](message("/music_invite preview"))
    token = bot.replies[-1][1].split("אסימון אישור חד־פעמי: ")[1].splitlines()[0]
    db[target.OPTED_USERS_KEY]["111"]["opted_in"] = False

    bot.handlers["music_invite"](message("/music_invite confirm " + token))

    assert bot.sent == []
    assert db[target.CAMPAIGN_KEY]["status"] == "SENT"


def test_expired_preview_is_rejected(monkeypatch):
    db = install_db(monkeypatch, {
        target.CAMPAIGN_KEY: {
            "status": "PREPARED", "token": "ABC12345",
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            "user_targets": ["111"], "group_targets": [],
            "sent_user_ids": [], "sent_group_ids": [],
        },
        target.OPTED_USERS_KEY: {"111": {"opted_in": True}},
        target.OPTED_GROUPS_KEY: {},
    })
    bot = FakeBot()
    target.register(bot)
    bot.handlers["music_invite"](message("/music_invite confirm ABC12345"))
    assert bot.sent == []
    assert "אינה בתוקף" in bot.replies[-1][1]


def test_private_subscribe_and_unsubscribe_are_explicit(monkeypatch):
    db = install_db(monkeypatch)
    bot = FakeBot()
    target.register(bot)
    bot.handlers["music_invite_subscribe"](message("/music_invite_subscribe", uid=555))
    assert db[target.OPTED_USERS_KEY]["555"]["opted_in"] is True
    bot.handlers["music_invite_unsubscribe"](message("/music_invite_unsubscribe", uid=555))
    assert db[target.OPTED_USERS_KEY]["555"]["opted_in"] is False


def test_group_opt_in_requires_owner_and_admin(monkeypatch):
    db = install_db(monkeypatch)
    bot = FakeBot(member_status="member")
    target.register(bot)
    group_message = message(
        "/music_invite group_on", chat_type="supergroup", chat_id=-1001, title="Test group"
    )
    bot.handlers["music_invite"](group_message)
    assert "-1001" not in db.get(target.OPTED_GROUPS_KEY, {})
    assert "נדרש מנהל" in bot.replies[-1][1]


def test_non_owner_cannot_prepare_or_send_campaign(monkeypatch):
    install_db(monkeypatch)
    bot = FakeBot()
    target.register(bot)
    bot.handlers["music_invite"](message("/music_invite preview", uid=987654))
    assert bot.sent == []
    assert "מיועדת לבעלים" in bot.replies[-1][1]
