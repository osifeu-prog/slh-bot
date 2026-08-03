class SystemCollector:

    def __init__(self, runtime=None):
        self.runtime = runtime

    def collect(self):
        return self.snapshot()

    def snapshot(self):

        if self.runtime is None:
            return {
                "system": {
                    "name": "SLH OS",
                    "version": "3.0",
                    "mode": "OS",
                },
                "health": {
                    "boot_ok": True,
                    "warnings": 0,
                    "fatal_errors": 0,
                },
                "agents": {},
                "users": {},
                "tasks": {},
                "votes": {},
                "projects": {},
                "devices": {},
                "installations": {},
                "database": {},
                "project_graph": {},
            }

        runtime_snapshot = self.runtime.snapshot()
        kernel_snapshot = self.runtime.kernel.snapshot()

        boot_ok = runtime_snapshot.get("boot_ok")

        return {
            "system": {
                "name": "SLH OS",
                "version": "3.0",
                "mode": "OS",
            },
            "runtime": dict(runtime_snapshot),
            "kernel": dict(kernel_snapshot),
            "health": {
                "boot_ok": boot_ok,
                "warnings": 0 if boot_ok else 1,
                "fatal_errors": 0 if boot_ok else 1,
            },
        }
