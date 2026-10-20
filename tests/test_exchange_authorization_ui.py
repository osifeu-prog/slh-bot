from pathlib import Path


def test_exchange_trader_certification_error_is_persistent_and_actionable():
    html = (Path(__file__).resolve().parents[1] / "mini_app.html").read_text(encoding="utf-8")
    start = html.index("function renderExchangeAuthorizationRequired")
    end = html.index("async function sendExchangeOrder", start)
    renderer = html[start:end]

    assert 'data-exchange-receipt="true"' in renderer
    assert "role','alert'" in renderer
    assert "לא נמצאה הסמכת Trader מאושרת" in renderer
    assert "/trader_test" in renderer
    assert "לא נוצרה הוראה ולא בוצע חיוב" in renderer
    assert "setTimeout" not in renderer

    send_start = html.index("async function sendExchangeOrder")
    send_end = html.index("function prepareTransfer", send_start)
    sender = html[send_start:send_end]
    assert "d.code==='TRADER_CERTIFICATION_REQUIRED'" in sender
    assert "renderExchangeAuthorizationRequired(d,options.sourceInputId)" in sender


def test_staking_screen_has_a_real_create_position_button_and_submission_path():
    html = (Path(__file__).resolve().parents[1] / "mini_app.html").read_text(encoding="utf-8")
    assert 'id="stake" class="screen"' in html
    assert 'onclick="submitStake()"' in html
    assert "fetch('/api/v1/staking'" in html
    assert "fetch('/api/v1/staking/positions'" in html
