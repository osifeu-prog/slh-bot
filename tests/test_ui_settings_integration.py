from pathlib import Path


MINI_APP = Path("mini_app.html")
WEBAPP = Path("webapp.py")
HELP = Path("handlers/help_handler.py")
LOADER = Path("handlers/loader.py")


def test_bot_and_miniapp_share_settings_surface():
    mini = MINI_APP.read_text(encoding="utf-8")
    web = WEBAPP.read_text(encoding="utf-8")
    loader = LOADER.read_text(encoding="utf-8")

    assert '<section id="settings" class="screen">' in mini
    assert "fetch('/api/v1/settings'" in mini
    assert '@app.route("/api/v1/settings", methods=["GET", "POST"])' in web
    from core import command_catalog
    assert "settings" in command_catalog.KNOWN
    assert "theme" in command_catalog.KNOWN
    assert '("ui_settings", "handlers.ui_settings_handler")' in loader
