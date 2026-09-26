from pathlib import Path


def test_trade_dashboard_home_callback_is_wired():
    src = Path("handlers/trade_terminal_handler.py").read_text(encoding="utf-8")
    assert 'action == "home"' in src
    assert '_send_trade_home' in src


def test_miniapp_trade_bridge_and_rewards_debug_are_fixed():
    webapp = Path("handlers/webapp_data_handler.py").read_text(encoding="utf-8")
    mini = Path("mini_app.html").read_text(encoding="utf-8")
    assert '"/trade"' in webapp
    assert 'loadRewardsPanel' in mini
    assert "JSON.stringify(d,null,2)" not in mini


def test_trade_dashboard_button_is_localized():
    src = Path("handlers/onboarding_v2.py").read_text(encoding="utf-8")
    assert "def _trade_button_label" in src
    assert "get_lang(user_id)" in src
    assert 'callback_data="trade:home"' in src



def test_owner_start_passes_user_id_to_dashboard_markup():
    src = Path("handlers/onboarding_v2.py").read_text(encoding="utf-8")
    assert "if is_owner:" in src
    assert "markup = _dashboard_markup(user_id)" in src
