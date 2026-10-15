"""Fail-closed, persisted human approval gates for supported system actions."""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any

import state_manager

POLICY_KEY = "human_intervention"
REQUESTS_KEY = "human_intervention_requests"
AUDIT_KEY = "human_intervention_audit"
CONFIG_CHANGES_KEY = "human_intervention_config_changes"
SETTING_NAMES = ("action_execution", "action_completion")
ACTION_SETTINGS = {
    "mission_execute": "action_execution",
    "mission_complete": "action_completion",
    "task_complete": "action_completion",
}
REQUEST_TTL_SECONDS = 30 * 60
CONFIG_CONFIRM_TTL_SECONDS = 5 * 60


def _now() -> float:
    return time.time()


def _iso(ts: float | None = None) -> str:
    value = _now() if ts is None else ts
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def _is_owner(uid: Any) -> bool:
    try:
        from core.authority import is_owner
        return bool(is_owner(str(uid)))
    except Exception:
        return False


def _settings_from_db(db: dict[str, Any]) -> dict[str, Any]:
    raw = db.get(POLICY_KEY)
    stored = raw.get("required") if isinstance(raw, dict) else None
    required = {}
    configured = {}
    for name in SETTING_NAMES:
        value = stored.get(name) if isinstance(stored, dict) else None
        valid = type(value) is bool
        configured[name] = valid
        # Unknown, missing, or malformed policy requires human approval.
        required[name] = value if valid else True
    return {
        "required": required,
        "configured": configured,
        "updated_at": raw.get("updated_at") if isinstance(raw, dict) else None,
        "updated_by": raw.get("updated_by") if isinstance(raw, dict) else None,
        "policy_source": "persisted" if all(configured.values()) else "default_fail_closed",
    }


def get_settings() -> dict[str, Any]:
    """Read effective policy; never writes defaults."""
    try:
        db = state_manager.load_db()
        result = _settings_from_db(db)
        result.update(status="ok", read_only=True)
        return result
    except Exception as exc:
        return {
            "required": {name: True for name in SETTING_NAMES},
            "configured": {name: False for name in SETTING_NAMES},
            "policy_source": "default_fail_closed",
            "status": "unavailable",
            "error": type(exc).__name__,
            "read_only": True,
        }


def _audit(db: dict[str, Any], event: str, *, actor_id=None, request_id=None,
           action=None, resource_id=None, detail=None) -> None:
    rows = db.get(AUDIT_KEY)
    if rows is None:
        rows = []
        db[AUDIT_KEY] = rows
    if not isinstance(rows, list):
        raise RuntimeError("HUMAN_INTERVENTION_AUDIT_MALFORMED")
    rows.append({
        "event": str(event),
        "timestamp": _iso(),
        "actor_id": str(actor_id) if actor_id is not None else None,
        "request_id": str(request_id) if request_id is not None else None,
        "action": str(action) if action is not None else None,
        "resource_id": str(resource_id) if resource_id is not None else None,
        "detail": str(detail)[:500] if detail is not None else None,
    })
    # Keep the audit trail append-only: never silently discard older decisions.


def record_action_event(event: str, *, actor_id=None, action=None,
                        resource_id=None, detail=None) -> dict[str, Any]:
    try:
        def mutate(db):
            _audit(db, event, actor_id=actor_id, action=action,
                   resource_id=resource_id, detail=detail)
            return {"status": "recorded"}
        return state_manager.atomic_update(mutate)
    except Exception as exc:
        return {"status": "blocked", "reason": "audit_write_failed",
                "error": type(exc).__name__}


