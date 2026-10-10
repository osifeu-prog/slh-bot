"""Owner/admin/developer read-only system checks for SLH OS."""

from __future__ import annotations

from core.authority import get_role
from core.release_readiness import build_release_report
from core.system_checks import (
    check_bnb,
    check_commands,
    check_exchange,
    check_exchange_for_execution,
    check_db,
    check_money,
    check_ton,
    check_ux,
)


_ALLOWED_ROLES = {"OWNER", "ADMIN", "DEVELOPER"}


def _allowed(message) -> bool:
    role = get_role(str(message.from_user.id))
    if role not in _ALLOWED_ROLES:
        message._slh_check_denied_role = role
        return False
    return True


def _send_denied(bot, message) -> None:
    role = getattr(message, "_slh_check_denied_role", "UNKNOWN")
    bot.reply_to(message, f"⛔ System checks require OWNER/ADMIN/DEVELOPER. Role: {role}")


def _icon(ok: bool) -> str:
    return "✅" if ok else "⛔️"


def _fmt_check(name: str, result: dict) -> str:
    return f"{_icon(bool(result.get('ok')))} {name}: {result.get('detail', 'no detail')}"


def _check_output(uid: str) -> str:
    db = check_db()
    commands = check_commands()
    ux = check_ux()
    money = check_money(uid)
    bnb = check_bnb()
    ton = check_ton(uid)
    exchange = check_exchange()

    lines = [
        "🧪 SLH SYSTEM CHECK — READ ONLY",
        "",
        _fmt_check("DB", db),
        _fmt_check("Commands", commands),
        _fmt_check("Mini App UX", ux),
        _fmt_check("Money / invariants", money),
        _fmt_check("BNB", bnb),
        _fmt_check("TON", ton),
        _fmt_check("Internal Exchange", exchange),
        "",
        "🔒 אין שינוי DB / balances / wallets / settlement / gates.",
        "🧭 לדוח Go-Live מאוחד: /go_live_report\n"
        "ℹ️ לפירוט: /check_ux · /check_money · /check_bnb · /check_ton · /check_exchange",
    ]
    return "\n".join(lines)[:3900]



def _release_icon(status: str) -> str:
    return {
        "GREEN": "✅",
        "DEGRADED": "🟡",
        "BLOCKED": "⛔️",
    }.get(str(status or "").upper(), "⚪️")


