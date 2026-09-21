"""Unified SLH System map exposed through the central Control Plane.

The inventory in control_plane_registry.json is the canonical topology snapshot
for the connected Railway/GitHub estate. Runtime state remains canonical in the
central SLH deployment.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from state_manager import load_db

REGISTRY = Path("control_plane_registry.json")


def _load_registry():
    try:
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    except Exception:
        return {
            "schema_version": "missing",
            "canonical": {},
            "railway_projects": [],
            "github_unmapped": [],
        }


def _load_bot_registry():
    """Read the canonical Bot Factory registry without mutating runtime state."""
    try:
        db = load_db() or {}
        bots = db.get("bots", {})
        if isinstance(bots, dict):
            return list(bots.values())
        return bots if isinstance(bots, list) else []
    except Exception:
        return []


def get_unified_map():
    registry = _load_registry()
    projects = registry.get("railway_projects", [])
    bots = _load_bot_registry()

    systems = []
    for project in projects:
        systems.append({
            "id": "railway:" + project.get("id", project.get("name", "unknown")),
            "name": project.get("name", "unknown"),
            "role": project.get("role", "external"),
            "railway_project": project.get("name"),
            "railway_project_id": project.get("id"),
            "environment_id": project.get("environment_id"),
            "services": project.get("services", []),
        })

    return {
        "schema_version": registry.get("schema_version", "1.0"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "control_plane": registry.get("canonical", {}),
        "canonical_repo": registry.get("canonical", {}).get("repo", "unknown"),
        "canonical_state": "state/db.json",
        "systems": systems,
        "bot_factory": bots,
        "github_unmapped": registry.get("github_unmapped", []),
        "principles": [
            "Central SLH deployment is the operational Control Plane.",
            "Secondary bots, APIs and sites are managed resources/clients, not competing state authorities.",
            "No client may mint, settle, or mutate canonical balances outside the central economy authority.",
            "External token conversion requires an explicit verified settlement path.",
            "Infrastructure is visible in the Control Plane but is not a bot identity.",
        ],
    }


def _render(m):
    projects = m["systems"]
    service_count = sum(len(p.get("services", [])) for p in projects)
    unmapped = m["github_unmapped"]
    bots = m.get("bot_factory", [])
    canonical = m["control_plane"]

    lines = [
        "🗺 SLH UNIFIED CONTROL PLANE",
        "",
        f"Canonical repo: {canonical.get('repo', 'unknown')}",
        f"Canonical Railway: {canonical.get('railway_project', 'unknown')} / {canonical.get('railway_service', 'unknown')}",
        f"Managed Railway projects: {len(projects)}",
        f"Managed Railway services: {service_count}",
        f"GitHub repos without Railway mapping: {len(unmapped)}",
        f"Bot Factory registry: {len(bots)}",
        "",
    ]

    for p in projects:
        services = p.get("services", [])
        non_green = [s for s in services if s.get("status") not in (None, "SUCCESS")]
        role = p.get("role", "external")
        if role == "canonical_control_plane":
            marker = "🟢"
            label = "CANONICAL"
        elif role == "secondary_non_polling_runtime":
            marker = "⚪"
            label = "NON-POLLING"
        elif any(s.get("status") == "CRASHED" for s in services):
            marker = "🔴"
            label = "FAILED"
        elif non_green:
            marker = "🟡"
            label = "DEGRADED"
        elif role.startswith("legacy_"):
            marker = "🟡"
            label = "LEGACY"
        else:
            marker = "🟢"
            label = "EXTERNAL"
        lines.append(
            f"{marker} {p['name']} — {label} / {role} — {len(services)} services"
        )
        for s in services:
            if s.get("class") != "infrastructure" and (s.get("repo") or s.get("status") not in (None, "SUCCESS")):
                if s.get("status") == "SUCCESS":
                    sm = "🟢"
                elif s.get("status") == "CRASHED":
                    sm = "🔴"
                elif s.get("status") in (None, "UNKNOWN", "unknown"):
                    sm = "⚪"
                else:
                    sm = "🟡"
                extra = ""
                if s.get("runtime_policy", {}).get("RUN_BOT") == "0":
                    extra = " / non-polling"
                lines.append(
                    f"   └ {sm} {s.get('name', '?')} → {s.get('repo', 'no repo')} [{s.get('status', 'unknown')}]"
                    f"{extra}"
                )

    lines += ["", "🤖 BOT FACTORY"]
    if not bots:
        lines.append("• No bots registered")
    else:
        for b in bots:
            status = b.get("status", "draft")
            marker = "🟢" if status in ("ready", "deployed", "running") else ("🟡" if status in ("draft", "deploying") else "🔴")
            binding = ""
            if b.get("railway_service_id"):
                binding = " / Railway-bound"
            lines.append(
                f"{marker} {b.get('name', '?')} — {status} / {b.get('template', 'generic')}"
                f"{binding} [{b.get('id', '?')}]"
            )

    lines += ["", "GitHub-only/unmapped in this Railway workspace:"]
    for r in unmapped:
        lines.append("• " + r.get("repo", "unknown"))

    return "\n".join(lines)


def register(bot):
    @bot.message_handler(commands=["unified_map", "control", "systems"])
    def unified_map(msg):
        bot.reply_to(msg, _render(get_unified_map()))
