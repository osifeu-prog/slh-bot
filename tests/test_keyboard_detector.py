from core.keyboard_detector import normalize_keyboard_text, should_convert_keyboard


def test_short_english_is_not_rewritten():
    assert normalize_keyboard_text("go") == "go"
    assert normalize_keyboard_text("tbh") == "tbh"
    assert should_convert_keyboard("go") is False
    assert should_convert_keyboard("tbh") is False


def test_accidental_hebrew_keyboard_input_still_converts():
    assert normalize_keyboard_text("akuo") == "שלום"
    assert should_convert_keyboard("akuo") is True
