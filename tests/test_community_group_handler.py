import types
from unittest.mock import patch

import handlers.community_group_handler as handler


def _chat(chat_id=-100123, title="Test Group"):
    return types.SimpleNamespace(
        id=chat_id,
        type="supergroup",
        title=title,
        username=None,
    )


def test_record_membership_writes_canonical_group_and_member():
    db = {}
    handler._record_membership(db, "501", _chat(), "member")

    assert db["community_groups"]["-100123"]["chat_id"] == "-100123"
    assert db["community_groups"]["-100123"]["title"] == "Test Group"
    assert db["community_memberships"]["501:-100123"]["status"] == "member"


def test_record_membership_updates_existing_status():
    db = {}
    chat = _chat()
    handler._record_membership(db, "501", chat, "member")
    handler._record_membership(db, "501", chat, "left")

    assert db["community_memberships"]["501:-100123"]["status"] == "left"


def test_bind_current_group_requires_group_chat():
    m = types.SimpleNamespace(
        from_user=types.SimpleNamespace(id=8789977826),
        chat=types.SimpleNamespace(id=99, type="private", title=None, username=None),
    )

    try:
        handler._bind_current_group(m, "free")
    except ValueError as exc:
        assert str(exc) == "GROUP_BIND_MUST_RUN_IN_GROUP"
    else:
        raise AssertionError("private chats must not be bindable")


def test_bind_current_group_persists_explicit_role():
    m = types.SimpleNamespace(
        from_user=types.SimpleNamespace(id=8789977826),
        chat=_chat(),
    )
    stored = {}

    def fake_update(mutator):
        db = {}
        result = mutator(db)
        stored.update(db)
        return result

    with patch.object(handler.state_manager, "atomic_update", side_effect=fake_update):
        result = handler._bind_current_group(m, "vip")

    assert result["role"] == "vip"
    assert result["chat_id"] == "-100123"
    assert stored["community_groups"]["-100123"]["role"] == "vip"