def _go_live_report_output(uid: str) -> str:
    """One-message, read-only launch report with explicit fail-closed gates."""
    report = build_release_report()
    db = check_db()
    commands = check_commands()
    ux = check_ux()
    money = check_money(uid)
    bnb = check_bnb()
    ton = check_ton(uid)

    try:
        import state_manager
        execution = check_exchange_for_execution(state_manager.load_db())
    except Exception as exc:
        execution = {
            "execution_ready": False,
            "public_gate": "UNKNOWN",
            "verdict": "BLOCKED",
            "detail": f"fresh preflight failed: {type(exc).__name__}",
        }

    overall = str(report.get("overall_status") or "UNKNOWN").upper()
    lines = [
        "🧭 SLH OS GO-LIVE REPORT — READ ONLY",
        "",
        f"Overall release readiness: {_release_icon(overall)} {overall}",
        "",
        "Release gates:",
    ]
    for name, row in (report.get("checks") or {}).items():
        status = str(row.get("status") or "BLOCKED").upper()
        detail = str(row.get("detail") or "no detail").replace("\n", " ")
        lines.append(
            f"{_release_icon(status)} {name}: {status} · {detail[:180]}"
        )

    lines += [
        "",
        "System integrity:",
        _fmt_check("DB", db),
        _fmt_check("Commands", commands),
        _fmt_check("Mini App UX", ux),
        _fmt_check("Money / invariants", money),
    ]

    execution_ready = execution.get("execution_ready") is True
    execution_status = "PASS" if execution_ready else "BLOCKED"
    lines += [
        "",
        f"{_release_icon('GREEN' if execution_ready else 'BLOCKED')} "
        f"Current Exchange execution preflight: {execution_status}",
        f"Gate: {execution.get('public_gate', 'UNKNOWN')} · "
        f"Verdict: {execution.get('verdict', 'UNKNOWN')} · "
        f"{str(execution.get('detail') or 'no detail')[:160]}",
        "This preflight is only a snapshot. Every Buy/Sell order rechecks "
        "canonically inside the atomic mutation and returns an execution receipt.",
    ]

    if bnb.get("ok"):
        bnb_icon = "✅"
        bnb_state = "OPEN · empirical settlement PASS"
    elif not bnb.get("public_open") and bnb.get("ready") and bnb.get("launch_ready"):
        bnb_icon = "🟡"
        bnb_state = "SAFE CLOSED · configuration PASS · empirical settlement PASS · pending operator review"
    elif not bnb.get("public_open") and bnb.get("ready") and not bnb.get("launch_ready"):
        bnb_icon = "🟡"
        bnb_state = (
            "SAFE CLOSED · configuration PASS · empirical settlement "
            + str(bnb.get("empirical_status") or "PENDING_EMPIRICAL")
        )
    else:
        bnb_icon = "⛔️"
        bnb_state = (
            "CLOSED · readiness requires attention · empirical settlement "
            + str(bnb.get("empirical_status") or "UNKNOWN")
        )
    lines += [
        "",
        f"{bnb_icon} BNB: {bnb_state}",
        f"TON: {'✅ OPEN' if ton.get('ok') else ('🟡 SAFE CLOSED' if ton.get('ready') and not ton.get('public_open') else '⛔️ NEEDS REVIEW')} · "
        f"gate={'OPEN' if ton.get('public_open') else 'CLOSED'} · "
        f"readiness={'PASS' if ton.get('ready') else 'BLOCKED'} · "
        f"rate={ton.get('rate', 'unknown')} Credits/TON · "
        f"replay={ton.get('replay_evidence', 'unknown')}",
        "",
        "🔒 No orders, broadcasts, transfers, claims or gate changes were made.",
        (
            "✅ BNB public gate OPEN; live empirical settlement evidence is currently revalidated."
            if bnb.get("public_open") and bnb.get("launch_ready")
            else "🟡 BNB remains safely CLOSED pending explicit operator review; live empirical settlement evidence is PASS and revalidated."
            if bnb.get("launch_ready")
            else "⛔️ BNB stays closed until live empirical settlement evidence is revalidated and all blockers are cleared."
        ),
        "ℹ️ Participation / public investment stays DESIGN ONLY unless separate approvals pass.",
    ]

    if bnb.get("next_action"):
        lines.append("BNB evidence next step: " + str(bnb["next_action"])[:180])
    for blocker in (bnb.get("blockers") or [])[:3]:
        lines.append("BNB blocker: " + str(blocker)[:160])

    return "\n".join(lines)[:3900]



