"""Controlled Telegram Developer Lab.

Developer proposals are stored as pending requests. Only OWNER approval can
turn a proposal into a GitHub branch + pull request. Production is never
modified directly by this module.
"""

from __future__ import annotations

import base64
import os
import re
import time
import uuid

import requests

import state_manager
from core.authority import get_role, is_owner

_SECRET_CONTENT = re.compile(
    r"(?i)(?:\b\d{8,12}:AA[A-Za-z0-9_-]{30,}\b|"
    r"\b(?:sk-|gsk_)[A-Za-z0-9_-]{20,}\b|"
    r"\bAIza[0-9A-Za-z_-]{30,}\b|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)


REPO = str(os.getenv("SLH_GITHUB_REPOSITORY", "osifeu-prog/slh-bot")).strip()
BASE_BRANCH = str(os.getenv("SLH_DEVELOPER_LAB_BASE", "main")).strip() or "main"
REQUESTS_KEY = "developer_lab_requests"
MAX_CONTENT = 24000

_ALLOWED_PREFIXES = ("core/", "handlers/", "tests/", "slh_mcp/")
_ALLOWED_ROOT_FILES = {"mini_app.html", "webapp.py", "README.md", "DEVELOPER_GUIDE.md"}
_PROTECTED = {
    ".env", ".env.example", "Dockerfile", "railway.json", "control_plane_registry.json",
    "core/authority.py", "core/exec_policy.py", "core/telegram_webapp_auth.py",
    "core/wallet_binding.py", "core/ton_wallet_binding.py", "core/ton_deposit_service.py",
    "core/bnb_gate.py", "core/bnb_deposit_service.py", "core/deposit_monitor.py",
    "core/economy_service.py", "core/railway_control.py",
    "handlers/deploy_handler.py", "handlers/git_handler.py", "handlers/exec_handler.py",
    "handlers/exec_request_handler.py", "handlers/e_handler.py",
}
_SECRET_WORDS = re.compile(r"(?i)(secret|password|private[_-]?key|api[_-]?key|bot[_-]?token|access[_-]?token|database[_-]?url)")
_PATH_RE = re.compile(r"^[A-Za-z0-9_./-]+$")


def _now() -> float:
    return time.time()


def _normalize_path(path: str) -> str:
    value = str(path or "").strip().replace("\\", "/")
    if not value or value.startswith("/") or ".." in value.split("/"):
        raise ValueError("INVALID_PATH")
    if not _PATH_RE.fullmatch(value):
        raise ValueError("INVALID_PATH")
    return value


def can_propose_path(path: str) -> bool:
    path = _normalize_path(path)
    if path in _PROTECTED or path.startswith(".github/") or path.startswith("state/"):
        return False
    if _SECRET_WORDS.search(path):
        return False
    return path in _ALLOWED_ROOT_FILES or path.startswith(_ALLOWED_PREFIXES)


def _github_headers() -> dict:
    token = str(os.getenv("GIT_TOKEN", "")).strip()
    if not token:
        raise RuntimeError("GIT_TOKEN_MISSING")
    return {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "SLH-Developer-Lab",
    }


def _github(method: str, path: str, **kwargs) -> requests.Response:
    url = "https://api.github.com" + path
    headers = _github_headers()
    extra = kwargs.pop("headers", {}) or {}
    headers.update(extra)
    response = requests.request(method, url, headers=headers, timeout=20, **kwargs)
    if response.status_code >= 400:
        raise RuntimeError(f"GITHUB_HTTP_{response.status_code}")
    return response


def _get_request(request_id: str) -> dict:
    db = state_manager.load_db()
    item = (db.get(REQUESTS_KEY, {}) or {}).get(str(request_id))
    if not isinstance(item, dict):
        raise KeyError("REQUEST_NOT_FOUND")
    return item


def submit_proposal(uid: str, path: str, content: str, summary: str) -> dict:
    uid = str(uid)
    if get_role(uid) not in {"DEVELOPER", "ADMIN", "OWNER"}:
        raise PermissionError("DEVELOPER_ACCESS_REQUIRED")
    path = _normalize_path(path)
    if not can_propose_path(path):
        raise PermissionError("PATH_NOT_ALLOWED")
    content = str(content or "")
    if not content.strip():
        raise ValueError("CONTENT_REQUIRED")
    if len(content.encode("utf-8")) > MAX_CONTENT:
        raise ValueError("CONTENT_TOO_LARGE")
    if _SECRET_CONTENT.search(content):
        raise ValueError("SECRET_CONTENT_BLOCKED")
    summary = str(summary or "Developer code change").strip()[:240]

    request_id = uuid.uuid4().hex[:10]
    item = {
        "id": request_id,
        "uid": uid,
        "path": path,
        "summary": summary or "Developer code change",
        "content_sha256": __import__("hashlib").sha256(content.encode("utf-8")).hexdigest(),
        "content": content,
        "status": "pending",
        "created_at": _now(),
    }

    def mutate(db):
        db.setdefault(REQUESTS_KEY, {})[request_id] = item
        return item

    return state_manager.atomic_update(mutate)



def read_file(path: str) -> dict:
    path = _normalize_path(path)
    if path.startswith(".git/") or path.startswith("state/") or _SECRET_WORDS.search(path):
        raise PermissionError("PATH_NOT_READABLE")
    if path in _PROTECTED:
        raise PermissionError("PATH_NOT_READABLE")
    if not (path in _ALLOWED_ROOT_FILES or path.startswith(_ALLOWED_PREFIXES)):
        raise PermissionError("PATH_NOT_READABLE")

    response = _github(
        "GET",
        f"/repos/{REPO}/contents/{path}",
        params={"ref": BASE_BRANCH},
    )
    data = response.json()
    if data.get("type") != "file":
        raise ValueError("NOT_A_FILE")
    raw = data.get("content", "")
    if data.get("encoding") == "base64":
        content = base64.b64decode(raw).decode("utf-8", errors="replace")
    else:
        content = str(raw)
    try:
        from core.exec_policy import redact_secrets
        content = redact_secrets(content)
    except Exception:
        pass
    return {
        "path": path,
        "size": len(content.encode("utf-8")),
        "content": content[:12000],
        "truncated": len(content) > 12000,
    }


def pending_requests() -> list[dict]:
    db = state_manager.load_db()
    rows = []
    for item in (db.get(REQUESTS_KEY, {}) or {}).values():
        if isinstance(item, dict) and item.get("status") == "pending":
            rows.append({
                k: item.get(k)
                for k in ("id", "uid", "path", "summary", "status", "created_at")
            })
    return sorted(rows, key=lambda x: x.get("created_at", 0))



def request_preview(request_id: str, actor_uid: str) -> dict:
    item = _get_request(request_id)
    actor_uid = str(actor_uid)
    if actor_uid != str(item.get("uid")) and not is_owner(actor_uid):
        raise PermissionError("FORBIDDEN")
    content = str(item.get("content") or "")
    try:
        from core.exec_policy import redact_secrets
        content = redact_secrets(content)
    except Exception:
        pass
    return {
        "id": request_id,
        "path": item.get("path"),
        "summary": item.get("summary"),
        "content": content[:3500],
        "truncated": len(content) > 3500,
        "content_sha256": item.get("content_sha256"),
        "status": item.get("status"),
    }


def request_status(request_id: str, actor_uid: str) -> dict:
    item = _get_request(request_id)
    actor_uid = str(actor_uid)
    if actor_uid != str(item.get("uid")) and not is_owner(actor_uid):
        raise PermissionError("FORBIDDEN")
    return {
        k: item.get(k)
        for k in (
            "id", "uid", "path", "summary", "status", "created_at",
            "approved_at", "approved_by", "branch", "pr_number", "pr_url",
            "ci_total", "ci_checks", "error",
        )
    }


def approve_proposal(request_id: str, actor_uid: str) -> dict:
    actor_uid = str(actor_uid)
    if not is_owner(actor_uid):
        raise PermissionError("OWNER_ONLY")
    item = _get_request(request_id)
    if item.get("status") != "pending":
        return request_status(request_id, actor_uid)

    path = _normalize_path(item["path"])
    if not can_propose_path(path):
        raise PermissionError("PATH_NOT_ALLOWED")

    ref = _github("GET", f"/repos/{REPO}/git/ref/heads/{BASE_BRANCH}").json()
    base_sha = str(ref["object"]["sha"])

    branch = f"dev/{item['uid']}/{item['id']}"
    _github(
        "POST",
        f"/repos/{REPO}/git/refs",
        json={"ref": f"refs/heads/{branch}", "sha": base_sha},
    )

    existing_sha = None
    try:
        existing = _github(
            "GET",
            f"/repos/{REPO}/contents/{path}",
            params={"ref": branch},
        ).json()
        existing_sha = existing.get("sha")
    except RuntimeError as exc:
        if str(exc) != "GITHUB_HTTP_404":
            raise

    payload = {
        "message": f"dev: {item['summary']}",
        "content": base64.b64encode(item["content"].encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if existing_sha:
        payload["sha"] = existing_sha

    _github("PUT", f"/repos/{REPO}/contents/{path}", json=payload)

    pr = _github(
        "POST",
        f"/repos/{REPO}/pulls",
        json={
            "title": item["summary"],
            "head": branch,
            "base": BASE_BRANCH,
            "body": (
                "Created through SLH Developer Lab.\n\n"
                f"Developer UID: {item['uid']}\n"
                f"Path: {path}\n"
                "Production deploy is not automatic."
            ),
        },
    ).json()

    result = {
        "id": request_id,
        "status": "pr_open",
        "uid": item["uid"],
        "path": path,
        "summary": item["summary"],
        "branch": branch,
        "pr_number": int(pr["number"]),
        "pr_url": pr.get("html_url"),
        "approved_at": _now(),
        "approved_by": actor_uid,
    }

    def mutate(db):
        stored = db.setdefault(REQUESTS_KEY, {}).get(request_id)
        if stored is None:
            return result
        stored.update(result)
        stored.pop("content", None)
        return {k: stored.get(k) for k in result}

    return state_manager.atomic_update(mutate)


def reject_proposal(request_id: str, actor_uid: str) -> dict:
    actor_uid = str(actor_uid)
    if not is_owner(actor_uid):
        raise PermissionError("OWNER_ONLY")
    _get_request(request_id)

    def mutate(db):
        stored = db.setdefault(REQUESTS_KEY, {}).get(request_id)
        if stored:
            stored["status"] = "rejected"
            stored["rejected_at"] = _now()
            stored["rejected_by"] = actor_uid
            stored.pop("content", None)
            return {
                k: stored.get(k)
                for k in (
                    "id", "uid", "path", "summary", "status", "created_at",
                    "rejected_at", "rejected_by",
                )
            }
        return {"id": str(request_id), "status": "rejected"}

    return state_manager.atomic_update(mutate)


def ci_status(request_id: str, actor_uid: str) -> dict:
    item = _get_request(request_id)
    actor_uid = str(actor_uid)
    if actor_uid != str(item.get("uid")) and not is_owner(actor_uid):
        raise PermissionError("FORBIDDEN")
    pr_number = item.get("pr_number")
    if not pr_number:
        raise ValueError("PR_NOT_CREATED")

    pr = _github("GET", f"/repos/{REPO}/pulls/{int(pr_number)}").json()
    sha = str(pr["head"]["sha"])
    checks = _github(
        "GET",
        f"/repos/{REPO}/commits/{sha}/check-runs",
        params={"per_page": 100},
    ).json()
    rows = [
        {
            "name": item.get("name"),
            "status": item.get("status"),
            "conclusion": item.get("conclusion"),
        }
        for item in checks.get("check_runs", [])
    ]
    result = {
        "id": request_id,
        "status": item.get("status"),
        "pr_number": int(pr_number),
        "pr_url": pr.get("html_url"),
        "sha": sha,
        "ci_total": int(checks.get("total_count", 0)),
        "ci_checks": rows,
    }

    def mutate(db):
        stored = db.setdefault(REQUESTS_KEY, {}).get(request_id)
        if stored:
            stored.update(result)
        return result

    return state_manager.atomic_update(mutate)
