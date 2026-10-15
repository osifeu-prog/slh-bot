"""Fail-closed human approval policy for system command execution and completion."""
from __future__ import annotations

import hashlib
import shlex
import time
import uuid
from datetime import datetime, timezone

import state_manager
from core.authority import is_owner

STATE_KEY = "human_intervention"
DEFAULT_SETTINGS = {"action_execution": True, "action_completion": True}
VALID_SETTINGS = frozenset(DEFAULT_SETTINGS)
EXECUTION_TTL_SECONDS = 15 * 60
COMPLETION_TTL_SECONDS = 24 * 60 * 60
SETTING_CONFIRM_TTL_SECONDS = 5 * 60
MAX_COMMAND_CHARS = 20000


def _iso_now(timestamp=None):
    value = time.time() if timestamp is None else float(timestamp)
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def _command_hash(command):
    return hashlib.sha256(str(command).encode("utf-8")).hexdigest()


def _effective_settings(state):
    raw = state.get("settings") if isinstance(state, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    return {key: raw.get(key) if type(raw.get(key)) is bool else True for key in VALID_SETTINGS}


def _ensure_state(db):
    state = db.get(STATE_KEY)
    if not isinstance(state, dict):
        state = {}
        db[STATE_KEY] = state
    if not isinstance(state.get("settings"), dict):
        state["settings"] = {}
    for key, default in DEFAULT_SETTINGS.items():
        if type(state["settings"].get(key)) is not bool:
            state["settings"][key] = default
    if not isinstance(state.get("requests"), dict):
        state["requests"] = {}
    if not isinstance(state.get("setting_requests"), dict):
        state["setting_requests"] = {}
    if not isinstance(state.get("audit"), list):
        state["audit"] = []
    state.setdefault("schema_version", 1)
    return state


def _event(state, *, actor, action, request_id, decision, result, details=None):
    event = {
        "timestamp": _iso_now(),
        "actor": str(actor),
        "action": str(action),
        "request_id": str(request_id or ""),
        "decision": str(decision),
        "result": str(result),
    }
    if isinstance(details, dict) and details:
        event["details"] = {str(k): str(v)[:200] for k, v in details.items()}
    state["audit"].append(event)


def get_policy():
    """Read only; missing, malformed or unavailable values require approval."""
    try:
        db = state_manager.load_db()
        if not isinstance(db, dict):
            raise ValueError("INVALID_DB_ROOT")
        raw_state = db.get(STATE_KEY)
        raw_settings = raw_state.get("settings") if isinstance(raw_state, dict) else None
        if not isinstance(raw_settings, dict):
            return {**DEFAULT_SETTINGS, "available": True, "source": "default_fail_closed"}
        settings = {
            key: raw_settings.get(key) if type(raw_settings.get(key)) is bool else True
            for key in VALID_SETTINGS
        }
        malformed = any(type(raw_settings.get(key)) is not bool for key in VALID_SETTINGS)
        return {**settings, "available": True,
                "source": "default_fail_closed" if malformed else "persisted"}
    except Exception:
        return {**DEFAULT_SETTINGS, "available": False, "source": "unavailable_fail_closed"}


def is_read_only_command(command):
    """Only simple commands with no shell composition qualify as read-only."""
    text = str(command or "").strip()
    if not text or len(text) > MAX_COMMAND_CHARS:
        return False
    if any(char in text for char in ("\n", "\r", ";", "|", "&", ">", "<", "$")) or chr(96) in text:
        return False
    try:
        tokens = shlex.split(text)
    except ValueError:
        return False
    if not tokens or tokens[0].startswith("/") or tokens[0].startswith("./"):
        return False
    # Reads of canonical state, dotenv files, repository internals or system
    # procfs are not in the unattended-read allowlist.
    sensitive_fragments = (
        ".env", "state/", "db.json", ".git/", "/proc/", "/sys/",
        "credentials", "secrets", "private_key",
    )
    if any(
        fragment in token.replace("\\\\", "/").lower()
        for token in tokens[1:]
        for fragment in sensitive_fragments
    ):
        return False
    name = tokens[0]
    if name in {
        "pwd", "whoami", "ls", "stat", "file", "head", "tail", "cat",
        "grep", "rg", "nl", "wc", "du", "df", "printenv", "echo", "printf",
    }:
        return True
    if name == "find":
        blocked = {"-exec", "-execdir", "-ok", "-okdir", "-delete", "-fls", "-fprint", "-fprintf"}
        return not any(token in blocked for token in tokens[1:])
    if name == "sed":
        if any(token == "-i" or token.startswith("-i") for token in tokens[1:]):
            return False
        scripts = [token for token in tokens[1:] if not token.startswith("-")]
        return "-n" in tokens[1:] and bool(scripts) and all("e" not in token.lower() for token in scripts)
    if name == "git" and len(tokens) > 1:
        return tokens[1] in {"status", "log", "show", "diff", "rev-parse"}
    return False


def _new_id():
    return uuid.uuid4().hex[:12]


def create_execution_request(actor_uid, command, source="run_gated"):
    """Persist a command request; execute immediately only when approval is explicitly off."""
    actor_uid, command = str(actor_uid), str(command or "")
    if not is_owner(actor_uid):
        raise PermissionError("OWNER_ONLY")
    if not command.strip() or len(command) > MAX_COMMAND_CHARS:
        raise ValueError("INVALID_SYSTEM_ACTION_COMMAND")
    request_id, now = _new_id(), time.time()

    def mutate(db):
        state = _ensure_state(db)
        required = _effective_settings(state)["action_execution"]
        status = "pending_execution" if required else "approved_for_execution"
        record = {
            "id": request_id, "kind": "system_command", "command": command,
            "command_sha256": _command_hash(command), "source": str(source or "unknown")[:120],
            "requested_by": actor_uid, "created_at": now,
            "expires_at": now + EXECUTION_TTL_SECONDS, "status": status,
            "execution_approval_required": required,
        }
        state["requests"][request_id] = record
        _event(state, actor=actor_uid, action="action_execution", request_id=request_id,
               decision="requested", result=status,
               details={"source": record["source"], "command_sha256": record["command_sha256"]})
        if not required:
            record["execution_approved_by"] = "policy_disabled"
            record["execution_approved_at"] = now
            _event(state, actor=actor_uid, action="action_execution", request_id=request_id,
                   decision="not_required", result="policy_disabled")
        return {"id": request_id, "requires_approval": required, "status": status}

    return state_manager.atomic_update(mutate)


def create_registered_action_request(actor_uid, action_key, parameters=None, source="typed_action"):
    """Create a pending request for one server-defined callable action.

    Only the handler's fixed dispatch table may interpret action_key. No dynamic
    imports or callable names are accepted from the request.
    """
    actor_uid = str(actor_uid)
    action_key = str(action_key or "").strip()
    allowed = {"alpha_open", "railway_up"}
    if not is_owner(actor_uid):
        raise PermissionError("OWNER_ONLY")
    if action_key not in allowed:
        raise ValueError("UNREGISTERED_ACTION")
    parameters = parameters if isinstance(parameters, dict) else {}
    request_id, now = _new_id(), time.time()
    command = "registered-action:" + action_key

    def mutate(db):
        state = _ensure_state(db)
        # Typed system actions (deployment/Alpha transitions) always keep a
        # dedicated approval, even if the generic shell-action setting is off.
        required = True
        status = "pending_execution"
        record = {
            "id": request_id, "kind": "registered_action",
            "action_key": action_key, "parameters": parameters,
            "command": command, "command_sha256": _command_hash(command),
            "source": str(source or "unknown")[:120],
            "requested_by": actor_uid, "created_at": now,
            "expires_at": now + EXECUTION_TTL_SECONDS, "status": status,
            "execution_approval_required": required,
        }
        state["requests"][request_id] = record
        _event(
            state, actor=actor_uid, action="action_execution",
            request_id=request_id, decision="requested", result=status,
            details={"source": record["source"], "action_key": action_key},
        )
        if not required:
            record["execution_approved_by"] = "policy_disabled"
            record["execution_approved_at"] = now
            _event(
                state, actor=actor_uid, action="action_execution",
                request_id=request_id, decision="not_required", result="policy_disabled",
            )
        return {"id": request_id, "requires_approval": required, "status": status}

    return state_manager.atomic_update(mutate)


def create_preapproved_execution(actor_uid, command, source, approved_by):
    """Record an already-confirmed owner approval, such as /execr approval."""
    if not is_owner(approved_by):
        raise PermissionError("OWNER_APPROVAL_REQUIRED")
    request = create_execution_request(actor_uid, command, source=source)
    if request["requires_approval"]:
        decision = approve_execution(request["id"], approved_by)
        if not decision.get("ok"):
            raise ValueError(decision.get("error", "APPROVAL_FAILED"))
    return request["id"]


def get_request(request_id):
    try:
        db = state_manager.load_db()
        state = db.get(STATE_KEY, {}) if isinstance(db, dict) else {}
        requests = state.get("requests", {}) if isinstance(state, dict) else {}
        record = requests.get(str(request_id)) if isinstance(requests, dict) else None
        return dict(record) if isinstance(record, dict) else None
    except Exception:
        return None


def approve_execution(request_id, actor_uid):
    if not is_owner(actor_uid):
        return {"ok": False, "error": "OWNER_ONLY"}
    request_id, now = str(request_id or "").strip(), time.time()

    def mutate(db):
        state = _ensure_state(db)
        record = state["requests"].get(request_id)
        if not isinstance(record, dict):
            return {"ok": False, "error": "REQUEST_NOT_FOUND"}
        if record.get("status") != "pending_execution":
            return {"ok": False, "error": "REQUEST_NOT_PENDING"}
        if now > float(record.get("expires_at", 0) or 0):
            record["status"], record["command"] = "expired", ""
            _event(state, actor=actor_uid, action="action_execution", request_id=request_id,
                   decision="expired", result="stale_approval")
            return {"ok": False, "error": "REQUEST_EXPIRED"}
        record["status"] = "approved_for_execution"
        record["execution_approved_by"], record["execution_approved_at"] = str(actor_uid), now
        _event(state, actor=actor_uid, action="action_execution", request_id=request_id,
               decision="approved", result="approved_for_execution")
        return {"ok": True, "request_id": request_id}

    return state_manager.atomic_update(mutate)


def claim_execution(request_id, actor_uid, command):
    """Consume one approval for the exact approved command, preventing replay."""
    if not is_owner(actor_uid):
        return {"ok": False, "error": "OWNER_ONLY"}
    request_id, now, command = str(request_id or "").strip(), time.time(), str(command or "")

    def mutate(db):
        state = _ensure_state(db)
        record = state["requests"].get(request_id)
        if not isinstance(record, dict):
            return {"ok": False, "error": "REQUEST_NOT_FOUND"}
        if record.get("status") != "approved_for_execution":
            return {"ok": False, "error": "APPROVAL_NOT_AVAILABLE"}
        if now > float(record.get("expires_at", 0) or 0):
            record["status"], record["command"] = "expired", ""
            _event(state, actor=actor_uid, action="action_execution", request_id=request_id,
                   decision="expired", result="stale_approval")
            return {"ok": False, "error": "REQUEST_EXPIRED"}
        if record.get("command_sha256") != _command_hash(command) or record.get("command") != command:
            return {"ok": False, "error": "COMMAND_MISMATCH"}
        record["status"], record["execution_started_at"] = "executing", now
        _event(state, actor=actor_uid, action="action_execution", request_id=request_id,
               decision="consumed", result="execution_started")
        return {"ok": True, "request_id": request_id}

    return state_manager.atomic_update(mutate)


def record_execution_result(request_id, actor_uid, success, result_code="unknown"):
    request_id, now = str(request_id or "").strip(), time.time()

    def mutate(db):
        state = _ensure_state(db)
        record = state["requests"].get(request_id)
        if not isinstance(record, dict) or record.get("status") != "executing":
            return {"ok": False, "error": "ACTION_NOT_EXECUTING"}
        record["command"] = ""
        record["execution_result"] = str(result_code or "unknown")[:120]
        record["execution_finished_at"] = now
        if not success:
            record["status"] = "execution_failed"
            _event(state, actor=actor_uid, action="action_execution", request_id=request_id,
                   decision="result", result="execution_failed",
                   details={"result_code": record["execution_result"]})
            return {"ok": True, "status": record["status"]}
        if _effective_settings(state)["action_completion"]:
            record["status"] = "executed_pending_completion"
            record["completion_expires_at"] = now + COMPLETION_TTL_SECONDS
            _event(state, actor=actor_uid, action="action_completion", request_id=request_id,
                   decision="required", result="awaiting_owner_approval")
        else:
            record["status"], record["completed_at"] = "completed", now
            record["completed_by"] = "policy_disabled"
            _event(state, actor=actor_uid, action="action_completion", request_id=request_id,
                   decision="not_required", result="completed_by_policy")
        return {"ok": True, "status": record["status"]}

    return state_manager.atomic_update(mutate)


def fail_execution_request(request_id, actor_uid, result_code):
    """Record a block before execution without ever running the command."""
    request_id = str(request_id or "").strip()

    def mutate(db):
        state = _ensure_state(db)
        record = state["requests"].get(request_id)
        if not isinstance(record, dict) or record.get("status") not in {
            "approved_for_execution", "pending_execution",
        }:
            return {"ok": False, "error": "REQUEST_NOT_PENDING"}
        record["status"], record["command"] = "execution_failed", ""
        record["execution_result"] = str(result_code or "blocked")[:120]
        _event(state, actor=actor_uid, action="action_execution", request_id=request_id,
               decision="blocked", result=record["execution_result"])
        return {"ok": True, "status": record["status"]}

    return state_manager.atomic_update(mutate)


def deny_action(request_id, actor_uid):
    if not is_owner(actor_uid):
        return {"ok": False, "error": "OWNER_ONLY"}
    request_id, now = str(request_id or "").strip(), time.time()

    def mutate(db):
        state = _ensure_state(db)
        record = state["requests"].get(request_id)
        if not isinstance(record, dict):
            return {"ok": False, "error": "REQUEST_NOT_FOUND"}
        status = record.get("status")
        if status == "pending_execution":
            record["status"], record["command"] = "execution_rejected", ""
            action, result = "action_execution", "execution_denied_no_side_effects"
        elif status == "executed_pending_completion":
            record["status"] = "completion_rejected"
            action, result = "action_completion", "completion_denied_action_already_executed"
        else:
            return {"ok": False, "error": "REQUEST_NOT_PENDING"}
        record["denied_by"], record["denied_at"] = str(actor_uid), now
        _event(state, actor=actor_uid, action=action, request_id=request_id,
               decision="denied", result=result)
        return {"ok": True, "status": record["status"], "result": result}

    return state_manager.atomic_update(mutate)


def complete_action(request_id, actor_uid):
    if not is_owner(actor_uid):
        return {"ok": False, "error": "OWNER_ONLY"}
    request_id, now = str(request_id or "").strip(), time.time()

    def mutate(db):
        state = _ensure_state(db)
        record = state["requests"].get(request_id)
        if not isinstance(record, dict):
            return {"ok": False, "error": "REQUEST_NOT_FOUND"}
        if record.get("status") != "executed_pending_completion":
            return {"ok": False, "error": "COMPLETION_NOT_PENDING"}
        if now > float(record.get("completion_expires_at", 0) or 0):
            record["status"] = "completion_expired"
            _event(state, actor=actor_uid, action="action_completion", request_id=request_id,
                   decision="expired", result="stale_completion_approval")
            return {"ok": False, "error": "COMPLETION_EXPIRED"}
        record["status"], record["completed_by"], record["completed_at"] = "completed", str(actor_uid), now
        _event(state, actor=actor_uid, action="action_completion", request_id=request_id,
               decision="approved", result="completed")
        return {"ok": True, "status": "completed"}

    return state_manager.atomic_update(mutate)


def enable_setting(actor_uid, setting):
    if not is_owner(actor_uid):
        raise PermissionError("OWNER_ONLY")
    if setting not in VALID_SETTINGS:
        raise ValueError("INVALID_SETTING")

    def mutate(db):
        state = _ensure_state(db)
        state["settings"][setting] = True
        request_id = _new_id()
        _event(state, actor=actor_uid, action="setting:" + setting, request_id=request_id,
               decision="enabled", result="approval_required")
        return {"ok": True, "setting": setting, "enabled": True, "request_id": request_id}

    return state_manager.atomic_update(mutate)


def request_setting_disable(actor_uid, setting):
    if not is_owner(actor_uid):
        raise PermissionError("OWNER_ONLY")
    if setting not in VALID_SETTINGS:
        raise ValueError("INVALID_SETTING")
    request_id, now = _new_id(), time.time()

    def mutate(db):
        state = _ensure_state(db)
        if state["settings"].get(setting) is False:
            return {"ok": True, "already_disabled": True, "setting": setting}
        state["setting_requests"][request_id] = {
            "id": request_id, "setting": setting, "requested_by": str(actor_uid),
            "created_at": now, "expires_at": now + SETTING_CONFIRM_TTL_SECONDS,
            "status": "pending_confirmation",
        }
        _event(state, actor=actor_uid, action="setting:" + setting, request_id=request_id,
               decision="disable_requested", result="awaiting_explicit_confirmation")
        return {"ok": True, "setting": setting, "request_id": request_id,
                "requires_confirmation": True}

    return state_manager.atomic_update(mutate)


def confirm_setting_disable(request_id, actor_uid):
    if not is_owner(actor_uid):
        return {"ok": False, "error": "OWNER_ONLY"}
    request_id, now = str(request_id or "").strip(), time.time()

    def mutate(db):
        state = _ensure_state(db)
        request = state["setting_requests"].get(request_id)
        if not isinstance(request, dict):
            return {"ok": False, "error": "SETTING_REQUEST_NOT_FOUND"}
        if request.get("status") != "pending_confirmation":
            return {"ok": False, "error": "SETTING_REQUEST_NOT_PENDING"}
        if str(request.get("requested_by")) != str(actor_uid):
            return {"ok": False, "error": "SETTING_REQUEST_ACTOR_MISMATCH"}
        if now > float(request.get("expires_at", 0) or 0):
            request["status"] = "expired"
            _event(state, actor=actor_uid, action="setting:" + str(request.get("setting")),
                   request_id=request_id, decision="expired", result="setting_disable_not_applied")
            return {"ok": False, "error": "SETTING_REQUEST_EXPIRED"}
        setting = request.get("setting")
        if setting not in VALID_SETTINGS:
            request["status"] = "rejected"
            return {"ok": False, "error": "INVALID_SETTING"}
        state["settings"][setting] = False
        request["status"], request["confirmed_by"], request["confirmed_at"] = "confirmed", str(actor_uid), now
        _event(state, actor=actor_uid, action="setting:" + setting, request_id=request_id,
               decision="confirmed_disable", result="approval_not_required")
        return {"ok": True, "setting": setting, "enabled": False, "request_id": request_id}

    return state_manager.atomic_update(mutate)


def get_status():
    """Read-only settings and pending IDs; never returns command contents."""
    policy = get_policy()
    result = {
        "settings": {
            "action_execution": policy["action_execution"],
            "action_completion": policy["action_completion"],
        },
        "policy_available": policy["available"],
        "policy_source": policy["source"],
        "pending": [],
        "audit_events": None,
    }
    try:
        db = state_manager.load_db()
        state = db.get(STATE_KEY, {}) if isinstance(db, dict) else {}
        requests = state.get("requests", {}) if isinstance(state, dict) else {}
        if isinstance(requests, dict):
            pending_statuses = {
                "pending_execution", "executed_pending_completion",
                "execution_failed", "execution_rejected", "completion_rejected",
                "completion_expired",
            }
            for request_id, record in requests.items():
                if isinstance(record, dict) and record.get("status") in pending_statuses:
                    result["pending"].append({
                        "id": str(request_id), "status": str(record.get("status")),
                        "source": str(record.get("source") or "")[:80],
                        "created_at": record.get("created_at"),
                    })
        audit = state.get("audit", []) if isinstance(state, dict) else []
        result["audit_events"] = len(audit) if isinstance(audit, list) else None
    except Exception:
        result["policy_available"] = False
        result["policy_source"] = "unavailable_fail_closed"
        result["settings"] = dict(DEFAULT_SETTINGS)
    return result
