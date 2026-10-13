"""Owner-only, read-only live connection checks for GitHub and Railway.

Reports provider reachability/authentication without printing tokens or mutating
provider configuration, deployments, balances, or ledgers.
"""
from datetime import datetime, timezone
import json
import os
import urllib.error
import urllib.request

from core.authority import is_owner


GITHUB_API = "https://api.github.com"
GITHUB_REPO = "osifeu-prog/slh-bot"


def _github_check():
    token = str(os.getenv("GIT_TOKEN") or os.getenv("GITHUB_TOKEN") or "").strip()
    if not token:
        return "BLOCKED", "GITHUB_TOKEN_MISSING"
    request = urllib.request.Request(
        GITHUB_API + "/repos/" + GITHUB_REPO,
        headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "SLH-Connections-Status",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                if isinstance(data, dict) and data.get("full_name", "").lower() == GITHUB_REPO:
                    return "PASS", "REPOSITORY_READ_OK"
                return "BLOCKED", "GITHUB_RESPONSE_INVALID"
            return "BLOCKED", "GITHUB_HTTP_" + str(response.status)
    except urllib.error.HTTPError as exc:
        return "BLOCKED", "GITHUB_HTTP_" + str(exc.code)
    except Exception as exc:
        return "UNKNOWN", "GITHUB_REQUEST_FAILED_" + type(exc).__name__


def _railway_check():
    # Reuse the existing explicitly scoped Project Token validation. Do not
    # fall back to Railway-injected metadata or expose credential values.
    try:
        from handlers.railway_control_handler import _ids, _graphql
        ctx = _ids()
        scope = _graphql(ctx, "query { projectToken { projectId environmentId } }").get("projectToken")
        if not isinstance(scope, dict):
            return "BLOCKED", "RAILWAY_PROJECT_TOKEN_REQUIRED"
        if (str(scope.get("projectId") or "") != ctx["project_id"]
                or str(scope.get("environmentId") or "") != ctx["environment_id"]):
            return "BLOCKED", "RAILWAY_TOKEN_SCOPE_MISMATCH"
        return "PASS", "PROJECT_TOKEN_SCOPE_READ_OK"
    except Exception as exc:
        detail = str(exc).split(":", 1)[0][:80]
        return "BLOCKED", detail or type(exc).__name__


def connections_status_text():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    gh_status, gh_reason = _github_check()
    rw_status, rw_reason = _railway_check()
    overall = "PASS" if gh_status == rw_status == "PASS" else (
        "FAIL" if "FAIL" in (gh_status, rw_status) else "ATTENTION"
    )
    return "\n".join([
        "🔎 SLH CONNECTIONS STATUS — READ ONLY",
        "Overall: " + overall,
        "Checked at (UTC): " + now,
        "",
        "GitHub: " + gh_status,
        "Reason: " + gh_reason,
        "Check: authenticated repository read",
        "",
        "Railway: " + rw_status,
        "Reason: " + rw_reason,
        "Check: explicitly scoped Project Token read",
        "",
        "No secrets displayed. No provider settings, deployments, balances, or ledgers changed.",
        "PASS means this runtime authenticated and completed the specified read check; it does not imply every provider feature is authorized.",
    ])


def register(bot):
    @bot.message_handler(commands=["connections_status"])
    def connections_status(message):
        uid = str(getattr(getattr(message, "from_user", None), "id", "") or "")
        if not is_owner(uid):
            bot.reply_to(message, "⛔ OWNER only", parse_mode=None)
            return
        if str(getattr(getattr(message, "chat", None), "type", "") or "").lower() != "private":
            bot.reply_to(message, "⛔ Run this read-only status command in private chat.", parse_mode=None)
            return
        bot.reply_to(message, connections_status_text(), parse_mode=None)
