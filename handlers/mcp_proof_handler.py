"""Owner-only Telegram proofs of the live MCP and autonomy paths."""

import os
import requests

from core.exec_policy import is_owner


def read_mcp_proof():
    """Read-only live Telegram -> MCP -> Control Plane proof for owner tools.

    Never returns bridge tokens or arbitrary upstream response bodies. A PASS
    requires the remote proof endpoint itself to report status=PASS.
    """
    base = os.getenv("SLH_MCP_URL", "").strip().rstrip("/")
    token = os.getenv("SLH_MCP_BRIDGE_TOKEN", "").strip()
    if not base or not token:
        return {
            "ok": False,
            "status": "UNAVAILABLE",
            "detail": "MCP proof unavailable: bridge client not configured.",
        }

    try:
        response = requests.get(
            base + "/internal/telegram/mcp-proof",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        return {
            "ok": False,
            "status": "ERROR",
            "detail": "MCP proof failed: " + type(exc).__name__,
        }

    if response.status_code >= 400:
        try:
            error_data = response.json()
        except ValueError:
            error_data = {}
        diagnostic = error_data.get("diagnostic") if isinstance(error_data, dict) else None
        if isinstance(diagnostic, dict):
            role = str(diagnostic.get("role") or "UNKNOWN")[:40]
            has_permission = diagnostic.get("has_agents_view_self")
            permission_count = diagnostic.get("permission_count")
            detail = (
                f"MCP auth diagnostic · HTTP {response.status_code} · role={role} · "
                f"agents.view_self={has_permission} · permission_count={permission_count}"
            )
            return {
                "ok": False,
                "status": "BLOCKED",
                "detail": detail,
                "diagnostic": {
                    "role": role,
                    "has_agents_view_self": has_permission,
                    "permission_count": permission_count,
                },
            }
        return {
            "ok": False,
            "status": "BLOCKED",
            "detail": f"MCP proof failed: HTTP {response.status_code}",
        }

    try:
        data = response.json()
    except ValueError:
        return {
            "ok": False,
            "status": "ERROR",
            "detail": "MCP proof failed: invalid response",
        }

    if not isinstance(data, dict) or data.get("status") != "PASS":
        return {
            "ok": False,
            "status": "BLOCKED",
            "detail": "MCP proof failed: remote proof did not return PASS",
        }

    runtime = data.get("runtime")
    runtime = runtime if isinstance(runtime, dict) else {}
    detail = (
        "Telegram → MCP → Control Plane PASS · "
        f"runtime_state={runtime.get('state')} · "
        f"running={runtime.get('running')} · "
        f"boot_ok={runtime.get('boot_ok')} · "
        f"agent_count={runtime.get('agent_count')}"
    )
    return {
        "ok": True,
        "status": "PASS",
        "detail": detail,
        "runtime": {
            "state": runtime.get("state"),
            "running": runtime.get("running"),
            "boot_ok": runtime.get("boot_ok"),
            "agent_count": runtime.get("agent_count"),
        },
    }


def register(bot, context=None):
    @bot.message_handler(commands=["autonomy_test"])
    def autonomy_test_cmd(m):
        if not is_owner(m.from_user.id):
            bot.reply_to(m, "⛔️ Owner only.")
            return
        try:
            from core.autonomy_control_plane import plan

            result = plan()
            observation = result.get("observation") or {}
            alpha = observation.get("alpha") or {}
            runtime = observation.get("runtime") or {}
            decision = result.get("decision") or {}
            settlement = result.get("financial_settlement") or {}
            bot.reply_to(
                m,
                "AUTONOMY RUNTIME PROOF\n"
                f"alpha={alpha.get('status')}\n"
                f"system={alpha.get('system_status')}\n"
                f"runtime={runtime.get('state')}\n"
                f"running={runtime.get('running')}\n"
                f"agents={runtime.get('agent_count')}\n"
                f"decision={decision.get('class')}\n"
                f"action={decision.get('action')}\n"
                f"financial={settlement.get('class')}",
            )
        except Exception as exc:
            bot.reply_to(m, "AUTONOMY RUNTIME PROOF FAILED: " + type(exc).__name__)

    @bot.message_handler(commands=["mcp_test", "mcp"])
    def mcp_test_cmd(m):
        if not is_owner(m.from_user.id):
            bot.reply_to(m, "⛔️ Owner only.")
            return

        result = read_mcp_proof()
        if not result.get("ok"):
            diagnostic = result.get("diagnostic")
            if isinstance(diagnostic, dict):
                bot.reply_to(
                    m,
                    "❌ MCP auth diagnostic\n"
                    f"role={diagnostic.get('role')}\n"
                    f"agents.view_self={diagnostic.get('has_agents_view_self')}\n"
                    f"permission_count={diagnostic.get('permission_count')}",
                )
            else:
                bot.reply_to(m, "❌ " + str(result.get("detail") or "MCP proof failed safely."))
            return

        runtime = result.get("runtime") or {}
        bot.reply_to(
            m,
            "✅ MCP TELEGRAM PROOF PASS\n"
            "Telegram → MCP → Control Plane\n"
            f"runtime_state={runtime.get('state')}\n"
            f"running={runtime.get('running')}\n"
            f"boot_ok={runtime.get('boot_ok')}\n"
            f"agent_count={runtime.get('agent_count')}",
        )
