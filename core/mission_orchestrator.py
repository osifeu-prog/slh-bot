from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from core.mission_lifecycle import (
    MissionLifecycleService
)

from core.mission_state import (
    MissionState,
    MissionStateNormalizer
)


class MissionOrchestrator:

    def __init__(
        self,
        root="."
    ):

        self.root = root

        self.lifecycle = (
            MissionLifecycleService(
                root
            )
        )

    def _now(self):

        return (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

    def _stage(
        self,
        name,
        status,
        result=None
    ):

        return {

            "name":
                name,

            "status":
                status,

            "result":
                result,

            "timestamp":
                self._now(),

        }

    def _blocked(
        self,
        mission_id,
        agent_id,
        stages,
        failed_stage,
        result
    ):

        return {

            "status":
                "blocked",

            "mission_id":
                str(mission_id),

            "agent_id":
                str(agent_id)
                if agent_id is not None
                else None,

            "failed_stage":
                failed_stage,

            "stages":
                stages,

            "result":
                result,

        }

    def get_mission_state(
        self,
        mission_id
    ):

        board, manifest = (
            self.lifecycle.load_state()
        )

        mission = (
            self.lifecycle.find_mission(
                board,
                mission_id
            )
        )

        if mission is None:

            return {

                "status":
                    "missing",

                "mission_id":
                    str(mission_id),

                "mission":
                    None,

            }

        return {

            "status":
                mission.get(
                    "status"
                ),

            "mission_id":
                str(mission_id),

            "assigned_to":
                mission.get(
                    "assigned_to"
                ),

            "mission":
                mission,

        }

    def get_next_action(
        self,
        mission_id,
        agent_id=None
    ):

        state = (
            self.get_mission_state(
                mission_id
            )
        )

        status = (
            MissionStateNormalizer
            .normalize(
                state.get(
                    "status"
                )
            )
        )

        if status == "missing":

            return {

                "status":
                    "ready",

                "mission_id":
                    str(mission_id),

                "current_state":
                    "missing",

                "next_action":
                    "create",

                "requires_agent":
                    False,

            }

        if status == MissionState.OPEN.value:

            return {

                "status":
                    "ready",

                "mission_id":
                    str(mission_id),

                "current_state":
                    "open",

                "next_action":
                    "assign",

                "requires_agent":
                    True,

                "agent_id":
                    str(agent_id)
                    if agent_id is not None
                    else None,

            }

        if status == MissionState.ASSIGNED.value:

            return {

                "status":
                    "ready",

                "mission_id":
                    str(mission_id),

                "current_state":
                    "assigned",

                "next_action":
                    "execute",

                "requires_agent":
                    False,

                "agent_id":
                    state.get(
                        "assigned_to"
                    ),

            }

        if status == MissionState.EXECUTED.value:

            return {

                "status":
                    "ready",

                "mission_id":
                    str(mission_id),

                "current_state":
                    "executed",

                "next_action":
                    "complete",

                "requires_agent":
                    False,

                "agent_id":
                    state.get(
                        "assigned_to"
                    ),

            }

        if MissionStateNormalizer.is_completed(
            status
        ):

            return {

                "status":
                    "done",

                "mission_id":
                    str(mission_id),

                "current_state":
                    "completed",

                "next_action":
                    None,

                "requires_agent":
                    False,

                "agent_id":
                    state.get(
                        "assigned_to"
                    ),

            }

        return {

            "status":
                "blocked",

            "mission_id":
                str(mission_id),

            "current_state":
                status,

            "next_action":
                None,

            "reason":
                "Unknown mission state",

        }

    def run_next_action(
        self,
        mission_id,
        agent_id=None,
        description=None,
        reward=0
    ):

        next_action = (
            self.get_next_action(
                mission_id=mission_id,
                agent_id=agent_id
            )
        )

        action = (
            next_action.get(
                "next_action"
            )
        )

        if action == "complete":

            preview = (
                self.lifecycle
                .preview_completion(
                    mission_id=mission_id
                )
            )

            if preview.get(
                "status"
            ) != "ready":

                return {

                    "status":
                        "blocked",

                    "action":
                        "complete",

                    "preview":
                        preview,

                }

            result = (
                self.lifecycle
                .complete_mission(
                    mission_id=mission_id
                )
            )

            return {

                "status":
                    "completed",

                "action":
                    "complete",

                "result":
                    result,

            }

        if action == "execute":

            preview = (
                self.lifecycle
                .preview_execution(
                    mission_id=mission_id
                )
            )

            if preview.get(
                "status"
            ) != "ready":

                return {

                    "status":
                        "blocked",

                    "action":
                        "execute",

                    "preview":
                        preview,

                }

            result = (
                self.lifecycle
                .execute_mission(
                    mission_id=mission_id
                )
            )

            return {

                "status":
                    "executed",

                "action":
                    "execute",

                "result":
                    result,

            }

        if action == "assign":

            if agent_id is None:

                return {

                    "status":
                        "blocked",

                    "action":
                        "assign",

                    "reason":
                        "agent_id is required",

                }

            preview = (
                self.lifecycle
                .preview_assignment(
                    mission_id=mission_id,
                    agent_id=agent_id
                )
            )

            if preview.get(
                "status"
            ) != "ready":

                return {

                    "status":
                        "blocked",

                    "action":
                        "assign",

                    "preview":
                        preview,

                }

            result = (
                self.lifecycle
                .assign_mission(
                    mission_id=mission_id,
                    agent_id=agent_id
                )
            )

            return {

                "status":
                    "assigned",

                "action":
                    "assign",

                "result":
                    result,

            }

        if action == "create":

            if description is None:

                return {

                    "status":
                        "blocked",

                    "action":
                        "create",

                    "reason":
                        "description is required",

                }

            preview = (
                self.lifecycle
                .preview_mission_creation(
                    mission_id=mission_id,
                    description=description,
                    reward=reward
                )
            )

            if preview.get(
                "status"
            ) != "ready":

                return {

                    "status":
                        "blocked",

                    "action":
                        "create",

                    "preview":
                        preview,

                }

            result = (
                self.lifecycle
                .create_mission(
                    mission_id=mission_id,
                    description=description,
                    reward=reward
                )
            )

            return {

                "status":
                    "created",

                "action":
                    "create",

                "result":
                    result,

            }

        if action is None:

            if next_action.get(
                "status"
            ) == "done":

                return {

                    "status":
                        "done",

                    "action":
                        None,

                    "message":
                        "Mission already completed",

                }

        return {

            "status":
                "blocked",

            "action":
                action,

            "reason":
                "Unknown or unsupported action",

            "router":
                next_action,

        }

    def create_and_run(
        self,
        mission_id,
        description,
        agent_id=None,
        reward=0,
        max_steps=10
    ):

        if description is None:

            return {

                "status":
                    "blocked",

                "mission_id":
                    str(mission_id),

                "reason":
                    "description is required",

            }

        result = (
            self.run_mission_to_completion(
                mission_id=mission_id,
                agent_id=agent_id,
                description=description,
                reward=reward,
                max_steps=max_steps
            )
        )

        return result

    def run_mission_to_completion(
        self,
        mission_id,
        agent_id=None,
        description=None,
        reward=0,
        max_steps=10
    ):

        steps = []

        for step_number in range(
            1,
            max_steps + 1
        ):

            next_action = (
                self.get_next_action(
                    mission_id=mission_id,
                    agent_id=agent_id
                )
            )

            action = (
                next_action.get(
                    "next_action"
                )
            )

            if (
                next_action.get(
                    "status"
                )
                == "done"
            ):

                return {

                    "status":
                        "completed",

                    "mission_id":
                        str(mission_id),

                    "steps":
                        steps,

                    "message":
                        "Mission already completed",

                }

            if action is None:

                return {

                    "status":
                        "blocked",

                    "mission_id":
                        str(mission_id),

                    "steps":
                        steps,

                    "reason":
                        "No valid next action",

                    "router":
                        next_action,

                }

            result = (
                self.run_next_action(
                    mission_id=mission_id,
                    agent_id=agent_id,
                    description=description,
                    reward=reward
                )
            )

            steps.append({

                "step":
                    step_number,

                "action":
                    action,

                "result":
                    result,

            })

            if result.get(
                "status"
            ) == "blocked":

                return {

                    "status":
                        "blocked",

                    "mission_id":
                        str(mission_id),

                    "steps":
                        steps,

                    "failed_action":
                        action,

                    "result":
                        result,

                }

        return {

            "status":
                "blocked",

            "mission_id":
                str(mission_id),

            "steps":
                steps,

            "reason":
                "Maximum lifecycle steps exceeded",

            "max_steps":
                max_steps,

        }

    def run_mission(
        self,
        mission_id,
        agent_id
    ):

        stages: List[
            Dict[str, Any]
        ] = []

        # --------------------------------------------------
        # 1. CREATION PREVIEW
        # --------------------------------------------------

        preview = (
            self.lifecycle
            .preview_mission_creation(
                mission_id=mission_id,
                description=None,
                reward=0
            )
        )

        stages.append(
            self._stage(
                "creation_preview",
                "passed"
                if preview.get(
                    "status"
                ) == "ready"
                else "failed",
                preview
            )
        )

        if preview.get(
            "status"
        ) != "ready":

            return self._blocked(
                mission_id,
                agent_id,
                stages,
                "creation_preview",
                preview
            )

        # --------------------------------------------------
        # 2. ASSIGNMENT PREVIEW
        # --------------------------------------------------

        preview = (
            self.lifecycle
            .preview_assignment(
                mission_id=mission_id,
                agent_id=agent_id
            )
        )

        stages.append(
            self._stage(
                "assignment_preview",
                "passed"
                if preview.get(
                    "status"
                ) == "ready"
                else "failed",
                preview
            )
        )

        if preview.get(
            "status"
        ) != "ready":

            return self._blocked(
                mission_id,
                agent_id,
                stages,
                "assignment_preview",
                preview
            )

        # --------------------------------------------------
        # 3. EXECUTION PREVIEW
        # --------------------------------------------------

        preview = (
            self.lifecycle
            .preview_execution(
                mission_id=mission_id
            )
        )

        stages.append(
            self._stage(
                "execution_preview",
                "passed"
                if preview.get(
                    "status"
                ) == "ready"
                else "failed",
                preview
            )
        )

        if preview.get(
            "status"
        ) != "ready":

            return self._blocked(
                mission_id,
                agent_id,
                stages,
                "execution_preview",
                preview
            )

        # --------------------------------------------------
        # 4. COMPLETION PREVIEW
        # --------------------------------------------------

        preview = (
            self.lifecycle
            .preview_completion(
                mission_id=mission_id
            )
        )

        stages.append(
            self._stage(
                "completion_preview",
                "passed"
                if preview.get(
                    "status"
                ) == "ready"
                else "failed",
                preview
            )
        )

        if preview.get(
            "status"
        ) != "ready":

            return self._blocked(
                mission_id,
                agent_id,
                stages,
                "completion_preview",
                preview
            )

        return {

            "status":
                "ready",

            "mission_id":
                str(mission_id),

            "agent_id":
                str(agent_id),

            "stages":
                stages,

            "message":
                "All lifecycle previews passed. Mission is ready for controlled commits."

        }


if __name__ == "__main__":

    print(
        "MissionOrchestrator module loaded."
    )
