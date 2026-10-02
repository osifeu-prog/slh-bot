import os
import re
import requests

from core.authority import is_owner


REGISTRY_FILE = "control_plane_registry.json"
RAILWAY_API_URL = "https://backboard.railway.app/graphql/v2"


def _load_registry():
    try:
        import json
        with open(REGISTRY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _managed_targets(include_infrastructure=False):
    registry = _load_registry()
    result = {}

    canonical = registry.get("canonical") or {}
    if canonical.get("railway_service_id") and canonical.get("railway_environment_id"):
        result["slh_main"] = {
            "railway_service_id": canonical["railway_service_id"],
            "railway_environment_id": canonical["railway_environment_id"],
            "railway_project_id": canonical.get("railway_project_id"),
            "railway_project": canonical.get("railway_project", "unknown"),
            "service": canonical.get("railway_service", "unknown"),
            "class": "canonical",
        }

    for project in registry.get("railway_projects", []):
        for service in project.get("services", []):
            sid = service.get("id")
            env_id = project.get("environment_id")
            if not sid or not env_id:
                continue
            if service.get("class") == "infrastructure" and not include_infrastructure:
                continue
            key = project["name"] + ":" + service.get("name", sid)
            result[key] = {
                "railway_service_id": sid,
                "railway_environment_id": env_id,
                "railway_project_id": project.get("id"),
                "railway_project": project["name"],
                "service": service.get("name", sid),
                "class": service.get("class", "unknown"),
            }
    return result


def _release_truth_targets():
    """Return exactly the canonical control-plane web and MCP services."""
    registry = _load_registry()
    canonical = registry.get("canonical") or {}
    project_id = canonical.get("railway_project_id")
    environment_id = canonical.get("railway_environment_id")
    project_name = canonical.get("railway_project")
    if not project_id or not environment_id:
        return {}

    result = {}
    for project in registry.get("railway_projects", []):
        if project.get("id") != project_id:
            continue
        if project.get("environment_id") != environment_id:
            continue
        for service in project.get("services", []):
            name = service.get("name")
            if name not in ("web", "slh-mcp") or not service.get("id"):
                continue
            result[name] = {
                "railway_service_id": service["id"],
                "railway_environment_id": environment_id,
                "railway_project_id": project_id,
                "railway_project": project.get("name", project_name or "unknown"),
                "service": name,
                "class": service.get("class", "unknown"),
            }
    return result


def _resolve_target(name, include_infrastructure=False):
    targets = _managed_targets(include_infrastructure=include_infrastructure)
    if not name:
        return targets.get("slh_main"), "slh_main"

    exact = targets.get(name)
    if exact:
        return exact, name

    normalized = name.lstrip("@").strip().lower()
    matches = [
        (key, target)
        for key, target in targets.items()
        if str(target.get("service", "")).lower() == normalized
        or key.lower() == normalized
    ]
    if len(matches) == 1:
        return matches[0][1], matches[0][0]
    if len(matches) > 1:
        return None, "AMBIGUOUS:" + ", ".join(key for key, _ in matches)
    return None, name


def _graphql(token, query, variables):
    response = requests.post(
        RAILWAY_API_URL,
        json={"query": query, "variables": variables},
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("errors"):
        messages = "; ".join(
            str(error.get("message", "GraphQL error")) for error in data["errors"]
        )
        raise RuntimeError(messages)
    return data.get("data") or {}


def _latest_deployment(token, target):
    query = """
    query Deployments($serviceId: String!, $projectId: String!, $environmentId: String!) {
      deployments(
        first: 1
        input: {
          projectId: $projectId
          serviceId: $serviceId
          environmentId: $environmentId
        }
      ) {
        edges {
          node {
            id
            status
            createdAt
            updatedAt
            meta {
              commitHash
              branch
              commitMessage
            }
          }
        }
      }
    }
    """
    project_id = target.get("railway_project_id")
    if not project_id:
        project = _load_registry().get("railway_projects", [])
        project_id = next(
            (
                p.get("id")
                for p in project
                if p.get("name") == target.get("railway_project")
            ),
            None,
        )
    if not project_id:
        raise RuntimeError("PROJECT_ID_MISSING")
    data = _graphql(
        token,
        query,
        {
            "projectId": project_id,
            "serviceId": target["railway_service_id"],
            "environmentId": target["railway_environment_id"],
        },
    )
    edges = ((data.get("deployments") or {}).get("edges") or [])
    if not edges:
        raise RuntimeError("NO_DEPLOYMENTS")
    return edges[0]["node"]


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
            lines.append(
                f"• {name} -> {t['railway_project']}/{t['service']} [{t.get('class', 'unknown')}]"
            )
        bot.reply_to(m, "\n".join(lines))

    @bot.message_handler(commands=["deploy", "redeploy"])
    def deploy_cmd(m):
        if not is_owner(m):
            return

        token = os.getenv("RAILWAY_API_TOKEN")
        if not token:
            bot.reply_to(m, "RAILWAY_API_TOKEN not set")
            return

        parts = m.text.split(maxsplit=1)
        target_arg = parts[1].strip() if len(parts) > 1 else ""
        target, resolved_name = _resolve_target(target_arg)
        if not target:
            if resolved_name.startswith("AMBIGUOUS:"):
                bot.reply_to(m, "ambiguous target: " + resolved_name.split(":", 1)[1])
            else:
                bot.reply_to(
                    m,
                    "project/service not found: "
                    + (target_arg or "slh_main")
                    + "\nUse /projects",
                )
            return

        command = (m.text or "").split(maxsplit=1)[0].lstrip("/").lower()
        mutation = """
        mutation Redeploy($serviceId: String!, $environmentId: String!) {
          serviceInstanceRedeploy(
            serviceId: $serviceId
            environmentId: $environmentId
          )
        }
        """
        if command == "deploy":
            mutation = """
            mutation Deploy($serviceId: String!, $environmentId: String!) {
              serviceInstanceDeployV2(
                serviceId: $serviceId
                environmentId: $environmentId
              )
            }
            """
        try:
            data = _graphql(
                token,
                mutation,
                {
                    "serviceId": target["railway_service_id"],
                    "environmentId": target["railway_environment_id"],
                },
            )
            result = (
                data.get("serviceInstanceRedeploy")
                if command == "redeploy"
                else data.get("serviceInstanceDeployV2")
            )
            bot.reply_to(
                m,
                f"{command} sent: {resolved_name} -> "
                f"{target['railway_project']}/{target['service']} "
                f"(deployment={result or 'queued'})",
            )
        except Exception as exc:
            bot.reply_to(m, f"{command} failed: {type(exc).__name__}: {str(exc)[:250]}")

    @bot.message_handler(commands=["release_status"])
    def release_status_cmd(m):
        if not is_owner(m):
            return

        token = os.getenv("RAILWAY_API_TOKEN")
        if not token:
            bot.reply_to(m, "RAILWAY_API_TOKEN not set")
            return

        try:
            targets = _release_truth_targets()
            expected = ""
            parts = m.text.split()
            if len(parts) > 1:
                expected = parts[1].strip().lower()

            rows = []
            for name, target in sorted(targets.items()):
                dep = _latest_deployment(token, target)
                commit = str((dep.get("meta") or {}).get("commitHash") or "").lower()
                rows.append((name, dep.get("status"), commit, dep.get("id")))

            if not rows:
                bot.reply_to(m, "RELEASE TRUTH\nBLOCKED: no canonical web/slh-mcp deployments found")
                return

            commits = {row[2] for row in rows if row[2]}
            success = all(row[1] == "SUCCESS" for row in rows)
            same_commit = len(commits) == 1 and len(commits) == len(rows)
            expected_ok = not expected or all(row[2] == expected for row in rows)
            status = "PASS" if success and same_commit and expected_ok else "BLOCKED"

            lines = [
                "RELEASE TRUTH",
                f"STATUS: {status}",
                f"DEPLOYMENTS_SUCCESS: {success}",
                f"SAME_COMMIT: {same_commit}",
                f"EXPECTED_COMMIT: {expected or '(not supplied)'}",
                f"EXPECTED_MATCH: {expected_ok}",
            ]
            for name, dep_status, commit, dep_id in rows:
                lines.append(
                    f"• {name}: {dep_status} commit={commit[:12] or 'unknown'} deployment={dep_id}"
                )
            lines.append(
                "Historical REMOVED deployments are ignored; only the latest deployment per canonical service is evaluated."
            )
            bot.reply_to(m, "\n".join(lines)[:3900])
        except Exception as exc:
            bot.reply_to(
                m,
                f"release_status failed: {type(exc).__name__}: {str(exc)[:300]}",
            )

    @bot.message_handler(commands=["logs"])
    def logs_cmd(m):
        if not is_owner(m):
            return

        token = os.getenv("RAILWAY_API_TOKEN")
        if not token:
            bot.reply_to(m, "RAILWAY_API_TOKEN not set")
            return

        parts = m.text.split()
        target_arg = parts[1] if len(parts) > 1 else ""
        stream = parts[2].lower() if len(parts) > 2 else "deploy"
        if stream not in ("deploy", "build"):
            bot.reply_to(m, "usage: /logs <service-or-project:service> [deploy|build]")
            return

        target, resolved_name = _resolve_target(
            target_arg,
            include_infrastructure=True,
        )
        if not target:
            if resolved_name.startswith("AMBIGUOUS:"):
                bot.reply_to(m, "ambiguous target: " + resolved_name.split(":", 1)[1])
            else:
                bot.reply_to(m, "project/service not found: " + (target_arg or "(missing)"))
            return

        try:
            deployment = _latest_deployment(token, target)
            operation = "deploymentLogs" if stream == "deploy" else "buildLogs"
            query = f"""
            query DeploymentLogs($deploymentId: String!, $limit: Int) {{
              {operation}(deploymentId: $deploymentId, limit: $limit) {{
                timestamp
                message
                severity
              }}
            }}
            """
            data = _graphql(
                token,
                query,
                {"deploymentId": deployment["id"], "limit": 60},
            )
            entries = data.get(operation) or []
            entries = entries[-30:]
            if not entries:
                bot.reply_to(
                    m,
                    f"{stream} logs empty: {resolved_name} "
                    f"deployment {deployment['id']} status={deployment.get('status')}",
                )
                return

            lines = [
                f"RAILWAY {stream.upper()} LOGS",
                f"{resolved_name} · {deployment['id']} · {deployment.get('status')}",
                "",
            ]
            for entry in entries:
                ts = str(entry.get("timestamp", ""))[-12:]
                sev = str(entry.get("severity") or "info").upper()
                message = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", str(entry.get("message", ""))).strip()
                for line in message.splitlines() or [""]:
                    lines.append(f"{ts} {sev} {line[:380]}")
            text = "\n".join(lines)
            bot.reply_to(m, text[:3900])
        except Exception as exc:
            bot.reply_to(m, f"logs failed: {type(exc).__name__}: {str(exc)[:300]}")