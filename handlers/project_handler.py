from core.project_context import get_project_context\nfrom core.authority import has_permission


def _render(ctx):
    identity = ctx.get("identity", {})
    health = ctx.get("health", {})
    agents = ctx.get("agents", {})
    runtime = ctx.get("runtime", {})
    services = ctx.get("services", [])

    lines = [
        "🧠 SLH PROJECT",
        "",
        f"Repo: {identity.get('canonical_repo', 'unknown')}",
        f"Railway: {identity.get('railway_project', 'unknown')} / {identity.get('railway_service', 'unknown')}",
        f"Runtime: {'🟢' if runtime.get('running') else '🔴'}",
        f"Agents: {agents.get('count', 0)} ({agents.get('active', 0)} active)",
        f"Application services: {len(services)}",
        f"Non-green: {len(health.get('non_green_application_services', []))}",
        "",
        "Graph: AI session → agents → services → deployments → health → journal",
    ]
    return "\n".join(lines)


def register(bot, context=None):
    @bot.message_handler(commands=["project"])
    def project_cmd(m):
        uid = getattr(getattr(m, "from_user", None), "id", None)
        try:
            bot.reply_to(m, _render(get_project_context(uid)))
        except Exception as exc:
            bot.reply_to(m, f"Project context failed: {type(exc).__name__}")
