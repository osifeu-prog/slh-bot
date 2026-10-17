"""Owner-only Railway controls. Only a preview-confirmed Treasury config repair is allowed."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import re
import uuid
import urllib.error
import urllib.request

import state_manager
from core.authority import is_owner

API_URL = "https://backboard.railway.com/graphql/v2"
PENDING_KEY = "railway_control_pending"
AUDIT_KEY = "railway_control_audit"
TTL_SECONDS = 300
ADDR = re.compile(r"^0x[0-9a-fA-F]{40}$")


def _ids():
    # Keep target IDs explicit and operator-managed. A project-token candidate
    # may come from SLH_RAILWAY_TOKEN or a standard Railway project-token variable;
    # _snapshot() verifies its project/environment scope before any control action.
    values = {
        "token": str(
            os.getenv("SLH_RAILWAY_TOKEN")
            or os.getenv("RAILWAY_PROJECT_TOKEN")
            or os.getenv("RAILWAY_PROJECT_TOKEN_SLH")
            or os.getenv("RAILWAY_TOKEN")
            or ""
        ).strip(),
        "project_id": str(os.getenv("SLH_RAILWAY_PROJECT_ID") or "").strip(),
        "environment_id": str(os.getenv("SLH_RAILWAY_ENVIRONMENT_ID") or "").strip(),
        "service_id": str(os.getenv("SLH_RAILWAY_SERVICE_ID") or "").strip(),
    }
    missing = [key.upper() for key, value in values.items() if not value]
    if missing:
        raise RuntimeError("SLH_RAILWAY_CREDENTIALS_MISSING:" + ",".join(missing))
    return values


def _graphql(ctx, query, variables=None):
    payload = json.dumps({"query": query, "variables": variables or {}}).encode()
    request = urllib.request.Request(
        API_URL, data=payload, method="POST",
        headers={"Project-Access-Token": ctx["token"],
                 "Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError("RAILWAY_API_REQUEST_FAILED:" + type(exc).__name__) from None
    if not isinstance(body, dict) or body.get("errors") or not isinstance(body.get("data"), dict):
        raise RuntimeError("RAILWAY_GRAPHQL_ERROR")
    return body["data"]


def _variables(ctx, service_id):
    query = (
        "query variables($projectId: String!, $environmentId: String!, "
        "$serviceId: String, $unrendered: Boolean) { variables("
        "projectId: $projectId, environmentId: $environmentId, "
        "serviceId: $serviceId, unrendered: $unrendered) }"
    )
    data = _graphql(ctx, query, {
        "projectId": ctx["project_id"], "environmentId": ctx["environment_id"],
        "serviceId": service_id, "unrendered": True,
    })
    result = data.get("variables")
    if not isinstance(result, dict):
        raise RuntimeError("RAILWAY_VARIABLES_INVALID")
    return result


def _snapshot():
    ctx = _ids()
    scope = _graphql(ctx, "query { projectToken { projectId environmentId } }").get("projectToken")
    if not isinstance(scope, dict):
        raise RuntimeError("RAILWAY_PROJECT_TOKEN_REQUIRED")
    if (str(scope.get("projectId") or "") != ctx["project_id"]
            or str(scope.get("environmentId") or "") != ctx["environment_id"]):
        raise RuntimeError("RAILWAY_TOKEN_SCOPE_MISMATCH")

    variables = {**_variables(ctx, None), **_variables(ctx, ctx["service_id"])}
    canonical = str(variables.get("SLH_BSC_CANONICAL_TREASURY") or "").strip()
    gate = str(variables.get("BNB_DEPOSITS_OPEN") or "").strip()
    raw = str(variables.get("SLH_BSC_CONFIG") or "").strip()
    if not ADDR.fullmatch(canonical):
        raise RuntimeError("CANONICAL_TREASURY_INVALID_OR_MISSING")
    if not raw:
        raise RuntimeError("SLH_BSC_CONFIG_MISSING")
    try:
        config = json.loads(raw)
    except (TypeError, ValueError):
        raise RuntimeError("SLH_BSC_CONFIG_INVALID_JSON") from None
    if not isinstance(config, dict):
        raise RuntimeError("SLH_BSC_CONFIG_NOT_OBJECT")
    current = str(config.get("treasury_wallet") or "").strip()
    if not ADDR.fullmatch(current):
        raise RuntimeError("TREASURY_IN_CONFIG_INVALID_OR_MISSING")
    return {
        "ctx": ctx, "vars": variables, "canonical": canonical, "gate": gate,
        "raw": raw, "config": config, "current": current,
        "config_hash": hashlib.sha256(raw.encode()).hexdigest(),
    }


def _updated_config(raw, target):
    if not ADDR.fullmatch(str(target or "").strip()):
        raise ValueError("TREASURY_TARGET_INVALID")
    try:
        config = json.loads(raw)
    except (TypeError, ValueError):
        raise ValueError("SLH_BSC_CONFIG_INVALID_JSON") from None
    if not isinstance(config, dict):
        raise ValueError("SLH_BSC_CONFIG_NOT_OBJECT")
    previous = str(config.get("treasury_wallet") or "").strip()
    if not ADDR.fullmatch(previous):
        raise ValueError("TREASURY_IN_CONFIG_INVALID_OR_MISSING")
    updated = dict(config)
    updated["treasury_wallet"] = target
    return json.dumps(updated, separators=(",", ":"), ensure_ascii=False), previous


def _update_and_redeploy(ctx, raw_new):
    result = _graphql(
        ctx,
        "mutation variableCollectionUpsert($input: VariableCollectionUpsertInput!) "
        "{ variableCollectionUpsert(input: $input) }",
        {"input": {
            "projectId": ctx["project_id"],
            "environmentId": ctx["environment_id"],
            "serviceId": ctx["service_id"],
            "variables": {"SLH_BSC_CONFIG": raw_new},
            "skipDeploys": True,
        }},
    )
    if result.get("variableCollectionUpsert") is not True:
        raise RuntimeError("RAILWAY_VARIABLE_UPSERT_UNCONFIRMED")
    deployed = _graphql(
        ctx,
        "mutation serviceInstanceRedeploy($serviceId: String!, $environmentId: String!) "
        "{ serviceInstanceRedeploy(serviceId: $serviceId, environmentId: $environmentId) }",
        {"serviceId": ctx["service_id"], "environmentId": ctx["environment_id"]},
    )
    if deployed.get("serviceInstanceRedeploy") is not True:
        return "VARIABLE_UPDATED_DEPLOY_UNCONFIRMED"
    return "DEPLOY_TRIGGERED"


def _runtime_state():
    try:
        from core.binance_connector import get_bsc_config
        from core.bnb_gate import _effective_config
        db = state_manager.load_db()
        return (
            str(get_bsc_config().get("treasury_wallet") or ""),
            str(_effective_config(db).get("treasury_wallet") or ""),
        )
    except Exception:
        return ("UNKNOWN", "UNKNOWN")


def railway_status_reply():
    try:
        s = _snapshot()
    except Exception as exc:
        return ("🔎 RAILWAY STATUS — READ ONLY\nAPI: BLOCKED\n"
                f"Reason: {str(exc)[:120]}\nNo secrets printed; no changes made.")
    runtime, db = _runtime_state()
    target = s["canonical"].lower()
    return "\n".join([
        "🔎 RAILWAY STATUS — READ ONLY",
        "Project token scope: PASS",
        "Remote config match: " + ("PASS" if s["current"].lower() == target else "MISMATCH"),
        "Runtime config match: " + ("PASS" if runtime.lower() == target else "MISMATCH"),
        "Database Treasury match: " + ("PASS" if db.lower() == target else "MISMATCH"),
        "BNB_DEPOSITS_OPEN: " + (s["gate"] or "UNSET"),
        "BNB gate closed: " + ("PASS" if s["gate"] == "0" else "BLOCKED"),
        "READ ONLY: no settings changed and no deploy triggered.",
    ])


def _add_audit(db, record, status, detail=""):
    audit = db.setdefault(AUDIT_KEY, [])
    if not isinstance(audit, list):
        audit = []
        db[AUDIT_KEY] = audit
    audit.append({
        "at": datetime.now(timezone.utc).isoformat(),
        "uid": record.get("uid"), "status": status,
        "previous_treasury": record.get("previous_treasury"),
        "target": record.get("target"),
        "changed_variable": "SLH_BSC_CONFIG.treasury_wallet",
        "bnb_gate_changed": False, "ledger_changed": False,
        "transaction_sent": False, "detail": str(detail)[:120],
    })
    del audit[:-50]


def prepare_railway_vars(uid):
    uid = str(uid or "").strip()
    if not is_owner(uid):
        return {"status": "FORBIDDEN"}
    try:
        s = _snapshot()
    except Exception as exc:
        return {"status": "BLOCKED", "detail": str(exc)[:120]}
    if s["gate"] != "0":
        return {"status": "BLOCKED", "detail": "BNB_DEPOSITS_OPEN_MUST_EQUAL_ZERO"}
    if s["current"].lower() == s["canonical"].lower():
        return {"status": "ALREADY_MATCHED", "target": s["canonical"]}
    now = datetime.now(timezone.utc)
    record = {
        "code": uuid.uuid4().hex[:10], "uid": uid, "status": "PENDING_CONFIRMATION",
        "target": s["canonical"], "previous_treasury": s["current"],
        "config_hash": s["config_hash"],
        "project_id": s["ctx"]["project_id"], "environment_id": s["ctx"]["environment_id"],
        "service_id": s["ctx"]["service_id"], "gate": s["gate"],
        "expires_at": (now + timedelta(seconds=TTL_SECONDS)).isoformat(),
    }
    def save(db):
        pending = db.setdefault(PENDING_KEY, {})
        if not isinstance(pending, dict):
            pending = {}
            db[PENDING_KEY] = pending
        pending[uid] = record
        return True
    try:
        state_manager.atomic_update(save)
    except Exception:
        return {"status": "BLOCKED", "detail": "PREVIEW_RECORD_WRITE_FAILED"}
    return {
        "status": "PREPARED", "code": record["code"],
        "previous_treasury": s["current"], "target": s["canonical"],
        "token_contract": s["config"].get("token_contract"),
        "expires_at": record["expires_at"],
    }


def _finish(uid, code, status, detail=""):
    def save(db):
        pending = db.get(PENDING_KEY, {}) if isinstance(db, dict) else {}
        record = pending.get(uid) if isinstance(pending, dict) else None
        if not isinstance(record, dict) or record.get("code") != code:
            return False
        record["status"] = status
        record["detail"] = str(detail)[:120]
        _add_audit(db, record, status, detail)
        return True
    try:
        state_manager.atomic_update(save)
    except Exception:
        pass
    return {"status": status, "detail": str(detail)[:120]}


def apply_railway_vars(uid, code):
    uid, code = str(uid or "").strip(), str(code or "").strip()
    if not is_owner(uid):
        return {"status": "FORBIDDEN"}
    try:
        db = state_manager.load_db()
        pending_map = db.get(PENDING_KEY, {}) if isinstance(db, dict) else {}
        record = pending_map.get(uid) if isinstance(pending_map, dict) else None
    except Exception:
        return {"status": "BLOCKED", "detail": "PREVIEW_RECORD_READ_FAILED"}
    if not isinstance(record, dict) or record.get("code") != code:
        return {"status": "NOT_PENDING"}
    if record.get("status") != "PENDING_CONFIRMATION":
        return {"status": "ALREADY_HANDLED"}
    try:
        expires = datetime.fromisoformat(record["expires_at"]).astimezone(timezone.utc)
    except Exception:
        return {"status": "BLOCKED", "detail": "PREVIEW_EXPIRY_INVALID"}
    if datetime.now(timezone.utc) >= expires:
        return _finish(uid, code, "EXPIRED")

    def claim(db_live):
        pending = db_live.get(PENDING_KEY, {}) if isinstance(db_live, dict) else {}
        item = pending.get(uid) if isinstance(pending, dict) else None
        if not isinstance(item, dict) or item.get("code") != code or item.get("status") != "PENDING_CONFIRMATION":
            return False
        item["status"] = "APPLYING"
        return True
    try:
        if not state_manager.atomic_update(claim):
            return {"status": "ALREADY_HANDLED"}
    except Exception:
        return {"status": "BLOCKED", "detail": "PREVIEW_CLAIM_FAILED"}

    try:
        s = _snapshot()
        if s["gate"] != "0":
            raise RuntimeError("BNB_DEPOSITS_OPEN_MUST_EQUAL_ZERO")
        for key in ("project_id", "environment_id", "service_id"):
            if s["ctx"][key] != record[key]:
                raise RuntimeError("RAILWAY_SCOPE_CHANGED_AFTER_PREVIEW")
        if s["canonical"].lower() != record["target"].lower():
            raise RuntimeError("CANONICAL_TARGET_CHANGED_AFTER_PREVIEW")
        if s["config_hash"] != record["config_hash"] or s["current"].lower() != record["previous_treasury"].lower():
            raise RuntimeError("SLH_BSC_CONFIG_CHANGED_AFTER_PREVIEW")

        raw_new, _previous = _updated_config(s["raw"], s["canonical"])
        ctx = s["ctx"]
        deployment_status = _update_and_redeploy(ctx, raw_new)
        if deployment_status != "DEPLOY_TRIGGERED":
            return _finish(uid, code, deployment_status)
        return _finish(uid, code, "DEPLOY_TRIGGERED")
    except Exception as exc:
        return _finish(uid, code, "BLOCKED", str(exc)[:120])


def _format(result):
    status = str(result.get("status") or "BLOCKED")
    if status == "FORBIDDEN":
        return "⛔ הפקודה זמינה לבעלים בלבד."
    if status == "ALREADY_MATCHED":
        return f"✅ Railway config כבר תואם ליעד: {result.get('target')}\nלא בוצע שינוי ולא הופעלה פריסה."
    if status == "PREPARED":
        return "\n".join([
            "🔎 Railway preview בלבד — לא בוצע שינוי.",
            f"treasury_wallet: {result.get('previous_treasury')} → {result.get('target')}",
            f"token_contract נשמר: {result.get('token_contract')}",
            "BNB_DEPOSITS_OPEN נשאר 0; לא נשלחה עסקה ולא שונו יתרות/ledger.",
            f"פג תוקף: {result.get('expires_at')}",
            f"לאישור ולפריסה: /railway_vars_apply {result.get('code')}",
        ])
    if status == "DEPLOY_TRIGGERED":
        return "✅ Railway קיבל את עדכון SLH_BSC_CONFIG ובקשת הפריסה. לאחר שהבוט חוזר, הרץ /railway_status לאימות. BNB נשאר CLOSED."
    if status == "VARIABLE_UPDATED_DEPLOY_UNCONFIRMED":
        return "⚠️ המשתנה עודכן אך הפריסה לא אושרה. הרץ /railway_status לפני כל ניסיון נוסף. BNB נשאר CLOSED."
    if status == "EXPIRED":
        return "⌛ התצוגה פגה. לא בוצע שינוי."
    if status == "NOT_PENDING":
        return "⛔ אין תצוגה תקפה לקוד הזה. הרץ /railway_vars_preview מחדש."
    if status == "ALREADY_HANDLED":
        return "⛔ התצוגה כבר טופלה. הרץ /railway_status."
    return "⛔ Railway operation blocked safely: " + str(result.get("detail") or status)


def connections_status_reply():
    """Read-only check of runtime connection configuration and API reachability.

    Never returns credential values. The only remote calls are a GitHub GET and
    a Railway projectToken GraphQL query; this function performs no mutations.
    """
    lines = ["🔗 SLH CONNECTIONS — READ ONLY"]

    github_token = (
        os.getenv("GITHUB_TOKEN")
        or os.getenv("GH_TOKEN")
        or os.getenv("GITHUB_TOKEN_SLH")
        or os.getenv("GIT_TOKEN")
    )
    git_writer_token = os.getenv("GIT_TOKEN") or os.getenv("GITHUB_TOKEN")
    railway_account_token = (
        os.getenv("RAILWAY_API_TOKEN") or os.getenv("RAILWAY_API_TOKEN_SLH")
    )
    railway_project_token = (
        os.getenv("SLH_RAILWAY_TOKEN")
        or os.getenv("RAILWAY_PROJECT_TOKEN")
        or os.getenv("RAILWAY_PROJECT_TOKEN_SLH")
        or os.getenv("RAILWAY_TOKEN")
    )
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "SLH-Connections-Status",
    }
    if github_token:
        headers["Authorization"] = "Bearer " + github_token

    request = urllib.request.Request(
        "https://api.github.com/repos/osifeu-prog/slh-bot",
        headers=headers,
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            body = json.loads(response.read().decode("utf-8"))
        if str(body.get("full_name") or "").lower() == "osifeu-prog/slh-bot":
            github_read = "PASS"
        else:
            github_read = "UNEXPECTED_RESPONSE"
    except urllib.error.HTTPError as exc:
        github_read = "HTTP_" + str(int(exc.code))
    except Exception as exc:
        github_read = "UNREACHABLE_" + type(exc).__name__

    lines.append("GitHub API read: " + github_read)
    lines.append(
        "GitHub write credential (/git commit): "
        + ("CONFIGURED (write permission not tested)" if git_writer_token else "MISSING")
    )
    lines.append(
        "Railway account/workspace token (cross-project targets): "
        + ("CONFIGURED (not probed here)" if railway_account_token else "MISSING — RAILWAY_API_TOKEN")
    )
    lines.append(
        "Railway project token candidate (single project/environment): "
        + ("CONFIGURED (scope checked below)" if railway_project_token else "MISSING")
    )
    lines.append(
        "Railway core control credential: "
        + ("CONFIGURED (scope checked below)" if (railway_account_token or railway_project_token) else "MISSING")
    )

    try:
        ctx = _ids()
        scope = _graphql(
            ctx,
            "query { projectToken { projectId environmentId } }",
        ).get("projectToken")
        if not isinstance(scope, dict):
            railway_scoped = "BLOCKED — RAILWAY_PROJECT_TOKEN_REQUIRED"
        elif (
            str(scope.get("projectId") or "") != ctx["project_id"]
            or str(scope.get("environmentId") or "") != ctx["environment_id"]
        ):
            railway_scoped = "BLOCKED — RAILWAY_TOKEN_SCOPE_MISMATCH"
        else:
            railway_scoped = "PASS — scoped project/environment verified"
    except Exception as exc:
        code = str(exc or "").split(":", 1)[0]
        if not code or len(code) > 72 or not re.fullmatch(r"[A-Z0-9_]+", code):
            code = "RAILWAY_CHECK_FAILED"
        railway_scoped = "BLOCKED — " + code

    lines.append("SLH scoped Railway integration: " + railway_scoped)
    lines.extend([
        "",
        "No secrets printed. No variables, balances, ledgers, gates, or deployments changed.",
    ])
    return "\n".join(lines)


def register(bot):
    @bot.message_handler(commands=["connections_status"])
    def connections_status(message):
        uid = str(getattr(getattr(message, "from_user", None), "id", "") or "")
        if not is_owner(uid):
            bot.reply_to(message, "⛔ OWNER only", parse_mode=None)
            return
        if str(getattr(getattr(message, "chat", None), "type", "") or "").lower() != "private":
            bot.reply_to(message, "⛔ Connection status is available in private chat only.", parse_mode=None)
            return
        bot.reply_to(message, connections_status_reply(), parse_mode=None)

    @bot.message_handler(commands=["railway_status"])
    def railway_status(message):
        uid = str(getattr(getattr(message, "from_user", None), "id", "") or "")
        if not is_owner(uid):
            bot.reply_to(message, "⛔ OWNER only", parse_mode=None)
            return
        if str(getattr(getattr(message, "chat", None), "type", "") or "").lower() != "private":
            bot.reply_to(message, "⛔ Railway controls available in private chat only.", parse_mode=None)
            return
        bot.reply_to(message, railway_status_reply(), parse_mode=None)

    @bot.message_handler(commands=["railway_vars_preview"])
    def railway_vars_preview(message):
        uid = str(getattr(getattr(message, "from_user", None), "id", "") or "")
        if not is_owner(uid):
            bot.reply_to(message, "⛔ OWNER only", parse_mode=None)
            return
        if str(getattr(getattr(message, "chat", None), "type", "") or "").lower() != "private":
            bot.reply_to(message, "⛔ Railway controls available in private chat only.", parse_mode=None)
            return
        bot.reply_to(message, _format(prepare_railway_vars(uid)), parse_mode=None)

    @bot.message_handler(commands=["railway_vars_apply"])
    def railway_vars_apply(message):
        uid = str(getattr(getattr(message, "from_user", None), "id", "") or "")
        if not is_owner(uid):
            bot.reply_to(message, "⛔ OWNER only", parse_mode=None)
            return
        if str(getattr(getattr(message, "chat", None), "type", "") or "").lower() != "private":
            bot.reply_to(message, "⛔ Railway controls available in private chat only.", parse_mode=None)
            return
        parts = (getattr(message, "text", "") or "").split(maxsplit=1)
        if len(parts) != 2:
            bot.reply_to(message, "שימוש: /railway_vars_apply <preview_code>", parse_mode=None)
            return
        bot.reply_to(message, _format(apply_railway_vars(uid, parts[1])), parse_mode=None)
