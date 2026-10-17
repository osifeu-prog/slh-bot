from unittest.mock import patch

import bot_gateway


class FakeBot:
    def __init__(self):
        self.menu_button = None
        self.command_sets = []

    def set_chat_menu_button(self, *, menu_button):
        self.menu_button = menu_button

    def set_my_commands(self, commands, *, language_code=None):
        self.command_sets.append({
            "language_code": language_code,
            "commands": commands,
        })


def test_startup_menu_configuration_includes_social_asset_gallery_in_both_languages(monkeypatch):
    monkeypatch.setenv("SLH_MINI_APP_URL", "https://slh-cloud-bot-production.up.railway.app/mini-app-v4")
    bot = FakeBot()
    with patch.object(bot_gateway, "log"):
        bot_gateway.configure_default_mini_app_menu(bot)

    assert bot.menu_button is not None
    assert [item["language_code"] for item in bot.command_sets] == ["", "he"]
    for command_set in bot.command_sets:
        commands = {item.command: item.description for item in command_set["commands"]}
        assert "media" in commands
        assert "share" in commands
        assert "start" in commands
    english = {item.command: item.description for item in bot.command_sets[0]["commands"]}
    hebrew = {item.command: item.description for item in bot.command_sets[1]["commands"]}
    assert english["media"] == "Brand images & sharing"
    assert hebrew["media"] == "מאגר תמונות לשיתוף"


def test_command_menu_api_failure_does_not_prevent_mini_app_menu(monkeypatch):
    monkeypatch.delenv("SLH_MINI_APP_URL", raising=False)

    class FailingBot(FakeBot):
        def set_my_commands(self, commands, *, language_code=None):
            raise RuntimeError("not available")

    bot = FailingBot()
    with patch.object(bot_gateway, "log"):
        bot_gateway.configure_default_mini_app_menu(bot)

    assert bot.menu_button is not None
