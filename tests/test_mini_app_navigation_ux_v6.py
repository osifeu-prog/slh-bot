from pathlib import Path

HTML = Path(__file__).resolve().parents[1] / "mini_app.html"


def test_primary_navigation_prioritizes_home_wallet_exchange_and_market():
    html = HTML.read_text(encoding="utf-8")
    assert '<nav class="bottom ux-bottom" aria-label="ניווט ראשי">' in html
    for element_id in ("bh", "bw", "bx", "bmarket", "bmore"):
        assert f'id="{element_id}"' in html
    assert 'aria-label="בורסה ומסחר פנימי"' in html
    assert `onclick="show('exchange')"` in html


def test_more_menu_search_covers_secondary_screens():
    html = HTML.read_text(encoding="utf-8")
    assert 'id="moreSearch"' in html
    assert "oninput=\"filterMoreTools(this.value)\"" in html
    assert "window.filterMoreTools=function(query)" in html
    for screen in ("transfer", "growth", "profile", "investor", "ai", "tonswap", "settings"):
        assert f"show('{screen}')" in html


def test_more_dialog_exposes_accessible_open_and_closed_states():
    html = HTML.read_text(encoding="utf-8")
    assert 'id="mSheet" role="dialog" aria-modal="true"' in html
    assert 'aria-hidden="true"' in html
    assert "m.setAttribute('aria-hidden','false')" in html
    assert "m.setAttribute('aria-hidden','true')" in html
    assert "button.setAttribute('aria-expanded','true')" in html
    assert "button.setAttribute('aria-expanded','false')" in html


def test_active_destination_and_toast_state_are_announced():
    html = HTML.read_text(encoding="utf-8")
    assert "button.setAttribute('aria-current','page')" in html
    assert 'id="toast" class="toast" role="status" aria-live="polite" aria-atomic="true"' in html
