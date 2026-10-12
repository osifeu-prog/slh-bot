import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from handlers import file_handler


class TestPrivateFileHandler(unittest.TestCase):
    def test_storage_uses_generated_name_and_private_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "uploads"
            with patch.object(file_handler, "UPLOAD_DIR", target):
                name = file_handler._store_upload(
                    b"safe test data",
                    "../../private-investor-names.csv",
                )
                path = target / name

                self.assertEqual(path.parent, target)
                self.assertNotIn("private-investor-names", name)
                self.assertNotIn("..", name)
                self.assertEqual(path.read_bytes(), b"safe test data")
                self.assertEqual(os.stat(target).st_mode & 0o777, 0o700)
                self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
                self.assertFalse((Path(tmp) / "journal.json").exists())

    def test_oversized_upload_is_rejected_without_file_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "uploads"
            with patch.object(file_handler, "UPLOAD_DIR", target):
                with patch.object(file_handler, "MAX_UPLOAD_BYTES", 3):
                    with self.assertRaisesRegex(ValueError, "UPLOAD_TOO_LARGE"):
                        file_handler._store_upload(b"four", "x.txt")
                self.assertFalse(target.exists())

    def test_unapproved_suffix_does_not_survive(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "uploads"
            with patch.object(file_handler, "UPLOAD_DIR", target):
                name = file_handler._store_upload(b"x", "run-me.sh")
                self.assertTrue(name.endswith(".bin"))
                self.assertNotIn("run-me", name)


if __name__ == "__main__":
    unittest.main()
