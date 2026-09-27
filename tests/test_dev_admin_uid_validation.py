import unittest
from handlers.dev_admin import _parse_target_uid


class DevAdminUidTests(unittest.TestCase):
    def test_positive_numeric_only(self):
        self.assertEqual(_parse_target_uid(["/dev_perm", "12345"]), "12345")
        for raw in ["<user_id>", "abc", "-123", "0", "user_1"]:
            self.assertIsNone(_parse_target_uid(["/dev_perm", raw]))


if __name__ == "__main__":
    unittest.main()
