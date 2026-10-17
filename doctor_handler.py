import os
import json
import subprocess
from pathlib import Path


FEDERATION_REGISTRY_STALE_DAYS = 7
REQUIRED_RUNTIME_COMMANDS = {
    "/start",
    "/help",
    "/doctor",
    "/check_bnb",
    "/check_ton",
    "/check_exchange",
    "/health_monitor",
}


def _git_status_label(repo_dir="."):
    """Report Git state only when the deployed runtime can actually inspect it."""
    root = Path(repo_dir)
    if not (root / ".git").exists():
        return "⚪️ לא ניתן לאמת Git מתוך image הפרודקשן"
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except Exception:
        return "⚪️ מצב Git לא אומת"
    if result.returncode != 0:
        return "⚪️ מצב Git לא אומת"
    return "🟡 יש שינויים מקומיים" if result.stdout.strip() else "🟢 clean"


def _deployment_source_label():
    """Report immutable deployment provenance without pretending Git exists in the image."""
    commit = str(
        os.getenv("RAILWAY_GIT_COMMIT_SHA")
        or os.getenv("COMMIT_SHA")
        or ""
    ).strip()
    branch = str(
        os.getenv("RAILWAY_GIT_BRANCH")
        or os.getenv("BRANCH")
        or ""
    ).strip()
    if commit:
        detail = f"🟢 deployed commit {commit[:12]}"
        if branch:
            detail += f" · branch {branch[:60]}"
        return detail
    return _git_status_label()


def _overall_health_label(checks):
    values = [str(value) for key, value in checks.items() if key != "Health"]
    if any("🔴" in value for value in values):
        return "🔴 נמצאו כשלים בבדיקות"
    if any(marker in value for value in values for marker in ("🟡", "⚪️", "⚠️")):
        return "🟡 חלק מהבדיקות דורשות אימות"
    return "🟢 כל הבדיקות שנכללו עברו"


def _runtime_commands_label(bot):
    """Read command evidence from this exact live bot instance."""
    try:
        from core.runtime_command_evidence import snapshot_bot

        snapshot = snapshot_bot("Me_ad_main", bot)
        commands = snapshot.get("commands", {})
        if not isinstance(commands, dict):
            raise TypeError("COMMAND_SNAPSHOT_INVALID")
        collisions = int(snapshot.get("collision_count") or 0)
        missing = sorted(REQUIRED_RUNTIME_COMMANDS - set(commands))
        detail = (
            f"handlers={snapshot.get('total_message_handlers', '?')} · "
            f"commands={snapshot.get('unique_commands', '?')} · "
            f"collisions={collisions}"
        )
        if collisions or missing:
            parts = [f"🔴 {detail}"]
            if missing:
                parts.append("missing=" + ",".join(missing[:7]))
            return " · ".join(parts)
        return f"🟢 {detail} · required commands PASS"
    except Exception as exc:
        return f"⚪️ runtime command evidence unavailable ({type(exc).__name__})"


def _federation_status_label(infrastructure):
    """Render registry status with explicit snapshot freshness; never call it a live heartbeat."""
    if not isinstance(infrastructure, dict):
        return "⚪️ inventory unavailable"

    verified_date = str(infrastructure.get("verified_date_utc") or "unknown")
    raw_age = infrastructure.get("registry_age_days")
    try:
        age_days = int(raw_age) if raw_age is not None and not isinstance(raw_age, bool) else None
    except (TypeError, ValueError, OverflowError):
        age_days = None

    non_green = infrastructure.get("non_green", [])
    non_green = non_green if isinstance(non_green, list) else []
    stale = (
        bool(infrastructure.get("registry_stale", True))
        or age_days is None
        or age_days < 0
        or age_days > FEDERATION_REGISTRY_STALE_DAYS
    )

    historical = []
    for item in non_green[:4]:
        if not isinstance(item, dict):
            continue
        project = str(item.get("project") or "?").replace("\n", " ")[:50]
        service = str(item.get("service") or "?").replace("\n", " ")[:50]
        status = str(item.get("status") or "unknown").replace("\n", " ")[:20]
        historical.append(f"{project}/{service}={status}")

    if stale:
        age_text = f"{age_days}d old" if age_days is not None else "age unknown"
        detail = (
            f"⚪️ INVENTORY STALE · verified {verified_date} · {age_text} · "
            f"historical non-green snapshot entries={len(non_green)} (not live status)"
        )
        if historical:
            detail += " · " + "; ".join(historical)
        return detail

    if non_green:
        detail = (
            f"⚠️ snapshot has {len(non_green)} non-green application entries · "
            f"verified {verified_date} · not a live heartbeat"
        )
        if historical:
            detail += " · " + "; ".join(historical)
        return detail

    return (
        f"🟢 snapshot has no non-green application entries · verified {verified_date} "
        "(snapshot, not a live heartbeat)"
    )


