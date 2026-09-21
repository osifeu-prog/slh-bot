from core.telegram_token_registry import get_bot, list_bots, targets_for


def test_known_bot_registry_is_non_secret_and_complete():
    bots = {b["alias"]: b for b in list_bots()}
    assert {"main", "air", "claude", "ton"}.issubset(bots)
    assert bots["main"]["username"] == "Me_ad_main_bot"
    assert bots["air"]["username"] == "SLH_AIR_bot"
    assert bots["claude"]["username"] == "SLH_Claude_bot"
    assert bots["ton"]["username"] == "TON_MNH_bot"
    rendered = repr(bots)
    assert "token" not in rendered.lower()


def test_air_uses_dedicated_telegram_token_variable():
    targets = targets_for("air")
    assert len(targets) == 1
    assert targets[0]["variable"] == "TELEGRAM_TOKEN"
    assert targets[0]["service"] == "slh-air-bot"


def test_claude_uses_dedicated_token_variable():
    targets = targets_for("claude")
    assert len(targets) == 1
    assert targets[0]["variable"] == "SLH_CLAUDE_BOT_TOKEN"
    assert targets[0]["service"] == "slh-AI-bot"


def test_ton_updates_webhook_and_worker():
    targets = targets_for("ton")
    assert len(targets) == 2
    assert {t["service"] for t in targets} == {"SLH_PROJECT_V2", "glorious-caring"}
    assert {t["variable"] for t in targets} == {"BOT_TOKEN"}


def test_unknown_alias_fails_closed():
    try:
        get_bot("not-a-real-bot")
    except KeyError:
        pass
    else:
        raise AssertionError("unknown alias must raise KeyError")
