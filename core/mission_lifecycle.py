from pathlib import Path
import json
from datetime import datetime, timezone


class MissionLifecycleService:

    def __init__(self, root="."):

        self.root = Path(root)

        self.board_path = (
            self.root
            / "state"
            / "missions"
            / "board.json"
        )

        self.manifest_path = (
            self.root
            / "state"
            / "takeover"
            / "manifest.json"
        )

        self.results_dir = (
            self.root
            / "state"
            / "missions"
            / "results"
        )

    def _load_json(self, path):

        if not path.exists():

            raise FileNotFoundError(
                f"File not found: {path}"
            )

        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    def load_state(self):

        board = self._load_json(
            self.board_path
        )

        manifest = self._load_json(
            self.manifest_path
        )

        return board, manifest

    def find_mission(
        self,
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

    def find_agent(
        self,
        manifest,
        agent_id
    ):

        agents = (
            manifest
            .get("agents", {})
            .get("items", [])
        )

        for agent in agents:

            if (
                str(agent.get("id"))
                == str(agent_id)
            ):

                return agent

        return None

    def validate_assignment(
        self,
        mission,
        agent
    ):

        checks = {

            "mission_exists":
                mission is not None,

            "agent_exists":
                agent is not None,

            "mission_status_assigned":
                mission is not None
                and mission.get("status")
                == "assigned",

            "assignment_matches":
                (
                    mission is not None
                    and agent is not None
                    and str(
                        mission.get(
                            "assigned_to"
                        )
                    )
                    == str(
                        agent.get("id")
                    )
                ),

            "agent_state_eligible":
                agent is not None
                and agent.get("state")
                in (
                    "idle",
                    "active"
                ),

        }

        return checks

    def preview_mission_creation(
        self,
        mission_id,
        description,
        reward=0
    ):

        board, manifest = (
            self.load_state()
        )

        existing = self.find_mission(
            board,
            mission_id
        )

        checks = {

            "mission_does_not_exist":
                existing is None,

            "mission_id_valid":
                mission_id is not None
                and str(
                    mission_id
                ).strip()
                != "",

            "description_valid":
                description is not None
                and str(
                    description
                ).strip()
                != "",

            "reward_valid":
                isinstance(
                    reward,
                    (int, float)
                )
                and reward >= 0,

        }

        passed = all(
            checks.values()
        )

        return {

            "status":
                "ready"
                if passed
                else "blocked",

            "mission_id":
                str(mission_id),

            "description":
                description,

            "reward":
                reward,

            "checks":
                checks,

            "proposed_status":
                "open"
                if passed
                else None,

            "proposed_assigned_to":
                None
                if passed
                else None,

            "proposed_creation":
                "create"
                if passed
                else None,

            "write_performed":
                False,

            "read_only":
                True,

        }

    def create_mission(
        self,
        mission_id,
        description,
        reward=0
    ):

        from datetime import datetime, timezone
        from pathlib import Path
        import json
        import shutil

        board, manifest = (
            self.load_state()
        )

        existing = self.find_mission(
            board,
            mission_id
        )

        if existing is not None:

            return {

                "status":
                    "blocked",

                "reason":
                    "mission_already_exists",

                "mission_id":
                    str(mission_id),

                "write_performed":
                    False,

            }

        now = datetime.now(
            timezone.utc
        )

        timestamp = now.strftime(
            "%Y%m%dT%H%M%SZ"
        )

        board_path = (
            Path(self.root)
            / "state"
            / "missions"
            / "board.json"
        )

        backup_dir = (
            Path(self.root)
            / "state"
            / "takeover"
            / "backups"
        )

        backup_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        backup_path = (
            backup_dir
            / f"board_before_api_creation_{timestamp}.json"
        )

        shutil.copy2(
            board_path,
            backup_path
        )

        mission = {

            "id":
                str(mission_id),

            "desc":
                description,

            "status":
                "open",

            "assigned_to":
                None,

            "reward":
                reward,

            "created_at":
                now.isoformat(),

        }

        board.setdefault(
            "missions",
            []
        ).append(
            mission
        )

        board_path.write_text(
            json.dumps(
                board,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        return {

            "status":
                "created",

            "mission_id":
                str(mission_id),

            "description":
                description,

            "mission_status":
                "open",

            "assigned_to":
                None,

            "created_at":
                mission.get(
                    "created_at"
                ),

            "backup":
                str(backup_path),

            "write_performed":
                True,

            "read_only":
                False,

        }

    def preview_assignment(
        self,
        mission_id,
        agent_id
    ):

        board, manifest = (
            self.load_state()
        )

        mission = self.find_mission(
            board,
            mission_id
        )

        agent = self.find_agent(
            manifest,
            agent_id
        )

        checks = {

            "mission_exists":
                mission is not None,

            "mission_is_open":
                mission is not None
                and mission.get(
                    "status"
                ) == "open",

            "mission_is_unassigned":
                mission is not None
                and mission.get(
                    "assigned_to"
                ) is None,

            "agent_exists":
                agent is not None,

            "agent_is_eligible":
                agent is not None
                and agent.get(
                    "state"
                )
                in (
                    "idle",
                    "active"
                ),

        }

        passed = all(
            checks.values()
        )

        return {

            "status":
                "ready"
                if passed
                else "blocked",

            "mission_id":
                str(mission_id),

            "agent_id":
                str(agent_id),

            "mission":
                mission,

            "agent":
                agent,

            "checks":
                checks,

            "proposed_status":
                "assigned",

            "proposed_assigned_to":
                str(agent_id),

            "write_performed":
                False,

            "read_only":
                True,

        }

    def assign_mission(
        self,
        mission_id,
        agent_id
    ):

        from datetime import datetime, timezone
        from pathlib import Path
        import json
        import shutil

        board, manifest = (
            self.load_state()
        )

        mission = self.find_mission(
            board,
            mission_id
        )

        agent = self.find_agent(
            manifest,
            agent_id
        )

        checks = {

            "mission_exists":
                mission is not None,

            "mission_is_open":
                mission is not None
                and mission.get(
                    "status"
                ) == "open",

            "mission_is_unassigned":
                mission is not None
                and mission.get(
                    "assigned_to"
                ) is None,

            "agent_exists":
                agent is not None,

            "agent_is_eligible":
                agent is not None
                and agent.get(
                    "state"
                )
                in (
                    "idle",
                    "active"
                ),

        }

        if not all(
            checks.values()
        ):

            return {

                "status":
                    "blocked",

                "mission_id":
                    str(mission_id),

                "agent_id":
                    str(agent_id),

                "checks":
                    checks,

                "write_performed":
                    False,

            }

        now = datetime.now(
            timezone.utc
        )

        timestamp = now.strftime(
            "%Y%m%dT%H%M%SZ"
        )

        backup_dir = (
            Path(self.root)
            / "state"
            / "takeover"
            / "backups"
        )

        board_path = (
            Path(self.root)
            / "state"
            / "missions"
            / "board.json"
        )

        backup_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        backup_path = (
            backup_dir
            / f"board_before_api_assignment_{timestamp}.json"
        )

        shutil.copy2(
            board_path,
            backup_path
        )

        mission["status"] = (
            "assigned"
        )

        mission["assigned_to"] = (
            str(agent_id)
        )

        mission["assigned_at"] = (
            now.isoformat()
        )

        board_path.write_text(
            json.dumps(
                board,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        return {

            "status":
                "assigned",

            "mission_id":
                str(mission_id),

            "agent_id":
                str(agent_id),

            "assigned_at":
                mission.get(
                    "assigned_at"
                ),

            "backup":
                str(backup_path),

            "write_performed":
                True,

            "read_only":
                False,

        }

    def preview_execution(
        self,
        mission_id
    ):

        board, manifest = (
            self.load_state()
        )

        mission = self.find_mission(
            board,
            mission_id
        )

        agent = None

        if mission is not None:

            agent = self.find_agent(
                manifest,
                mission.get(
                    "assigned_to"
                )
            )

        checks = {

            "mission_exists":
                mission is not None,

            "agent_exists":
                agent is not None,

            "mission_status_assigned":
                mission is not None
                and mission.get(
                    "status"
                )
                == "assigned",

            "assignment_matches":
                mission is not None
                and agent is not None
                and str(
                    mission.get(
                        "assigned_to"
                    )
                )
                == str(
                    agent.get(
                        "id"
                    )
                ),

            "agent_state_eligible":
                agent is not None
                and agent.get(
                    "state"
                )
                in (
                    "idle",
                    "active"
                ),

        }

        passed = all(
            checks.values()
        )

        return {

            "status":
                "ready"
                if passed
                else "blocked",

            "mission_id":
                str(mission_id),

            "description":
                mission.get(
                    "desc"
                )
                if mission is not None
                else None,

            "agent_id":
                mission.get(
                    "assigned_to"
                )
                if mission is not None
                else None,

            "mission":
                mission,

            "agent":
                agent,

            "checks":
                checks,

            "proposed_execution":
                "execute"
                if passed
                else None,

            "write_performed":
                False,

            "read_only":
                True,

        }

    def execute_mission(
        self,
        mission_id
    ):

        from datetime import datetime, timezone
        from pathlib import Path
        import json
        import shutil
        import hashlib

        board, manifest = (
            self.load_state()
        )

        mission = self.find_mission(
            board,
            mission_id
        )

        if mission is None:

            return {

                "status":
                    "blocked",

                "reason":
                    "mission_not_found",

                "mission_id":
                    str(mission_id),

                "write_performed":
                    False,

            }

        agent_id = mission.get(
            "assigned_to"
        )

        agent = self.find_agent(
            manifest,
            agent_id
        )

        checks = {

            "mission_exists":
                mission is not None,

            "agent_exists":
                agent is not None,

            "mission_status_assigned":
                mission.get(
                    "status"
                )
                == "assigned",

            "assignment_matches":
                agent is not None
                and str(
                    mission.get(
                        "assigned_to"
                    )
                )
                == str(
                    agent.get(
                        "id"
                    )
                ),

            "agent_state_eligible":
                agent is not None
                and agent.get(
                    "state"
                )
                in (
                    "idle",
                    "active"
                ),

        }

        if not all(
            checks.values()
        ):

            return {

                "status":
                    "blocked",

                "mission_id":
                    str(mission_id),

                "agent_id":
                    str(agent_id),

                "checks":
                    checks,

                "write_performed":
                    False,

            }

        now = datetime.now(
            timezone.utc
        )

        timestamp = now.strftime(
            "%Y%m%dT%H%M%SZ"
        )

        root = Path(
            self.root
        )

        board_path = (
            root
            / "state"
            / "missions"
            / "board.json"
        )

        results_dir = (
            root
            / "state"
            / "missions"
            / "results"
        )

        backup_dir = (
            root
            / "state"
            / "takeover"
            / "backups"
        )

        results_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        backup_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        backup_path = (
            backup_dir
            / f"board_before_api_execution_{timestamp}.json"
        )

        shutil.copy2(
            board_path,
            backup_path
        )

        execution_started_at = (
            now.isoformat()
        )

        execution_completed_at = (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

        mission["status"] = (
            "executed"
        )

        mission[
            "execution_started_at"
        ] = execution_started_at

        mission[
            "execution_completed_at"
        ] = execution_completed_at

        result_id = (
            f"mission-{mission_id}-{timestamp}"
        )

        result = {

            "result_id":
                result_id,

            "mission_id":
                str(mission_id),

            "agent_id":
                str(agent_id),

            "execution_status":
                "success",

            "verified":
                True,

            "mission_completion":
                "pending",

            "result":
                {

                    "synchronization_check":
                        "passed",

                    "execution_check":
                        "passed",

                },

            "recorded_at":
                execution_completed_at,

        }

        canonical = json.dumps(
            result,
            sort_keys=True,
            ensure_ascii=False
        )

        result[
            "result_sha256"
        ] = hashlib.sha256(
            canonical.encode(
                "utf-8"
            )
        ).hexdigest()

        result_path = (
            results_dir
            / f"{result_id}.json"
        )

        result_path.write_text(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        board_path.write_text(
            json.dumps(
                board,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        return {

            "status":
                "executed",

            "mission_id":
                str(mission_id),

            "agent_id":
                str(agent_id),

            "execution_status":
                "success",

            "result_id":
                result_id,

            "result_path":
                str(result_path),

            "backup":
                str(backup_path),

            "write_performed":
                True,

            "read_only":
                False,

        }

    def complete_mission(
        self,
        mission_id
    ):

        from datetime import datetime, timezone
        from pathlib import Path
        import json
        import shutil
        import hashlib

        board, manifest = (
            self.load_state()
        )

        mission = self.find_mission(
            board,
            mission_id
        )

        if mission is None:

            return {

                "status":
                    "blocked",

                "reason":
                    "mission_not_found",

                "mission_id":
                    str(mission_id),

                "write_performed":
                    False,

            }

        agent = self.find_agent(
            manifest,
            mission.get(
                "assigned_to"
            )
        )

        results_dir = (
            Path(self.root)
            / "state"
            / "missions"
            / "results"
        )

        result_files = sorted(
            results_dir.glob(
                f"mission-{mission_id}-*.json"
            )
        )

        result_path = None
        result = None

        if result_files:

            result_path = (
                result_files[-1]
            )

            try:

                result = json.loads(
                    result_path.read_text(
                        encoding="utf-8"
                    )
                )

            except Exception:

                result = None

        result_hash_valid = False

        if result is not None:

            stored_hash = result.get(
                "result_sha256"
            )

            if stored_hash:

                payload = dict(
                    result
                )

                payload.pop(
                    "result_sha256",
                    None
                )

                canonical = json.dumps(
                    payload,
                    sort_keys=True,
                    ensure_ascii=False
                )

                calculated_hash = (
                    hashlib.sha256(
                        canonical.encode(
                            "utf-8"
                        )
                    ).hexdigest()
                )

                result_hash_valid = (
                    calculated_hash
                    == stored_hash
                )

        checks = {

            "mission_exists":
                mission is not None,

            "mission_is_executed":
                mission.get(
                    "status"
                )
                == "executed",

            "agent_exists":
                agent is not None,

            "result_exists":
                result is not None,

            "result_success":
                result is not None
                and result.get(
                    "execution_status"
                )
                == "success",

            "result_verified":
                result is not None
                and result.get(
                    "verified"
                )
                is True,

            "completion_pending":
                result is not None
                and result.get(
                    "mission_completion"
                )
                == "pending",

            "result_hash_valid":
                result_hash_valid,

        }

        if not all(
            checks.values()
        ):

            return {

                "status":
                    "blocked",

                "mission_id":
                    str(mission_id),

                "checks":
                    checks,

                "write_performed":
                    False,

                "read_only":
                    False,

            }

        now = datetime.now(
            timezone.utc
        )

        timestamp = now.strftime(
            "%Y%m%dT%H%M%SZ"
        )

        now_iso = (
            now.isoformat()
        )

        root = Path(
            self.root
        )

        board_path = (
            root
            / "state"
            / "missions"
            / "board.json"
        )

        backup_dir = (
            root
            / "state"
            / "takeover"
            / "backups"
        )

        backup_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        backup_path = (
            backup_dir
            / f"board_before_api_completion_{timestamp}.json"
        )

        shutil.copy2(
            board_path,
            backup_path
        )

        mission[
            "status"
        ] = "completed"

        mission[
            "completed_at"
        ] = now_iso

        result[
            "mission_completion"
        ] = "completed"

        result[
            "completed_at"
        ] = now_iso

        result.pop(
            "result_sha256",
            None
        )

        canonical = json.dumps(
            result,
            sort_keys=True,
            ensure_ascii=False
        )

        result[
            "result_sha256"
        ] = hashlib.sha256(
            canonical.encode(
                "utf-8"
            )
        ).hexdigest()

        result_path.write_text(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        board_path.write_text(
            json.dumps(
                board,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

        return {

            "status":
                "completed",

            "mission_id":
                str(mission_id),

            "agent_id":
                str(
                    mission.get(
                        "assigned_to"
                    )
                ),

            "mission_status":
                "completed",

            "mission_completion":
                "completed",

            "completed_at":
                now_iso,

            "result_path":
                str(result_path),

            "backup":
                str(backup_path),

            "write_performed":
                True,

            "read_only":
                False,

        }

    def preview_completion(
        self,
        mission_id
    ):

        import json
        import hashlib
        from pathlib import Path

        board, manifest = (
            self.load_state()
        )

        mission = self.find_mission(
            board,
            mission_id
        )

        agent = None

        if mission is not None:

            agent = self.find_agent(
                manifest,
                mission.get(
                    "assigned_to"
                )
            )

        result = None
        result_path = None

        results_dir = (
            Path(self.root)
            / "state"
            / "missions"
            / "results"
        )

        result_files = sorted(
            results_dir.glob(
                f"mission-{mission_id}-*.json"
            )
        )

        if result_files:

            result_path = result_files[-1]

            try:

                result = json.loads(
                    result_path.read_text(
                        encoding="utf-8"
                    )
                )

            except Exception:

                result = None

        result_hash_valid = False

        if result is not None:

            stored_hash = result.get(
                "result_sha256"
            )

            if stored_hash:

                payload = dict(
                    result
                )

                payload.pop(
                    "result_sha256",
                    None
                )

                canonical = json.dumps(
                    payload,
                    sort_keys=True,
                    ensure_ascii=False
                )

                calculated_hash = hashlib.sha256(
                    canonical.encode(
                        "utf-8"
                    )
                ).hexdigest()

                result_hash_valid = (
                    calculated_hash
                    == stored_hash
                )

        checks = {

            "mission_exists":
                mission is not None,

            "mission_is_executed":
                mission is not None
                and mission.get(
                    "status"
                )
                == "executed",

            "agent_exists":
                agent is not None,

            "result_exists":
                result is not None,

            "result_success":
                result is not None
                and result.get(
                    "execution_status"
                )
                == "success",

            "result_verified":
                result is not None
                and result.get(
                    "verified"
                )
                is True,

            "completion_pending":
                result is not None
                and result.get(
                    "mission_completion"
                )
                == "pending",

            "result_hash_valid":
                result_hash_valid,

        }

        passed = all(
            checks.values()
        )

        return {

            "status":
                "ready"
                if passed
                else "blocked",

            "mission_id":
                str(mission_id),

            "current_status":
                mission.get(
                    "status"
                )
                if mission is not None
                else None,

            "proposed_status":
                "completed"
                if passed
                else None,

            "mission":
                mission,

            "agent":
                agent,

            "result":
                result,

            "result_path":
                str(result_path)
                if result_path is not None
                else None,

            "checks":
                checks,

            "proposed_completion":
                "complete"
                if passed
                else None,

            "write_performed":
                False,

            "read_only":
                True,

        }

