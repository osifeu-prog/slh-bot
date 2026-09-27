from unittest.mock import patch

from core import ui_preferences


def test_theme_aliases_and_validation():
    assert ui_preferences.normalize_theme("כהה") == "calm"
    assert ui_preferences.normalize_theme("telegram") == "system"
    assert ui_preferences.normalize_theme("ניגודיות") == "contrast"
    assert ui_preferences.validate_theme("בהיר") == "light"
    try:
        ui_preferences.validate_theme("unknown-theme")
    except ValueError as exc:
        assert str(exc) == "THEME_INVALID"
    else:
        raise AssertionError("invalid theme was accepted")


def test_preferences_are_stored_in_canonical_db():
    db = {"users": {}}

    with patch.object(ui_preferences.state_manager, "load_db", return_value=db), patch.object(
        ui_preferences.state_manager, "atomic_update", side_effect=lambda fn: fn(db)
    ):
        prefs = ui_preferences.set_preferences("123", theme="light")

    assert prefs["theme"] == "light"
    assert db["ui_preferences"]["123"]["theme"] == "light"


def test_get_preferences_defaults_are_stable():
    with patch.object(ui_preferences.state_manager, "load_db", return_value={"users": {}}):
        prefs = ui_preferences.get_preferences("123")
    assert prefs == {"theme": "calm", "language": "he", "compact": False}
