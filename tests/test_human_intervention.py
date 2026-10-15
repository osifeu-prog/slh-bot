import copy

import pytest

from core import human_intervention as hi


OWNER = "8789977826"
REQUESTER = "5010371391"


@pytest.fixture
def memory_db(monkeypatch):
    db = {"users": {OWNER: {}, REQUESTER: {}}}

    def load_db():
        return db

    def atomic_update(mutator):
        candidate = copy.deepcopy(db)
        result = mutator(candidate)
        db.clear()
        db.update(candidate)
        return result

    monkeypatch.setattr(hi.state_manager, "load_db", load_db)
    monkeypatch.setattr(hi.state_manager, "atomic_update", atomic_update)
    monkeypatch.setattr(hi, "_is_owner", lambda uid: str(uid) == OWNER)
    return db


def test_missing_policy_defaults_to_approval_required(memory_db):
    effective = hi.get_settings()
    assert effective["required"] == {
        "action_execution": True,
        "action_completion": True,
    }
    assert effective["policy_source"] == "default_fail_closed"

    result = hi.request_or_authorize(
        action="mission_execute",
        resource_id="mission-17",
        requester_uid=REQUESTER,
        requester_chat_id=REQUESTER,
    )
    assert result["status"] == "approval_required"
    assert result["request_id"] in memory_db[hi.REQUESTS_KEY]
    assert memory_db[hi.REQUESTS_KEY][result["request_id"]]["status"] == "pending"
    assert [x["event"] for x in memory_db[hi.AUDIT_KEY]] == ["approval_requested"]


def test_only_owner_can_decide_and_approval_is_one_time(memory_db):
    requested = hi.request_or_authorize(
        action="task_complete",
        resource_id="task-a",
        requester_uid=REQUESTER,
        requester_chat_id=REQUESTER,
    )
    rid = requested["request_id"]

    denied = hi.decide_request(rid, approver_uid=REQUESTER, decision="approve")
    assert denied == {"status": "blocked", "reason": "owner_only"}
    assert memory_db[hi.REQUESTS_KEY][rid]["status"] == "pending"

    approved = hi.decide_request(rid, approver_uid=OWNER, decision="approve")
    assert approved["status"] == "approved"

    consumed = hi.request_or_authorize(
        action="task_complete",
        resource_id="task-a",
        requester_uid=REQUESTER,
        requester_chat_id=REQUESTER,
        approval_id=rid,
    )
    assert consumed["status"] == "authorized"
    assert memory_db[hi.REQUESTS_KEY][rid]["status"] == "executing"

    finished = hi.finish_request(rid, success=True, detail="test completed")
    assert finished["status"] == "completed"
    replay = hi.request_or_authorize(
        action="task_complete",
        resource_id="task-a",
        requester_uid=REQUESTER,
        requester_chat_id=REQUESTER,
        approval_id=rid,
    )
    assert replay["status"] == "blocked"
    assert memory_db[hi.REQUESTS_KEY][rid]["status"] == "completed"


def test_approval_is_bound_to_action_resource_and_requester(memory_db):
    requested = hi.request_or_authorize(
        action="mission_complete",
        resource_id="mission-5",
        requester_uid=REQUESTER,
    )
    rid = requested["request_id"]
    assert hi.decide_request(rid, approver_uid=OWNER, decision="approve")["status"] == "approved"

    mismatch = hi.request_or_authorize(
        action="mission_complete",
        resource_id="mission-6",
        requester_uid=REQUESTER,
        approval_id=rid,
    )
    assert mismatch["status"] == "blocked"
    assert mismatch["reason"] == "approval_scope_mismatch"
    assert memory_db[hi.REQUESTS_KEY][rid]["status"] == "approved"

    valid = hi.request_or_authorize(
        action="mission_complete",
        resource_id="mission-5",
        requester_uid=REQUESTER,
        approval_id=rid,
    )
    assert valid["status"] == "authorized"


def test_expired_request_cannot_be_approved(monkeypatch, memory_db):
    now = [1000.0]
    monkeypatch.setattr(hi, "_now", lambda: now[0])
    requested = hi.request_or_authorize(
        action="task_complete",
        resource_id="task-expiring",
        requester_uid=REQUESTER,
    )
    now[0] += hi.REQUEST_TTL_SECONDS + 1

    result = hi.decide_request(
        requested["request_id"], approver_uid=OWNER, decision="approve"
    )
    assert result["status"] == "blocked"
    assert result["reason"] == "request_expired"
    assert memory_db[hi.REQUESTS_KEY][requested["request_id"]]["status"] == "expired"


def test_disabling_requires_second_explicit_owner_confirmation(memory_db):
    enabled = hi.set_required(
        "action_execution", required=True, actor_uid=OWNER
    )
    assert enabled["status"] == "ok"
    assert enabled["settings"]["action_execution"] is True

    first = hi.propose_disable("action_execution", actor_uid=OWNER)
    assert first["status"] == "confirmation_required"
    change_id = first["confirmation_id"]
    assert memory_db[hi.CONFIG_CHANGES_KEY][change_id]["status"] == "pending"

    second = hi.confirm_disable(change_id, actor_uid=OWNER)
    assert second["status"] == "ok"
    assert second["required"] is False
    assert hi.get_settings()["required"]["action_execution"] is False

    replay = hi.confirm_disable(change_id, actor_uid=OWNER)
    assert replay["status"] == "blocked"
    assert replay["reason"] == "confirmation_replayed"


def test_unknown_action_and_missing_identity_are_blocked(memory_db):
    unknown = hi.request_or_authorize(
        action="arbitrary_shell_write",
        resource_id="x",
        requester_uid=REQUESTER,
    )
    assert unknown["status"] == "blocked"
    assert unknown["reason"] == "unknown_mutating_action"

    missing = hi.request_or_authorize(
        action="mission_execute",
        resource_id="mission-1",
        requester_uid="",
    )
    assert missing["status"] == "blocked"
    assert missing["reason"] == "action_identity_missing"


def test_state_read_failure_keeps_both_gates_closed(monkeypatch):
    def fail():
        raise RuntimeError("read unavailable")

    monkeypatch.setattr(hi.state_manager, "load_db", fail)
    effective = hi.get_settings()
    assert effective["status"] == "unavailable"
    assert effective["required"] == {
        "action_execution": True,
        "action_completion": True,
    }
    assert effective["policy_source"] == "default_fail_closed"


def test_task_completion_service_does_not_write_before_approval(monkeypatch, memory_db):
    from core.task_completion_service import complete_task

    memory_db["tasks"] = {
        "task-approval-test": {
            "id": "task-approval-test",
            "status": "active",
            "reward": 7,
            "done_by": [],
        }
    }
    memory_db["ledger"] = []

    result = complete_task(
        uid=REQUESTER,
        task_id="task-approval-test",
        meta={"source": "test"},
        requester_chat_id=REQUESTER,
    )

    assert result["status"] == "approval_required"
    assert result["action"] == "task_complete"
    assert memory_db["tasks"]["task-approval-test"]["status"] == "active"
    assert memory_db["tasks"]["task-approval-test"]["done_by"] == []
    assert memory_db["ledger"] == []
    assert memory_db[hi.REQUESTS_KEY][result["request_id"]]["status"] == "pending"
