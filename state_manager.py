"""Canonical db.json state access with atomic, process-safe persistence.

The canonical database is state/db.json. All read/modify/write operations that
touch this file should go through atomic_update(). Public load/save calls are
also protected by the same shared lock so a malformed read can never fall back
to an empty database and overwrite the live state.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    with open("config.json", encoding="utf-8") as f:
        cfg = json.load(f)
except Exception:
    cfg = {}

DB_FILE = cfg.get("DB_FILE", "state/db.json")
_DB_PATH = Path(DB_FILE)
_LOCK_PATH = str(_DB_PATH) + ".lock"
_BACKUP_DIR = _DB_PATH.parent / "backups"

try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    fcntl = None
    HAS_FCNTL = False

_THREAD_LOCK = threading.RLock()
_LOCK_TLS = threading.local()
_BACKUP_START_LOCK = threading.Lock()
_BACKUP_THREAD: threading.Thread | None = None
_ALERT_LOCK = threading.Lock()
_LAST_ALERT_AT = 0.0
_ALERT_COOLDOWN_SECONDS = 60.0


def _db_path() -> Path:
    return Path(DB_FILE)


def _lock_path() -> Path:
    return Path(_LOCK_PATH)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _db_lock():
    """One re-entrant process/thread lock shared by every db.json operation."""
    _THREAD_LOCK.acquire()
    depth = int(getattr(_LOCK_TLS, "depth", 0))
    lockfile = getattr(_LOCK_TLS, "lockfile", None)

    if depth == 0:
        path = _lock_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        lockfile = path.open("a+", encoding="utf-8")
        if HAS_FCNTL:
            fcntl.flock(lockfile.fileno(), fcntl.LOCK_EX)
        _LOCK_TLS.lockfile = lockfile

    _LOCK_TLS.depth = depth + 1
    try:
        yield
    finally:
        new_depth = int(getattr(_LOCK_TLS, "depth", 1)) - 1
        _LOCK_TLS.depth = new_depth
        if new_depth == 0:
            held = getattr(_LOCK_TLS, "lockfile", None)
            try:
                if HAS_FCNTL and held is not None:
                    fcntl.flock(held.fileno(), fcntl.LOCK_UN)
            finally:
                if held is not None:
                    held.close()
                _LOCK_TLS.lockfile = None
        _THREAD_LOCK.release()


def _telegram_credentials() -> tuple[str | None, str | None]:
    token = str(os.getenv("BOT_TOKEN") or "").strip()
    if not token:
        token = str(cfg.get("BOT_TOKEN") or "").strip()

    owner = str(os.getenv("SLH_OWNER_ID") or "").strip()
    if not owner:
        owner = str(cfg.get("SUPER_ADMIN") or "").strip()

    return (token or None, owner or None)


def _notify_owner(message: str) -> None:
    """Best-effort Telegram alert; never masks the original state error."""
    global _LAST_ALERT_AT

    now = time.monotonic()
    with _ALERT_LOCK:
        if now - _LAST_ALERT_AT < _ALERT_COOLDOWN_SECONDS:
            return
        _LAST_ALERT_AT = now

    token, owner = _telegram_credentials()
    if not token or not owner:
        print("[STATE] owner alert skipped: Telegram credentials unavailable")
        return

    try:
        body = urllib.parse.urlencode({
            "chat_id": owner,
            "text": str(message)[:3900],
        }).encode("utf-8")
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=body,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=6) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not payload.get("ok"):
            raise RuntimeError(str(payload.get("description") or "telegram alert failed"))
    except Exception as exc:
        print(f"[STATE] owner alert failed safely: {type(exc).__name__}")


def _validate_db_data(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise RuntimeError("load_db: db.json root must be an object")
    if "users" not in data:
        raise RuntimeError("load_db: db.json missing users")
    if not isinstance(data.get("users"), dict):
        raise RuntimeError("load_db: db.json users must be an object")
    return data


def _load_db_unlocked() -> dict[str, Any]:
    path = _db_path()
    if not path.exists():
        raise FileNotFoundError(f"DB not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        raise RuntimeError("DB_READ_FAILED") from exc

    return _validate_db_data(data)


def _atomic_write_json_unlocked(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temp_path = Path(temp_name)

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                indent=2,
                ensure_ascii=False,
                sort_keys=False,
            )
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())

        os.replace(temp_path, path)

        # Persist the directory entry where supported.
        try:
            dir_fd = os.open(str(path.parent), os.O_DIRECTORY)
        except (AttributeError, OSError):
            dir_fd = None
        if dir_fd is not None:
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
    finally:
        temp_path.unlink(missing_ok=True)


def _save_db_unlocked(db: dict[str, Any]) -> None:
    if not isinstance(db, dict) or "users" not in db:
        raise ValueError("save_db refused: malformed db")
    if not isinstance(db.get("users"), dict) or not db["users"]:
        raise ValueError("save_db refused: empty users - possible wipe")
    _atomic_write_json_unlocked(_db_path(), db)


def load_db() -> dict[str, Any]:
    """Read canonical state under the shared lock; failures raise and never default."""
    try:
        with _db_lock():
            data = _load_db_unlocked()
    except Exception as exc:
        _notify_owner(
            "❗️ SLH state read failed: state/db.json could not be read. "
            "No replacement/default database was written."
        )
        if isinstance(exc, FileNotFoundError):
            raise
        raise RuntimeError("DB_READ_FAILED") from exc

    _ensure_backup_scheduler()
    return data


def save_db(db: dict[str, Any]) -> None:
    """Persist canonical state atomically under the same shared lock."""
    with _db_lock():
        _save_db_unlocked(db)


def atomic_update(mutate_fn: Callable[[dict[str, Any]], Any]) -> Any:
    """Safely load, mutate and save db.json as one locked atomic operation."""
    if not callable(mutate_fn):
        raise TypeError("mutate_fn must be callable")

    # Re-enter the same lock while using the public API. This keeps test/runtime
    # patch points intact without creating a second independent lock.
    with _db_lock():
        db = load_db()
        result = mutate_fn(db)
        save_db(db)
        return result


def validate_backup(path: str | os.PathLike[str]) -> bool:
    """Read a backup and confirm it is valid canonical DB JSON."""
    try:
        with Path(path).open("r", encoding="utf-8") as f:
            data = json.load(f)
        _validate_db_data(data)
        return True
    except Exception:
        return False


def backup_db(*, keep: int | None = None) -> str:
    """Create and re-read a verified db.json backup, retaining only N newest."""
    keep_n = int(
        keep
        if keep is not None
        else os.getenv("SLH_DB_BACKUP_KEEP", "5")
    )
    if keep_n < 1:
        raise ValueError("SLH_DB_BACKUP_KEEP_INVALID")

    with _db_lock():
        db = _load_db_unlocked()
        backup_dir = _BACKUP_DIR
        backup_dir.mkdir(parents=True, exist_ok=True)

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        final_path = backup_dir / f"db_{stamp}.json"
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{final_path.name}.",
            suffix=".tmp",
            dir=str(backup_dir),
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(db, f, indent=2, ensure_ascii=False)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())

            # Backup must be readable before it is published.
            if not validate_backup(temp_path):
                temp_path.unlink(missing_ok=True)
                raise RuntimeError("DB_BACKUP_VALIDATION_FAILED")

            os.replace(temp_path, final_path)

            if not validate_backup(final_path):
                final_path.unlink(missing_ok=True)
                raise RuntimeError("DB_BACKUP_REJECTED_AFTER_PUBLISH")

            backups = sorted(backup_dir.glob("db_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            for old in backups[keep_n:]:
                old.unlink(missing_ok=True)

            return str(final_path)
        except Exception as exc:
            temp_path.unlink(missing_ok=True)
            _notify_owner(
                "❗️ SLH db.json backup failed or was rejected. "
                "The live db.json was not replaced."
            )
            raise RuntimeError("DB_BACKUP_FAILED") from exc


def _backup_interval_seconds() -> int:
    try:
        value = int(os.getenv("SLH_DB_BACKUP_INTERVAL_SECONDS", "3600"))
    except (TypeError, ValueError):
        value = 3600
    return max(300, value)


def _backup_loop() -> None:
    interval = _backup_interval_seconds()
    while True:
        time.sleep(interval)
        try:
            backup_db()
        except Exception as exc:
            print(f"[STATE] periodic backup failed: {type(exc).__name__}")


def _ensure_backup_scheduler() -> None:
    global _BACKUP_THREAD
    if _BACKUP_THREAD is not None and _BACKUP_THREAD.is_alive():
        return
    with _BACKUP_START_LOCK:
        if _BACKUP_THREAD is not None and _BACKUP_THREAD.is_alive():
            return
        _BACKUP_THREAD = threading.Thread(
            target=_backup_loop,
            name="slh-db-backup",
            daemon=True,
        )
        _BACKUP_THREAD.start()


def get_agents():
    from core.agent_state_store import AgentStateStore
    return AgentStateStore().get_all()


def set_agents(agents):
    if not isinstance(agents, dict):
        raise ValueError("agents must be a dict")
    return atomic_update(lambda db: db.__setitem__("agents", agents))


def update_agent(prefix, data):
    def mutate(db):
        agents = db.setdefault("agents", {})
        agents[str(prefix)] = data
    return atomic_update(mutate)


def delete_agent(prefix):
    def mutate(db):
        agents = db.setdefault("agents", {})
        agents.pop(str(prefix), None)
    return atomic_update(mutate)


def clear_agents():
    return set_agents({})


def load_json(filename, default=None):
    """Read a JSON state file without mutating it."""
    path = Path(filename) if os.path.isabs(str(filename)) else Path("state") / str(filename)
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def atomic_json_update(filename, mutate_fn, default=None):
    """Atomically update a non-canonical JSON file under its own lock."""
    path = Path(filename) if os.path.isabs(str(filename)) else Path("state") / str(filename)
    lock_path = Path(str(path) + ".lock")
    os.makedirs(path.parent, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lockfile:
        if HAS_FCNTL:
            fcntl.flock(lockfile.fileno(), fcntl.LOCK_EX)
        try:
            if path.exists():
                with path.open(encoding="utf-8") as f:
                    data = json.load(f)
            else:
                data = default if default is not None else {}
            result = mutate_fn(data)
            _atomic_write_json_unlocked(path, data)
            return result
        finally:
            if HAS_FCNTL:
                fcntl.flock(lockfile.fileno(), fcntl.LOCK_UN)
