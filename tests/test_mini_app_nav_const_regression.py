from pathlib import Path


def test_mini_app_navigation_stack_is_reassignable():
    src = Path("mini_app.html").read_text(encoding="utf-8")
    assert "let __slhNavStack=['home'];let __slhShowing='home';let __slhNavReady=false;" in src
    assert "const __slhNavStack=['home'];let __slhShowing='home';let __slhNavReady=false;" not in src
