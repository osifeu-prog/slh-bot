import unittest
from handlers.dev_admin import _normalize_role_action, _parse_target_uid


class DevAdminValidationTest(unittest.TestCase):
    def test_target_uid_must_be_positive_numeric(self):
        self.assertEqual(_parse_target_uid(["/dev_perm", "12345"]), "12345")
        for raw in ["", "<user_id>", "-123", "abc123", "0", "user_123"]:
            self.assertIsNone(_parse_target_uid(["/dev_perm", raw]))

    def test_revoke_aliases_remain_normalized(self):
        for raw in ["revoke", "remove", "none"]:
            self.assertEqual(_normalize_role_action(raw), "revoke")
        self.assertEqual(_normalize_role_action("lock"), "lock")


if __name__ == "__main__":
    unittest.main()