def request_or_authorize(*, action: str, resource_id: str, requester_uid: str,
                         requester_chat_id=None, approval_id=None) -> dict[str, Any]:
    """Create a request, or atomically consume its approved one-time capability."""
    action = str(action or "").strip()
    setting = ACTION_SETTINGS.get(action)
    resource_id = str(resource_id or "").strip()
    requester_uid = str(requester_uid or "").strip()
    if setting is None:
        return {"status": "blocked", "reason": "unknown_mutating_action"}
    if not resource_id or not requester_uid:
        return {"status": "blocked", "reason": "action_identity_missing"}

    try:
        now = _now()

        if approval_id is not None:
            def consume(db):
                required = _settings_from_db(db)["required"][setting]
                requests = db.get(REQUESTS_KEY, {})
                req = requests.get(str(approval_id)) if isinstance(requests, dict) else None
                if not isinstance(req, dict):
                    return {"status": "blocked", "reason": "approval_request_not_found"}
                if not required:
                    if isinstance(req, dict) and req.get("status") == "approved":
                        req["status"] = "invalidated"
                        req["invalidated_at"] = now
                    _audit(db, "approval_invalidated_by_policy_change",
                           actor_id=requester_uid, request_id=approval_id,
                           action=action, resource_id=resource_id)
                    return {"status": "blocked", "reason": "policy_changed_resubmit"}
                if req.get("status") != "approved":
                    return {"status": "blocked", "reason": "approval_not_approved_or_replayed"}
                if float(req.get("expires_at", 0) or 0) <= now:
                    req["status"] = "expired"
                    req["expired_at"] = now
                    _audit(db, "request_expired", request_id=approval_id,
                           actor_id=requester_uid, action=action, resource_id=resource_id)
                    return {"status": "blocked", "reason": "approval_expired"}
                if (req.get("action") != action
                        or str(req.get("resource_id")) != resource_id
                        or str(req.get("requester_id")) != requester_uid):
                    _audit(db, "approval_mismatch_blocked", request_id=approval_id,
                           actor_id=requester_uid, action=action, resource_id=resource_id)
                    return {"status": "blocked", "reason": "approval_scope_mismatch"}
                req["status"] = "executing"
                req["executing_at"] = now
                _audit(db, "request_execution_started", request_id=approval_id,
                       actor_id=requester_uid, action=action, resource_id=resource_id)
                return {"status": "authorized", "gate": "approved", "request_id": str(approval_id)}
            return state_manager.atomic_update(consume)

        def create_or_reuse(db):
            required = _settings_from_db(db)["required"][setting]
            if not required:
                _audit(db, "action_gate_bypassed_by_explicit_policy",
                       actor_id=requester_uid, action=action, resource_id=resource_id,
                       detail="setting was explicitly disabled by owner")
                return {"status": "authorized", "gate": "disabled_by_owner"}
            requests = db.get(REQUESTS_KEY)
            if requests is None:
                requests = {}
                db[REQUESTS_KEY] = requests
            if not isinstance(requests, dict):
                return {"status": "blocked", "reason": "approval_state_malformed"}
            for existing_id, existing in requests.items():
                if not isinstance(existing, dict):
                    continue
                if (existing.get("status") == "pending"
                        and existing.get("action") == action
                        and str(existing.get("resource_id")) == resource_id
                        and str(existing.get("requester_id")) == requester_uid
                        and float(existing.get("expires_at", 0) or 0) > now):
                    return {"status": "approval_required", "request_id": str(existing_id),
                            "reused": True, "action": action, "resource_id": resource_id}
            request_id = uuid.uuid4().hex
            requests[request_id] = {
                "id": request_id, "action": action, "resource_id": resource_id,
                "requester_id": requester_uid,
                "requester_chat_id": str(requester_chat_id) if requester_chat_id is not None else None,
                "status": "pending", "created_at": now, "created_at_utc": _iso(now),
                "expires_at": now + REQUEST_TTL_SECONDS,
            }
            _audit(db, "approval_requested", actor_id=requester_uid,
                   request_id=request_id, action=action, resource_id=resource_id)
            return {"status": "approval_required", "request_id": request_id,
                    "reused": False, "action": action, "resource_id": resource_id}
        return state_manager.atomic_update(create_or_reuse)
    except Exception as exc:
        return {"status": "blocked", "reason": "approval_state_unavailable",
                "error": type(exc).__name__}


def get_request(request_id: str) -> dict[str, Any] | None:
    try:
        db = state_manager.load_db()
        requests = db.get(REQUESTS_KEY, {})
        req = requests.get(str(request_id)) if isinstance(requests, dict) else None
        return dict(req) if isinstance(req, dict) else None
    except Exception:
        return None