def register_doctor_handlers(bot):
    @bot.message_handler(commands=["doctor"])
    def doctor(m):
        from core.authority import has_permission

        uid = str(m.from_user.id)
        if not has_permission(uid, "exec.audit"):
            bot.reply_to(m, "⛔️ הרשאת אבחון מערכת מלאה נדרשת.")
            return
        report = generate_health_report(bot, uid)
        bot.reply_to(m, report)


def generate_health_report(bot, uid=None):
    checks = {}

    try:
        me = bot.get_me()
        checks["Bot"] = f"🟢 @{me.username}"
    except Exception:
        checks["Bot"] = "🔴 FAILED"

    railway_env = os.getenv("RAILWAY_ENVIRONMENT", "local")
    checks["Railway"] = (
        f"🟢 {railway_env}"
        if railway_env == "production"
        else f"🟡 {railway_env}"
    )
    checks["Deployment source"] = _deployment_source_label()

    # Use the canonical state manager so DB validation and its shared lock apply.
    try:
        import state_manager

        db = state_manager.load_db()
        users = db.get("users")
        ledger = db.get("ledger")
        missing = [key for key in ("users", "transactions", "ledger") if key not in db]
        if missing or not isinstance(users, dict) or not isinstance(ledger, (list, dict)):
            checks["DB"] = "🔴 canonical state is incomplete"
        else:
            checks["DB"] = (
                f"🟢 canonical state readable · users={len(users)} · "
                f"ledger_rows={len(ledger)}"
            )
            checks["DB lock"] = "🟢 state_manager.load_db acquired canonical lock"
    except Exception as exc:
        checks["DB"] = f"🔴 canonical state read failed ({type(exc).__name__})"
        checks["DB lock"] = "⚪️ lock was not verified"

    # Railway mounts the durable state volume at /app/state; do not report the
    # ephemeral /app container filesystem as if it were the persistent volume.
    try:
        import shutil

        state_volume = Path("/app/state")
        if not state_volume.is_dir():
            checks["State volume"] = "🔴 expected /app/state mount is missing"
        else:
            _total, _used, free = shutil.disk_usage(str(state_volume))
            checks["State volume"] = f"🟢 /app/state mounted · {free // (1024 * 1024)} MB free"
    except Exception:
        checks["State volume"] = "⚪️ persistent volume capacity not verified"

    # Configuration only: this deliberately does not spend provider quota.
    try:
        from system_health import get_health

        components = get_health().get("components", {})
        providers = components.get("llm_providers", {})
        configured = [name for name, ok in providers.items() if ok]
        if configured:
            checks["LLM config"] = (
                "🟢 configured (provider response not tested): " + ", ".join(configured)
            )
        else:
            checks["LLM config"] = "🔴 no provider configured"
    except Exception as exc:
        checks["LLM config"] = f"🔴 configuration check failed ({type(exc).__name__})"

    checks["Mini App assets"] = (
        "🟢 mini_app.html present (public HTTP route not probed)"
        if Path("mini_app.html").is_file()
        else "🔴 mini_app.html missing"
    )
    dashboard = Path("web/dashboard_v2/index.html")
    checks["Control Plane dashboard assets"] = (
        "🟢 dashboard assets present (not the Telegram user Mini App)"
        if dashboard.is_file()
        else "⚪️ optional dashboard assets not present"
    )

    checks["Handlers / commands"] = _runtime_commands_label(bot)

    try:
        import state_manager

        agent_data = state_manager.get_agents()
        agent_values = (
            list(agent_data.values())
            if isinstance(agent_data, dict)
            else list(agent_data)
            if isinstance(agent_data, list)
            else []
        )
        agents = [
            agent for agent in agent_values
            if isinstance(agent, dict) and agent.get("state") != "archived"
        ]
        checks["Agents"] = f"🟢 {len(agents)} non-archived agents"
    except Exception as exc:
        checks["Agents"] = f"🔴 agent registry read failed ({type(exc).__name__})"

    try:
        from core.control_center import get_infrastructure_snapshot

        infrastructure = get_infrastructure_snapshot()
        checks["Federation inventory"] = _federation_status_label(infrastructure)
    except Exception as exc:
        checks["Federation inventory"] = f"⚪️ inventory check unavailable ({type(exc).__name__})"

    checks["Health"] = _overall_health_label(checks)
    lines = ["🩺 SLH HEALTH REPORT", ""] + [
        f"{key}: {value}" for key, value in checks.items()
    ]
    lines += [
        "",
        "המלצה:",
    ]
    if "🔴" in checks["Health"]:
        lines.append("❌ נמצאו כשלים בבדיקות; אין להציג את המערכת כתקינה.")
    elif "🟡" in checks["Health"]:
        lines.append("🟡 חלק מהבדיקות דורשות אימות. מצב ירוק מלא לא הוכח.")
    else:
        lines.append("✅ כל בדיקות הבריאות שנכללו בדוח עברו.")
    lines.append(
        "ℹ️ Health אינו אישור Go-Live פיננסי. לבדיקת מוכנות מסחר השתמש ב-/go_live_report; "
        "אין לפתוח שערי BNB/TON או Exchange לפי דוח בריאות בלבד."
    )

    return "\n".join(lines)
