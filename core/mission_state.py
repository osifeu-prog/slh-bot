from __future__ import annotations

from enum import Enum


class MissionState(str, Enum):

    OPEN = "open"

    ASSIGNED = "assigned"

    EXECUTED = "executed"

    COMPLETED = "completed"

    BLOCKED = "blocked"


class MissionStateNormalizer:

    LEGACY_MAP = {

        "done":
            MissionState.COMPLETED.value,

    }

    VALID_STATES = {

        MissionState.OPEN.value,

        MissionState.ASSIGNED.value,

        MissionState.EXECUTED.value,

        MissionState.COMPLETED.value,

        MissionState.BLOCKED.value,

    }

    @classmethod
    def normalize(
        cls,
        status
    ):

        if status is None:

            return None

        status = str(
            status
        ).strip().lower()

        return cls.LEGACY_MAP.get(
            status,
            status
        )

    @classmethod
    def is_valid(
        cls,
        status
    ):

        return (
            cls.normalize(
                status
            )
            in cls.VALID_STATES
        )

    @classmethod
    def is_completed(
        cls,
        status
    ):

        return (
            cls.normalize(
                status
            )
            == MissionState.COMPLETED.value
        )

    @classmethod
    def is_terminal(
        cls,
        status
    ):

        return (
            cls.normalize(
                status
            )
            == MissionState.COMPLETED.value
        )

    @classmethod
    def next_action(
        cls,
        status
    ):

        normalized = cls.normalize(
            status
        )

        mapping = {

            None:
                "create",

            "open":
                "assign",

            "assigned":
                "execute",

            "executed":
                "complete",

            "completed":
                None,

        }

        return mapping.get(
            normalized
        )

