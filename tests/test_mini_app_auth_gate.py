from pathlib import Path


HTML = Path(__file__).resolve().parents[1] / "mini_app.html"


def test_mini_app_requires_telegram_webapp_auth_before_private_data_load():
    html = HTML.read_text(encoding="utf-8")
    assert 'id="authGate"' in html
    assert "showAuthGate()" in html
    assert "if(!initData){showAuthGate();return}" in html
