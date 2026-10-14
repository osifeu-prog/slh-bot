from types import SimpleNamespace

import doctor_handler


def test_git_status_is_unknown_when_deployment_has_no_git_metadata(tmp_path):
    assert "לא ניתן לאמת Git" in doctor_handler._git_status_label(tmp_path)


def test_git_status_reports_clean_only_when_git_confirms_clean(monkeypatch, tmp_path):
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(
        doctor_handler.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=""),
    )
    assert doctor_handler._git_status_label(tmp_path) == "🟢 clean"


def test_git_status_reports_local_changes(monkeypatch, tmp_path):
    (tmp_path / ".git").mkdir()
    monkeypatch.setattr(
        doctor_handler.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=" M core/example.py\n"),
    )
    assert "שינויים מקומיים" in doctor_handler._git_status_label(tmp_path)


def test_overall_health_is_not_green_when_a_check_failed():
    assert "🔴" in doctor_handler._overall_health_label({"Bot": "🟢", "DB": "🔴 missing"})


def test_overall_health_is_partial_when_a_check_is_unverified():
    assert "🟡" in doctor_handler._overall_health_label({"Bot": "🟢", "Git": "⚪️ לא אומת"})


def test_overall_health_is_green_only_when_all_checks_are_green():
    assert doctor_handler._overall_health_label({"Bot": "🟢", "DB": "🟢"}) == "🟢 כל הבדיקות שנכללו עברו"
