from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_investor_screen_exists_in_mini_app():
    html = (ROOT / "mini_app.html").read_text(encoding="utf-8")
    assert 'id="investor" class="screen"' in html
    assert 'const __slhInitialScreens=[' in html
    assert "'investor'" in html
    assert "renderInvestorOverview(d)" in html
    onboarding = (ROOT / "handlers" / "onboarding_v2.py").read_text(encoding="utf-8")
    assert "mini-app-v4?screen=investor" in onboarding


def test_investor_telegram_entry_point_exists():
    source = (ROOT / "handlers" / "onboarding_v2.py").read_text(encoding="utf-8")
    assert 'callback_data="investor_overview"' in source
    assert "mini-app-v4?screen=investor" in source
    assert "Investor Overview" in source
