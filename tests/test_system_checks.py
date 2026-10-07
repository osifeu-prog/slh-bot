from pathlib import Path

from core.command_registry import _extract_commands


def test_system_check_commands_are_registered_in_source():
    source = Path("handlers/system_checks_handler.py").read_text(encoding="utf-8")
    found = _extract_commands(source)
    assert {"check", "checks", "check_ux", "check_money", "check_bnb", "check_ton"} <= found


def test_miniapp_contract_contains_new_public_shell():
    source = Path("mini_app.html").read_text(encoding="utf-8")
    for marker in ('id="balance"', 'id="move"', 'id="growth"', 'id="investor"', 'id="profile"'):
        assert marker in source


def test_system_check_module_exposes_read_only_contract():
    source = Path("core/system_checks.py").read_text(encoding="utf-8")
    for marker in ("def check_db", "def check_commands", "def check_ux", "def check_money", "def check_bnb", "def check_ton"):
        assert marker in source
