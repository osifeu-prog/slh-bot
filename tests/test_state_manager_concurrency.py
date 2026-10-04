import json
import threading

import state_manager


def configure_db_path(tmp_path):
    db_path = tmp_path / "db.json"
    state_manager.DB_FILE = str(db_path)
    state_manager._LOCK_PATH = str(db_path) + ".lock"
    return db_path


def test_save_db_concurrent_writes_are_atomic(tmp_path):
    db_path = configure_db_path(tmp_path)
    db = {"users": {"1": {"uid": "1"}}, "counter": 0}
    errors = []

    def writer():
        try:
            state_manager.save_db(db)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=writer) for _ in range(20)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    with db_path.open(encoding="utf-8") as handle:
        stored = json.load(handle)
    assert stored["users"]["1"]["uid"] == "1"


def test_atomic_update_serializes_concurrent_mutations(tmp_path):
    db_path = configure_db_path(tmp_path)
    state_manager.save_db({"users": {"1": {"uid": "1"}}, "counter": 0})
    errors = []

    def increment(_db):
        _db["counter"] += 1

    def worker():
        try:
            state_manager.atomic_update(increment)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(50)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    with db_path.open(encoding="utf-8") as handle:
        stored = json.load(handle)
    assert stored["counter"] == 50
