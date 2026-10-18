import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.identity import OWNER_TELEGRAM_ID
from handlers import music_lab_invite_handler as invites


def message(uid, chat_type="private", text="/music_invite"):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=int(uid)),
        chat=SimpleNamespace(id=int(uid) if chat_type == "private" else -100123, type=chat_type),
        text=text,
        message_id=77,
    )


class FakeBot:
    def __init__(self):
        self.messages = []
        self.replies = []
        self.answers = []
        self.edits = []
        self.message_handlers = []
        self.callback_handlers = []

    def message_handler(self, **kwargs):
        def register(fn):
            self.message_handlers.append((kwargs, fn))
            return fn
        return register

    def callback_query_handler(self, **kwargs):
        def register(fn):
            self.callback_handlers.append((kwargs, fn))
            return fn
        return register

    def reply_to(self, msg, text, **kwargs):
        self.replies.append((msg, text, kwargs))

    def send_message(self, chat_id, text, **kwargs):
        self.messages.append((chat_id, text, kwargs))

    def answer_callback_query(self, callback_id, text=None, **kwargs):
        self.answers.append((callback_id, text, kwargs))

    def edit_message_reply_markup(self, *args, **kwargs):
        self.edits.append((args, kwargs))

    def handler(self, commands=None, callback_data=None):
        for opts, fn in self.message_handlers:
            if commands and all(command in opts.get("commands", []) for command in commands):
                return fn
        if callback_data:
            for opts, fn in self.callback_handlers:
                predicate = opts.get("func")
                if predicate and predicate(SimpleNamespace(data=callback_data)):
                    return fn
        raise AssertionError("handler not registered")


class MusicLabInviteTests(unittest.TestCase):
    def setUp(self):
        invites._PENDING.clear()
        self.bot = FakeBot()
        invites.register(self.bot)

    def tearDown(self):
        invites._PENDING.clear()

    def sample_db(self):
        owner = str(OWNER_TELEGRAM_ID)
        return {
            "users": {owner: {}, "111": {}, "222": {}, "333": {"lang": "he"}, "not-an-id": {}},
            "music_lab_invite_opt_outs": {"333": "2026-10-01T00:00:00+00:00"},
            "music_lab_invite_opt_ins": {
                "111": "2026-10-01T00:00:00+00:00",
                "222": "2026-10-01T00:00:00+00:00",
                "333": "2026-10-01T00:00:00+00:00",
            },
            "community_groups": {
                "-100111": {
                    "chat_id": "-100111", "role": "free", "bot_status": "administrator",
                    "music_lab_invite_opt_in": True,
                },
                "-100222": {"chat_id": "-100222", "role": "unbound", "bot_status": "administrator"},
                "-100333": {"chat_id": "-100333", "role": "academy", "bot_status": "left"},
                "444": {"chat_id": "444", "role": "vip", "bot_status": "administrator"},
            },
        }

    def test_targets_exclude_owner_optouts_and_unverified_groups(self):
        users, groups = invites._targets(self.sample_db())
        self.assertEqual(users, ["111", "222"])
        self.assertEqual(groups, ["-100111"])

    def test_preview_is_private_owner_only_and_sends_nothing(self):
        db = self.sample_db()
        with patch.object(invites.state_manager, "load_db", return_value=db):
            invites._PENDING.clear()
            owner = str(OWNER_TELEGRAM_ID)
            self.bot.handler(commands=["music_invite"])(message(owner))
        self.assertEqual(len(self.bot.replies), 1)
        self.assertEqual(self.bot.messages, [])
        self.assertIn("לא נשלחה הודעה", self.bot.replies[0][1])
        self.assertEqual(len(invites._PENDING), 1)
        preview = self.bot.replies[0][1]
        self.assertIn("2", preview)
        self.assertIn("1", preview)

    def test_non_owner_cannot_prepare_campaign(self):
        with patch.object(invites.state_manager, "load_db", side_effect=AssertionError("DB should not be read")):
            self.bot.handler(commands=["music_invite"])(message("111"))
        self.assertIn("בעלים בלבד", self.bot.replies[0][1])
        self.assertFalse(invites._PENDING)

    def test_group_command_cannot_prepare_campaign(self):
        with patch.object(invites.state_manager, "load_db", side_effect=AssertionError("DB should not be read")):
            self.bot.handler(commands=["music_invite"])(message(OWNER_TELEGRAM_ID, "supergroup"))
        self.assertIn("בשיחה הפרטית", self.bot.replies[0][1])
        self.assertFalse(invites._PENDING)

    def test_confirmation_is_owner_private_single_use_and_expiring(self):
        owner = str(OWNER_TELEGRAM_ID)
        campaign_id = "abc123"
        invites._PENDING[campaign_id] = {
            "campaign_id": campaign_id, "owner_uid": owner,
            "user_ids": ["111"], "group_ids": [], "expires_at": 10**12,
        }
        call = SimpleNamespace(
            id="callback-1", data=f"mliv:send:{campaign_id}",
            from_user=SimpleNamespace(id=int(OWNER_TELEGRAM_ID)),
            message=SimpleNamespace(chat=SimpleNamespace(type="private", id=int(OWNER_TELEGRAM_ID)), message_id=99),
        )
        with patch.object(invites, "_send_campaign", return_value="sent summary") as send:
            handler = self.bot.handler(callback_data=call.data)
            handler(call)
        send.assert_called_once()
        self.assertNotIn(campaign_id, invites._PENDING)
        self.assertEqual(self.bot.messages[-1][1], "sent summary")
        # A duplicate tap cannot deliver the same campaign again.
        handler(call)
        send.assert_called_once()
        self.assertIn("אינה פעילה", self.bot.answers[-1][1])

    def test_group_invitation_does_not_offer_a_misleading_personal_optout_button(self):
        markup = invites._markup(private=False)
        callback_data = [
            button.callback_data
            for row in markup.keyboard
            for button in row
            if getattr(button, "callback_data", None)
        ]
        self.assertNotIn("mliv:optout", callback_data)
        self.assertIn("/music_invite_stop", invites.GROUP_INVITE_TEXT)
        self.assertIn("הודעות אישיות", invites.GROUP_INVITE_TEXT)

    def test_opt_out_callback_persists_preference_without_financial_paths(self):
        call = SimpleNamespace(
            id="callback-optout", data="mliv:optout",
            from_user=SimpleNamespace(id=111),
            message=SimpleNamespace(chat=SimpleNamespace(type="private", id=111)),
        )
        with patch.object(invites, "_set_optout", return_value=True) as save:
            self.bot.handler(callback_data="mliv:optout")(call)
        save.assert_called_once_with("111", True)
        self.assertTrue(self.bot.answers[-1][1].startswith("העדפה נשמרה"))


if __name__ == "__main__":
    unittest.main()