def register(bot, context=None):
    @bot.message_handler(commands=["go_live_report", "release_report"])
    def go_live_report_cmd(message):
        if not _allowed(message):
            _send_denied(bot, message)
            return
        try:
            bot.reply_to(
                message,
                _go_live_report_output(str(message.from_user.id)),
                parse_mode=None,
            )
        except Exception as exc:
            bot.reply_to(
                message,
                f"❌ Go-Live report failed safely: {type(exc).__name__}",
                parse_mode=None,
            )

    @bot.message_handler(commands=["check", "checks"])
    def check_cmd(message):
        if not _allowed(message):
            _send_denied(bot, message)
            return
        try:
            bot.reply_to(message, _check_output(str(message.from_user.id)), parse_mode=None)
        except Exception as exc:
            bot.reply_to(message, f"❌ System check failed safely: {type(exc).__name__}")

    @bot.message_handler(commands=["check_ux", "uxcheck"])
    def check_ux_cmd(message):
        if not _allowed(message):
            _send_denied(bot, message)
            return
        try:
            result = check_ux()
            lines = [
                "🎨 SLH UX CHECK — READ ONLY",
                "",
                f"{_icon(result['ok'])} {result['detail']}",
            ]
            for item in result.get("checks", []):
                lines.append(f"{_icon(item['ok'])} {item['name']}")
            lines += [
                "",
                "Source: deployed repository files",
                "🔒 No mutation.",
            ]
            bot.reply_to(message, "\n".join(lines)[:3900], parse_mode=None)
        except Exception as exc:
            bot.reply_to(message, f"❌ UX check failed safely: {type(exc).__name__}")

    @bot.message_handler(commands=["check_money", "moneycheck"])
    def check_money_cmd(message):
        if not _allowed(message):
            _send_denied(bot, message)
            return
        try:
            result = check_money(str(message.from_user.id))
            lines = [
                "💰 SLH MONEY CHECK — READ ONLY",
                "",
                f"{_icon(result['ok'])} {result['detail']}",
            ]
            for item in result.get("checks", []):
                lines.append(
                    f"{_icon(item['ok'])} {item['name']}: {item.get('detail', '')}"
                )
            lines += ["", "🔒 No balance mutation."]
            bot.reply_to(message, "\n".join(lines)[:3900], parse_mode=None)
        except Exception as exc:
            bot.reply_to(message, f"❌ Money check failed safely: {type(exc).__name__}")

    @bot.message_handler(commands=["check_exchange", "exchange_check"])
    def check_exchange_cmd(message):
        if not _allowed(message):
            _send_denied(bot, message)
            return
        try:
            result = check_exchange()
            lines = [
                "📈 SLH EXCHANGE CHECK — READ ONLY",
                "",
                f"Open orders: {result['open_orders']}",
                f"Open test/seed orders: {result['test_seed_open']}",
                f"Recent trades: {result['recent_trades']}",
                f"Test/seed trades: {result['test_seed_trades']}",
                f"Order book integrity: {'PASS' if result['order_book_integrity'] else 'FAIL'}",
                f"Trade integrity: {'PASS' if result['trade_integrity'] else 'FAIL'}",
                f"Money invariants: {'PASS' if result['money_invariants'] else 'FAIL'}",
                f"Public trading gate: {result['public_gate']}",
                f"Public trading readiness: {'PASS' if result['public_ready'] else 'FAIL'}",
                f"Verdict: {result['verdict']}",
                f"Detail: {result['detail']}",
                "",
                "🔒 Read-only: no orders, trades, balances, wallets or gates are changed.",
            ]
            bot.reply_to(message, "\n".join(lines)[:3900], parse_mode=None)
        except Exception as exc:
            bot.reply_to(message, f"❌ Exchange check failed safely: {type(exc).__name__}")

    @bot.message_handler(commands=["check_bnb", "bnb_check"])
    def check_bnb_cmd(message):
        if not _allowed(message):
            _send_denied(bot, message)
            return
        try:
            result = check_bnb()
            lines = [
                "🔶 SLH BNB CHECK — READ ONLY",
                "",
                f"{_icon(result['ok'])} {result['detail']}",
                f"Public gate: {'OPEN' if result['public_open'] else 'CLOSED'}",
                f"Readiness: {'PASS' if result['ready'] else 'BLOCKED'}",
                f"Empirical smoke: {result['empirical_status']}",
                f"Evidence status: {result.get('evidence_status', 'UNKNOWN')}",
                f"Live RPC: {result.get('live_rpc_status', 'UNKNOWN')}",
                f"Confirmations required: {result['confirmations_required']}",
            ]
            for reason in result.get("gate_reasons", [])[:5]:
                lines.append(f"Gate reason: {reason}")
            for reason in result.get("blockers", [])[:5]:
                lines.append(f"Blocker: {reason}")
            for warning in result.get("warnings", [])[:3]:
                lines.append(f"Warning: {warning}")
            if result.get("next_action"):
                lines.append(f"Next action: {result['next_action']}")
            lines += [
                "",
                "⛔️ אין שליחה, broadcast, claim או gate change.",
            ]
            bot.reply_to(message, "\n".join(lines)[:3900], parse_mode=None)
        except Exception as exc:
            bot.reply_to(message, f"❌ BNB check failed safely: {type(exc).__name__}")

    @bot.message_handler(commands=["check_ton", "ton_check_status"])
    def check_ton_cmd(message):
        if not _allowed(message):
            _send_denied(bot, message)
            return
        try:
            result = check_ton(str(message.from_user.id))
            lines = [
                "💎 SLH TON CHECK — READ ONLY",
                "",
                f"{_icon(result['ok'])} {result['detail']}",
                f"Public gate: {'OPEN' if result['public_open'] else 'CLOSED'}",
                f"Readiness: {'PASS' if result['ready'] else 'BLOCKED'}",
                f"Rate: {result['rate']} Credits / TON",
                f"Replay evidence: {result['replay_evidence']}",
                "",
                "🔒 No transaction lookup that can credit funds; no mutation.",
            ]
            bot.reply_to(message, "\n".join(lines)[:3900], parse_mode=None)
        except Exception as exc:
            bot.reply_to(message, f"❌ TON check failed safely: {type(exc).__name__}")

    print("✅ system_checks loaded")
