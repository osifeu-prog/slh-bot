import os
import requests

from core.authority import is_owner


REGISTRY_FILE = "control_plane_registry.json"


def _load_registry():
    try:
        import json
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _managed_targets():
    registry = _load_registry()
    result = {}

    canonical = registry.get("canonical") or {}
    if canonical.get("railway_service_id") and canonical.get("railway_environment_id"):
        result["slh_main"] = {
            "railway_service_id": canonical["railway_service_id"],
            "railway_environment_id": canonical["railway_environment_id"],
            "railway_project": canonical.get("railway_project", "unknown"),
            "service": canonical.get("railway_service", "unknown"),
        }

    for project in registry.get("railway_projects", []):
        for service in project.get("services", []):
            sid = service.get("id")
            env_id = project.get("environment_id")
            if not sid or not env_id or service.get("class") == "infrastructure":
                continue
            result[project["name"] + ":" + service.get("name", sid)] = {
                "railway_service_id": sid,
                "railway_environment_id": env_id,
                "railway_project": project["name"],
                "service": service.get("name", sid),
            }
    return result


def register(bot):
    @bot.message_handler(commands=["projects"])
    def projects_cmd(m):
        if not is_owner(m):
            return
        targets = _managed_targets()
        if not targets:
            bot.reply_to(m, "no managed Railway targets")
            return
        lines = ["MANAGED RAILWAY TARGETS:", ""]
        for name in sorted(targets):
            t = targets[name]
            lines.append(f"• {name} -> {t['railway_project']}/{t['service']}")
        bot.reply_to(m, "\n".join(lines))

    @bot.message_handler(commands=["deploy"])
    def deploy_cmd(m):
        if not is_owner(m):
            return

        token = os.getenv("RAILWAY_API_TOKEN")
        if not token:
            bot.reply_to(m, "RAILWAY_API_TOKEN not set")
            return

        parts = m.text.split(maxsplit=1)
        target_name = parts[1].strip() if len(parts) > 1 else "slh_main"

        target = _managed_targets().get(target_name)
        if not target:
            bot.reply_to(
                m,
                "project/service not found: "
                + target_name
                + "\nUse /projects",
            )
            return

        q = (
            "mutation("
            + chr(36)
            + "s:String!,"
            + chr(36)
            + "e:String!"
            + "){serviceInstanceDeploy(serviceId:"
            + chr(36)
            + "s,environmentId:"
            + chr(36)
            + "e)}"
        )
        headers = {
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        }
        r = requests.post(
            "https://backboard.railway.app/graphql/v2",
            json={
                "query": q,
                "variables": {
                    "s": target["railway_service_id"],
                    "e": target["railway_environment_id"],
                },
            },
            headers=headers,
            timeout=20,
        )
        if r.status_code == 200:
            bot.reply_to(
                m,
                "deploy sent: "
                + target_name
                + " -> "
                + target["railway_project"]
                + "/"
                + target["service"],
            )
        else:
            bot.reply_to(
                m,
                "failed: "
                + str(r.status_code)
                + " "
                + r.text[:200],
            )
