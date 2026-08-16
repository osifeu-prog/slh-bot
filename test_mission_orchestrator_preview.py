import json

from core.mission_orchestrator import (
    MissionOrchestrator
)


def main():

    print("=" * 80)
    print("       SLH MISSION ORCHESTRATOR")
    print("              PREVIEW TEST")
    print("=" * 80)

    mission_id = "4"
    agent_id = "3"

    orchestrator = MissionOrchestrator(".")

    result = orchestrator.run_mission(
        mission_id=mission_id,
        agent_id=agent_id
    )

    print()
    print("[ORCHESTRATOR RESULT]")

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
            default=str
        )
    )

    print()
    print("[SAFETY ASSERTIONS]")

    checks = [

        (
            "result exists",
            result is not None
        ),

        (
            "status == blocked",
            result.get(
                "status"
            )
            == "blocked"
        ),

        (
            "failed_stage == creation_preview",
            result.get(
                "failed_stage"
            )
            == "creation_preview"
        ),

        (
            "mission_id == 4",
            str(
                result.get(
                    "mission_id"
                )
            )
            == "4"
        ),

        (
            "only one stage executed",
            len(
                result.get(
                    "stages",
                    []
                )
            )
            == 1
        ),

        (
            "no assignment preview executed",
            not any(
                stage.get(
                    "name"
                )
                == "assignment_preview"
                for stage in result.get(
                    "stages",
                    []
                )
            )
        ),

        (
            "no execution preview executed",
            not any(
                stage.get(
                    "name"
                )
                == "execution_preview"
                for stage in result.get(
                    "stages",
                    []
                )
            )
        ),

        (
            "no completion preview executed",
            not any(
                stage.get(
                    "name"
                )
                == "completion_preview"
                for stage in result.get(
                    "stages",
                    []
                )
            )
        ),

    ]

    failed = False

    for name, passed in checks:

        print(
            "✅" if passed else "❌",
            name
        )

        if not passed:

            failed = True

    print()

    if failed:

        print(
            "❌ ORCHESTRATOR SAFETY TEST FAILED"
        )

        return 1

    print(
        "✅ ORCHESTRATOR SAFETY TEST PASSED"
    )

    print()
    print(
        "MISSION #4 WAS SAFELY BLOCKED"
    )

    print(
        "NO INVALID LIFECYCLE TRANSITION WAS ATTEMPTED"
    )

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
