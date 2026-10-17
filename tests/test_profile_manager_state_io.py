import unittest
from unittest.mock import patch

from core import profile_manager


class ProfileManagerCanonicalDBIOTests(unittest.TestCase):
    def test_load_db_delegates_to_canonical_state_manager(self):
        expected = {"users": {"u1": {"wallet": {"credits": 3.0}}}}

        with patch.object(
            profile_manager.state_manager, "load_db", return_value=expected
        ) as load_db:
            result = profile_manager.load_db()

        load_db.assert_called_once_with()
        self.assertIs(result, expected)

    def test_save_db_delegates_to_canonical_atomic_writer(self):
        db = {"users": {"u1": {"wallet": {"credits": 3.0}}}}

        with patch.object(profile_manager.state_manager, "save_db") as save_db:
            profile_manager.save_db(db)

        save_db.assert_called_once_with(db)


if __name__ == "__main__":
    unittest.main()
