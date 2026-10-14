from urllib.parse import parse_qs, urlsplit
from types import SimpleNamespace

from handlers.exchange_handler import build_exchange_chart_url, register


def test_chart_deep_link_uses_exchange_screen_and_preserves_safe_query():
    url = build_exchange_chart_url(
        "https://example.com/mini-app-v4?lang=he&screen=home&chart=0#ignored"
    )
    parsed = urlsplit(url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "example.com"
    assert parsed.path == "/mini-app-v4"
    assert query == {"lang": ["he"], "screen": ["exchange"], "chart": ["1"]}
    assert parsed.fragment == ""


def test_chart_deep_link_falls_back_when_base_url_is_not_https():
    url = build_exchange_chart_url("http://example.com/mini-app")
    parsed = urlsplit(url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "slh-cloud-bot-production.up.railway.app"
    assert parsed.path == "/mini-app-v4"
    assert query["screen"] == ["exchange"]
    assert query["chart"] == ["1"]


def test_chart_command_is_registered_and_returns_a_telegram_web_app_button(monkeypatch):
    class FakeBot:
        def __init__(self):
            self.handlers = {}
            self.replies = []

        def message_handler(self, **options):
            def decorator(handler):
                for command in options.get("commands", []) or []:
                    self.handlers[command] = handler
                return handler
            return decorator

        def reply_to(self, message, text, **kwargs):
            self.replies.append((message, text, kwargs))

    monkeypatch.setenv("SLH_MINI_APP_URL", "https://example.com/mini-app-v4?lang=he")
    bot = FakeBot()
    msg = SimpleNamespace(text="/chart", from_user=SimpleNamespace(id=123), chat=SimpleNamespace(type="private"))

    register(bot)
    assert "chart" in bot.handlers

    bot.handlers["chart"](msg)

    assert len(bot.replies) == 1
    _, reply_text, options = bot.replies[0]
    assert "עסקאות פנימיות שהושלמו בלבד" in reply_text
    markup = options["reply_markup"]
    button = markup.keyboard[0][0]
    assert button.text == "📈 פתח את בורסת SLH"
    query = parse_qs(urlsplit(button.web_app.url).query)
    assert query["screen"] == ["exchange"]
    assert query["chart"] == ["1"]
    assert query["lang"] == ["he"]
