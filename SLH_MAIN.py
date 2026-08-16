from core.kernel import SLHKernel
from core.runtime import Runtime
from core.agent_factory import load_agents_into_kernel
from adapters.cli import CLIAdapter



class BootState:
    """
    Canonical state object for the SLH OS boot process.

    Centralizes the Kernel and Boot Report
    without changing existing boot behavior.
    """

    def __init__(self, kernel, report):
        self.kernel = kernel
        self.report = report

    @property
    def boot_ok(self):
        return bool(
            self.report.get(
                "boot_ok",
                False
            )
        )

    @property
    def warnings(self):
        return list(
            self.report.get(
                "warnings",
                []
            )
        )

    @property
    def fatal_errors(self):
        return list(
            self.report.get(
                "fatal_errors",
                []
            )
        )

    def status(self):
        return {
            "boot_ok": self.boot_ok,
            "warnings": len(
                self.warnings
            ),
            "fatal_errors": len(
                self.fatal_errors
            ),
            "agents": self.kernel.status().get(
                "agents",
                []
            ),
        }


class BootFailure(RuntimeError):
    """
    Raised when the SLH OS boot integrity contract fails.
    """

    def __init__(self, report):
        self.report = report

        fatal_errors = report.get(
            "fatal_errors",
            []
        )

        message = (
            "SLH boot failed: "
            f"{len(fatal_errors)} fatal error(s)"
        )

        super().__init__(message)


def boot_kernel():
    """
    Create the Kernel and load all DB-defined Agents
    through the validated runtime factory.
    """

    kernel = SLHKernel()

    report = load_agents_into_kernel(
        kernel
    )

    print()
    print("🔐 AGENT BOOT REPORT")
    print(
        "LOADED:",
        len(report["loaded"])
    )
    print(
        "SKIPPED:",
        len(report["skipped"])
    )
    print(
        "ERRORS:",
        len(report["errors"])
    )

    for item in report["loaded"]:
        print(
            "✅ LOADED:",
            item["name"],
            "→",
            item["runtime_class"]
        )

    for item in report["skipped"]:
        print(
            "⏭️ SKIPPED:",
            item["name"],
            "→",
            item["reason"]
        )

    for item in report["errors"]:
        print(
            "❌ ERROR:",
            item.get("name"),
            "→",
            item.get("error")
        )

    # ---------------------------------------------------------
    # BOOT INTEGRITY CONTRACT
    # ---------------------------------------------------------

    report["fatal_errors"] = list(
        report.get("errors", [])
    )

    report["warnings"] = list(
        report.get("skipped", [])
    )

    report["boot_ok"] = (
        len(report["fatal_errors"]) == 0
    )

    print()
    print(
        "🛡️ BOOT INTEGRITY:",
        "OK" if report["boot_ok"]
        else "FAILED"
    )

    print(
        "⚠️ WARNINGS:",
        len(report["warnings"])
    )

    print(
        "🚨 FATAL ERRORS:",
        len(report["fatal_errors"])
    )

    if not report.get(
        "boot_ok",
        False
    ):
        raise BootFailure(
            report
        )

    return BootState(
        kernel,
        report
    )


def main():

    try:
        state = boot_kernel()

    except BootFailure as exc:

        print()
        print("🛑 FATAL BOOT FAILURE")
        print(
            "Runtime and CLI will NOT start."
        )

        print()
        print("FATAL ERRORS:")

        for error in exc.report.get(
            "fatal_errors",
            []
        ):
            print(
                "❌",
                error
            )

        return 1

    runtime = Runtime(
        state
    )

    runtime.start()

    cli = CLIAdapter(
        runtime
    )

    cli.run()

    return 0


if __name__ == "__main__":
    main()
