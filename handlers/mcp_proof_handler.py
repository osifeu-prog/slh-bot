"""Owner-only Telegram proofs of the live MCP and autonomy paths."""

import os
import requests

from core.exec_policy import is_owner


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

    @bot.message_handler(commands=["mcp_test"])
    def mcp_test_cmd(m):
        if not is_owner(m.from_user.id):
            bot.reply_to(m, "⛔️ Owner only.")
            return

        base = os.getenv("SLH_MCP_URL", "").strip().rstrip("/")
        token = os.getenv("SLH_MCP_BRIDGE_TOKEN", "").strip()
        if not base or not token:
            bot.reply_to(m, "MCP proof unavailable: bridge client not configured.")
            return

        try:
            response = requests.get(
                base + "/internal/telegram/mcp-proof",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                timeout=15,
            )
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                except ValueError:
                    error_data = {}
                diagnostic = error_data.get("diagnostic") or {}
                if diagnostic:
                    bot.reply_to(
                        m,
                        "❌ MCP auth diagnostic\n"
                        f"role={diagnostic.get('role')}\n"
                        f"agents.view_self={diagnostic.get('has_agents_view_self')}\n"
                        f"permission_count={diagnostic.get('permission_count')}",
                    )
                else:
                    response.raise_for_status()
                return
            data = response.json()
        except requests.RequestException as exc:
            bot.reply_to(m, "❌ MCP proof failed: " + type(exc).__name__)
            return
        except ValueError:
            bot.reply_to(m, "❌ MCP proof failed: invalid response")
            return

        if data.get("status") != "PASS":
            bot.reply_to(m, "❌ MCP proof failed.")
            return

        runtime = data.get("runtime") or {}
        bot.reply_to(
            m,
            "✅ MCP TELEGRAM PROOF PASS\n"
            "Telegram → MCP → Control Plane\n"
            f"runtime_state={runtime.get('state')}\n"
            f"running={runtime.get('running')}\n"
            f"boot_ok={runtime.get('boot_ok')}\n"
            f"agent_count={runtime.get('agent_count')}",
        )
