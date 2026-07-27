from pathlib import Path
import fcntl


class MissionLifecycleLock:

    def __init__(self, root="."):
        self.root = Path(root)
        self.lock_path = (
            self.root
            / "state"
            / "missions"
            / ".mission_lifecycle.lock"
        )
        self._handle = None

    def acquire(self):
        self.lock_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self._handle = open(
            self.lock_path,
            "a+",
            encoding="utf-8"
        )

        fcntl.flock(
            self._handle.fileno(),
            fcntl.LOCK_EX
        )

        return self

    def release(self):
        if self._handle is not None:

            fcntl.flock(
                self._handle.fileno(),
                fcntl.LOCK_UN
            )

            self._handle.close()
            self._handle = None

    def __enter__(self):
        return self.acquire()

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback
    ):
        self.release()
        return False