def decide_request(request_id: str, *, approver_uid: str, decision: str) -> dict[str, Any]:
    decision = str(decision or "").lower()
    approver_uid = str(approver_uid or "")
    if not _is_owner(approver_uid):
        return {"status": "blocked", "reason": "owner_only"}
    if decision not in {"approve", "reject"}:
        return {"status": "blocked", "reason": "invalid_decision"}
    now = _now()

    def mutate(db):
        requests = db.get(REQUESTS_KEY, {})
        req = requests.get(str(request_id)) if isinstance(requests, dict) else None
        if not isinstance(req, dict):
            return {"status": "blocked", "reason": "request_not_found"}
        if req.get("status") != "pending":
            return {"status": "blocked", "reason": "request_not_pending_or_replayed",
                    "current_status": req.get("status")}
        if float(req.get("expires_at", 0) or 0) <= now:
            req["status"] = "expired"
            req["expired_at"] = now
            _audit(db, "request_expired", request_id=request_id, actor_id=approver_uid,
                   action=req.get("action"), resource_id=req.get("resource_id"))
            return {"status": "blocked", "reason": "request_expired"}
        req["status"] = "approved" if decision == "approve" else "rejected"
        req["decided_by"] = approver_uid
        req["decided_at"] = now
        req["decided_at_utc"] = _iso(now)
        _audit(db, "request_" + req["status"], actor_id=approver_uid,
               request_id=request_id, action=req.get("action"),
               resource_id=req.get("resource_id"))
        return {"status": req["status"], "request": dict(req)}

    try:
        return state_manager.atomic_update(mutate)
    except Exception as exc:
        return {"status": "blocked", "reason": "approval_state_unavailable",
                "error": type(exc).__name__}


def finish_request(request_id: str, *, success: bool, detail=None) -> dict[str, Any]:
    target_status = "completed" if success else "failed"

    def mutate(db):
        requests = db.get(REQUESTS_KEY, {})
        req = requests.get(str(request_id)) if isinstance(requests, dict) else None
        if not isinstance(req, dict):
            return {"status": "blocked", "reason": "request_not_found"}
        allowed_prior = {"executing"} if success else {"executing", "approved"}
        if req.get("status") not in allowed_prior:
            return {"status": "blocked", "reason": "request_not_finishable_or_replayed",
                    "current_status": req.get("status")}
        req["status"] = target_status
        req["finished_at"] = _now()
        req["result_summary"] = str(detail or "")[:500]
        _audit(db, "request_" + target_status, actor_id=req.get("decided_by"),
               request_id=request_id, action=req.get("action"),
               resource_id=req.get("resource_id"), detail=detail)
        return {"status": target_status}

    try:
        return state_manager.atomic_update(mutate)
    except Exception as exc:
        return {"status": "blocked", "reason": "approval_state_unavailable",
                "error": type(exc).__name__}


def set_required(setting: str, *, required: bool, actor_uid: str) -> dict[str, Any]:
    setting = str(setting or "").strip()
    actor_uid = str(actor_uid or "")
    if not _is_owner(actor_uid):
        return {"status": "blocked", "reason": "owner_only"}
    if setting not in SETTING_NAMES or type(required) is not bool:
        return {"status": "blocked", "reason": "invalid_setting"}
    if required is False:
        return {"status": "confirmation_required", "reason": "disabling_requires_second_confirmation"}

    def mutate(db):
        # Enabling a gate is also the safe recovery path for a malformed policy.
        raw_row = db.get(POLICY_KEY)
        row = dict(raw_row) if isinstance(raw_row, dict) else {}
        required_map = row.get("required", {})
        if not isinstance(required_map, dict):
            required_map = {}
        normalized = {name: (required_map.get(name) if type(required_map.get(name)) is bool else True)
                      for name in SETTING_NAMES}
        normalized[setting] = True
        row.update(required=normalized, schema_version=1, updated_at=_iso(), updated_by=actor_uid)
        db[POLICY_KEY] = row
        _audit(db, "setting_enabled", actor_id=actor_uid, action=setting,
               detail="explicit approval required")
        return {"status": "ok", "setting": setting, "required": True, "settings": normalized}

    try:
        return state_manager.atomic_update(mutate)
    except Exception as exc:
        return {"status": "blocked", "reason": "policy_state_unavailable",
                "error": type(exc).__name__}


