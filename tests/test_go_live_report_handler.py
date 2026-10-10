from types import SimpleNamespace

import state_manager
import handlers.system_checks_handler as handler


class _FakeBot:
    def __init__(self):
        self.registered = []
        self.replies = []

    def message_handler(self, commands=None, **kwargs):
        def decorate(fn):
            self.registered.append((commands, fn))
            return fn
        return decorate

    def reply_to(self, message, text, **kwargs):
        self.replies.append((message, text))


def _go_live_handler(bot):
    handler.register(bot)
    return next(
        fn
        for commands, fn in bot.registered
        if "go_live_report" in (commands or [])
    )


def test_single_go_live_report_command_is_registered():
    bot = _FakeBot()
    handler.register(bot)

    commands = {
        command
        for registered, _handler in bot.registered
        for command in (registered or [])
    }
    assert "go_live_report" in commands
    assert "release_report" in commands


def test_go_live_report_explains_safe_closed_gates_and_send_time_check(monkeypatch):
    bot = _FakeBot()
    report_handler = _go_live_handler(bot)

    monkeypatch.setattr(handler, "_allowed", lambda message: True)
    monkeypatch.setattr(
        handler,
        "build_release_report",
        lambda: {
            "overall_status": "DEGRADED",
            "checks": {
                "Internal exchange": {
                    "status": "GREEN",
                    "detail": "canonical exchange checks pass; public gate=OPEN",
                },
                "External settlement gates": {
                    "status": "DEGRADED",
                    "detail": "BNB settlement remains CLOSED: empirical settlement proof pending/invalid",
                },
                "Participation": {
                    "status": "GREEN",
                    "detail": "disabled by default; approvals remain closed",
                },
            },
        },
    )
    monkeypatch.setattr(handler, "check_db", lambda: {"ok": True, "detail": "DB readable"})
    monkeypatch.setattr(handler, "check_commands", lambda: {"ok": True, "detail": "collisions=0"})
    monkeypatch.setattr(handler, "check_ux", lambda: {"ok": True, "detail": "Mini App shell present"})
    monkeypatch.setattr(handler, "check_money", lambda uid: {"ok": True, "detail": "invariants PASS"})
    monkeypatch.setattr(
        handler,
        "check_bnb",
        lambda: {
            "ok": False,
            "public_open": False,
            "ready": True,
            "launch_ready": False,
            "empirical_status": "PENDING_EMPIRICAL",
            "evidence_status": "BLOCKED",
            "blockers": [],
            "next_action": "controlled_empirical_reconciliation_before_opening",
            "gate_reasons": [],
        },
    )
    monkeypatch.setattr(
        handler,
        "check_ton",
        lambda uid: {
            "ok": False,
            "public_open": False,
            "ready": True,
            "rate": "100",
            "replay_evidence": "present",
        },
    )
    monkeypatch.setattr(
        handler,
        "check_exchange_for_execution",
        lambda db: {
            "execution_ready": True,
            "public_gate": "OPEN",
            "verdict": "OPEN",
            "detail": "public state clean",
        },
    )
    monkeypatch.setattr(state_manager, "load_db", lambda: {"users": {}})

    message = SimpleNamespace(from_user=SimpleNamespace(id=8789977826))
    report_handler(message)
    output = bot.replies[-1][1]

    assert "Overall release readiness: 🟡 DEGRADED" in output
    assert "Current Exchange execution preflight: PASS" in output
    assert "BNB: SAFE CLOSED" in output
    assert "empirical settlement PENDING_EMPIRICAL" in output
    assert "TON: 🟡 SAFE CLOSED" in output
    assert "No orders, broadcasts, transfers, claims or gate changes were made." in output
    assert "Every Buy/Sell order rechecks canonically inside the atomic mutation" in output
