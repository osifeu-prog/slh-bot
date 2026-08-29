from pathlib import Path
import json
import shutil
from datetime import datetime, timezone


ROOT = Path(".")

BOARD_PATH = (
    ROOT
    / "state"
    / "missions"
    / "board.json"
)

BACKUP_DIR = (
    ROOT
    / "state"
    / "takeover"
    / "backups"
)


def load_json(path):

    if not path.exists():

        raise FileNotFoundError(
            f"File not found: {path}"
        )

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def find_mission(
    board,
    mission_id
):

    for mission in board.get(
        "missions",
        []
    ):

        if (
            isinstance(mission, dict)
            and str(
                mission.get("id")
            )
            == str(mission_id)
        ):

            return mission

    return None


def main():

    print("=" * 80)
    print("       SLH MISSION CREATION COMMIT")
    print("             CONTROLLED WRITE")
    print("=" * 80)

    mission_id = "2"

    description = (
        "LIFECYCLE CORE TEST"
    )

    board = load_json(
        BOARD_PATH
    )

    print()
    print("[FINAL PRE-WRITE VALIDATION]")

    existing = find_mission(
        board,
        mission_id
    )

    checks = [

        (
            "mission ID is available",
            existing is None
        ),

        (
            "description is valid",
            bool(
                description.strip()
            )
        ),

        (
            "initial status is open",
            True
        ),

    ]

    failed = False

    for name, passed in checks:

        if passed:

            print(
                "✅",
                name
            )

        else:

            print(
                "❌",
                name
            )

            failed = True

    if failed:

        print()
        print(
            "❌ MISSION CREATION BLOCKED"
        )

        return 1

    now = datetime.now(
        timezone.utc
    )

    timestamp = now.strftime(
        "%Y%m%dT%H%M%SZ"
    )

    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    backup_path = (
        BACKUP_DIR
        / f"board_before_mission_2_{timestamp}.json"
    )

    print()
    print("[BACKUP]")

    shutil.copy2(
        BOARD_PATH,
        backup_path
    )

    print(
        "✅ Board backup:",
        backup_path
    )

    mission = {

        "id": mission_id,

        "desc": description,

        "status": "open",

        "assigned_to": None,

        "created_at":
            now.isoformat(),

    }

    print()
    print("[CONTROLLED WRITE]")

    board.setdefault(
        "missions",
        []
    ).append(
        mission
    )

    BOARD_PATH.write_text(
        json.dumps(
            board,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print(
        "✅ Mission #2 created"
    )

    print(
        "✅ Status: open"
    )

    print(
        "✅ Assigned To: None"
    )

    print()
    print("[SAFETY BOUNDARY]")

    print(
        "✅ BOARD MODIFIED: ONE NEW MISSION"
    )

    print(
        "✅ BACKUP CREATED BEFORE WRITE"
    )

    print(
        "✅ MANIFEST NOT MODIFIED DIRECTLY"
    )

    print(
        "✅ AGENTS NOT MODIFIED"
    )

    print(
        "✅ NO EXTERNAL NETWORK ACTION"
    )

    print()
    print("=" * 80)
    print("MISSION CREATION COMMIT COMPLETE")
    print("MISSION #2 EXISTS IN OPEN STATE")
    print("READY FOR MANIFEST REFRESH")
    print("=" * 80)

    return 0


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