def propose_disable(setting: str, *, actor_uid: str) -> dict[str, Any]:
    setting = str(setting or "").strip()
    actor_uid = str(actor_uid or "")
    if not _is_owner(actor_uid):
        return {"status": "blocked", "reason": "owner_only"}
    if setting not in SETTING_NAMES:
        return {"status": "blocked", "reason": "invalid_setting"}
    change_id = uuid.uuid4().hex[:12]
    now = _now()

    def mutate(db):
        changes = db.get(CONFIG_CHANGES_KEY)
        if changes is None:
            changes = {}
            db[CONFIG_CHANGES_KEY] = changes
        if not isinstance(changes, dict):
            raise RuntimeError("HUMAN_INTERVENTION_CONFIG_CHANGE_STATE_MALFORMED")
        effective = _settings_from_db(db)["required"]
        if not effective[setting]:
            return {"status": "already_disabled", "setting": setting}
        changes[change_id] = {
            "id": change_id, "setting": setting, "required": False,
            "status": "pending", "requested_by": actor_uid,
            "created_at": now, "expires_at": now + CONFIG_CONFIRM_TTL_SECONDS,
        }
        _audit(db, "setting_disable_confirmation_requested", actor_id=actor_uid,
               request_id=change_id, action=setting,
               detail="second explicit confirmation required")
        return {"status": "confirmation_required", "setting": setting,
                "confirmation_id": change_id, "expires_at": now + CONFIG_CONFIRM_TTL_SECONDS}

    try:
        return state_manager.atomic_update(mutate)
    except Exception as exc:
        return {"status": "blocked", "reason": "policy_state_unavailable",
                "error": type(exc).__name__}


def confirm_disable(change_id: str, *, actor_uid: str) -> dict[str, Any]:
    actor_uid = str(actor_uid or "")
    if not _is_owner(actor_uid):
        return {"status": "blocked", "reason": "owner_only"}
    now = _now()

    def mutate(db):
        changes = db.get(CONFIG_CHANGES_KEY, {})
        change = changes.get(str(change_id)) if isinstance(changes, dict) else None
        if not isinstance(change, dict):
            return {"status": "blocked", "reason": "confirmation_not_found"}
        if change.get("status") != "pending":
            return {"status": "blocked", "reason": "confirmation_replayed",
                    "current_status": change.get("status")}
        if float(change.get("expires_at", 0) or 0) <= now:
            change["status"] = "expired"
            _audit(db, "setting_disable_confirmation_expired", actor_id=actor_uid,
                   request_id=change_id, action=change.get("setting"))
            return {"status": "blocked", "reason": "confirmation_expired"}
        setting = change.get("setting")
        if setting not in SETTING_NAMES:
            return {"status": "blocked", "reason": "invalid_setting"}
        row = db.get(POLICY_KEY)
        if row is not None and not isinstance(row, dict):
            raise RuntimeError("HUMAN_INTERVENTION_POLICY_MALFORMED")
        row = dict(row or {})
        required_map = row.get("required", {})
        if not isinstance(required_map, dict):
            raise RuntimeError("HUMAN_INTERVENTION_POLICY_MALFORMED")
        normalized = {name: (required_map.get(name) if type(required_map.get(name)) is bool else True)
                      for name in SETTING_NAMES}
        normalized[setting] = False
        row.update(required=normalized, schema_version=1, updated_at=_iso(now), updated_by=actor_uid)
        db[POLICY_KEY] = row
        change["status"] = "confirmed"
        change["confirmed_by"] = actor_uid
        change["confirmed_at"] = now
        _audit(db, "setting_disabled", actor_id=actor_uid, request_id=change_id,
               action=setting, detail="owner explicitly confirmed disabling approval gate")
        return {"status": "ok", "setting": setting, "required": False, "settings": normalized}

    try:
        return state_manager.atomic_update(mutate)
    except Exception as exc:
        return {"status": "blocked", "reason": "policy_state_unavailable",
                "error": type(exc).__name__}
