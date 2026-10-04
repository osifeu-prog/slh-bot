import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import state_manager


class TestDbJsonIntegrity(unittest.TestCase):
    def _sandbox(self):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        db = root / "db.json"
        lock = root / "db.json.lock"
        backups = root / "backups"
        db.write_text(
            json.dumps({"users": {"u": {}}, "counter": 0}, ensure_ascii=False),
            encoding="utf-8",
        )
        return td, db, lock, backups

    def _patch_paths(self, db, lock, backups):
        return patch.multiple(
            state_manager,
            DB_FILE=str(db),
            _LOCK_PATH=str(lock),
            _BACKUP_DIR=backups,
        )

    def test_atomic_read_modify_write_survives_concurrent_threads(self):
        td, db, lock, backups = self._sandbox()
        try:
            with self._patch_paths(db, lock, backups):
                errors = []

                def worker(worker_id):
                    try:
                        for _ in range(200):
                            def mutate(data):
                                data["counter"] = int(data.get("counter", 0)) + 1
                                data["last_worker"] = worker_id
                            state_manager.atomic_update(mutate)
                    except Exception as exc:
                        errors.append(exc)

                threads = [
                    threading.Thread(target=worker, args=(1,)),
                    threading.Thread(target=worker, args=(2,)),
                ]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()

                self.assertEqual(errors, [])
                data = json.loads(db.read_text(encoding="utf-8"))
                self.assertEqual(data["counter"], 400)
        finally:
            td.cleanup()

    def test_failed_read_never_falls_back_to_empty_or_writes(self):
        td, db, lock, backups = self._sandbox()
        try:
            corrupt = "{ definitely-not-json"
            db.write_text(corrupt, encoding="utf-8")
            before = db.read_bytes()
            mutate_called = []

            with self._patch_paths(db, lock, backups), patch.object(
                state_manager, "_notify_owner"
            ) as notify:
                with self.assertRaises(RuntimeError):
                    state_manager.atomic_update(
                        lambda data: mutate_called.append(True)
                    )

                self.assertEqual(mutate_called, [])
                self.assertEqual(db.read_bytes(), before)
                notify.assert_called_once()
        finally:
            td.cleanup()

    def test_backup_is_re_read_and_corrupt_backup_is_rejected(self):
        td, db, lock, backups = self._sandbox()
        try:
            with self._patch_paths(db, lock, backups):
                backup = Path(state_manager.backup_db(keep=5))
                self.assertTrue(backup.exists())
                self.assertTrue(state_manager.validate_backup(backup))

                backup.write_text("{broken", encoding="utf-8")
                self.assertFalse(state_manager.validate_backup(backup))

                # A fresh backup remains valid and retention never exceeds N.
                for _ in range(7):
                    state_manager.backup_db(keep=5)
                valid_backups = sorted(backups.glob("db_*.json"))
                self.assertLessEqual(len(valid_backups), 5)
                self.assertTrue(all(state_manager.validate_backup(p) for p in valid_backups))
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main()
