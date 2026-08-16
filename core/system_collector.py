class SystemCollector:

    # ---------------------------------------------------------
    # SYSTEM COLLECTOR FOUNDATION
    # ---------------------------------------------------------
    # Collects system state from approved public contracts.
    #
    # The collector does not expose:
    #   - Runtime internals
    #   - Kernel objects
    #   - Dispatcher objects
    #   - Queue objects
    #
    # It returns data only.
    # ---------------------------------------------------------

    def __init__(self, runtime):

        self.runtime = runtime

    def snapshot(self):

        runtime_snapshot = self.runtime.snapshot()

        kernel_snapshot = self.runtime.kernel.snapshot()

        boot_ok = runtime_snapshot.get(
            "boot_ok"
        )

        return {
            "system": {
                "name": "SLH OS",
                "version": "3.0",
                "mode": "OS",
            },

            "runtime": dict(
                runtime_snapshot
            ),

            "kernel": dict(
                kernel_snapshot
            ),

            "health": {
                "boot_ok": boot_ok,
                "warnings": (
                    0
                    if boot_ok is None
                    else (
                        0
                        if boot_ok
                        else 1
                    )
                ),
                "fatal_errors": (
                    0
                    if boot_ok
                    else 1
                ),
            },
        }
