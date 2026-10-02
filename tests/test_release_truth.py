import pytest

from handlers import deploy_handler


def test_release_status_ignores_historical_removed_deployments(monkeypatch):
    deployments = [
        {
            "id": "current-web",
            "status": "SUCCESS",
            "meta": {"commitHash": "a" * 40},
        },
        {
            "id": "current-mcp",
            "status": "SUCCESS",
            "meta": {"commitHash": "a" * 40},
        },
    ]
    calls = iter(deployments)
    monkeypatch.setattr(deploy_handler, "_latest_deployment", lambda token, target: next(calls))
    monkeypatch.setattr(
        deploy_handler,
        "_managed_targets",
        lambda include_infrastructure=False: {
            "web": {"railway_project": "endearing-amazement", "service": "web"},
            "mcp": {"railway_project": "endearing-amazement", "service": "slh-mcp"},
            "old": {"railway_project": "legacy", "service": "old"},
        },
    )

    targets = deploy_handler._managed_targets()
    canonical = [
        name for name, target in targets.items()
        if target.get("railway_project") == "endearing-amazement"
        and target.get("service") in ("web", "slh-mcp")
    ]
    assert canonical == ["web", "mcp"]

    rows = []
    for name in canonical:
        dep = deploy_handler._latest_deployment("token", targets[name])
        rows.append((name, dep["status"], dep["meta"]["commitHash"]))

    assert all(row[1] == "SUCCESS" for row in rows)
    assert len({row[2] for row in rows}) == 1


def test_release_status_detects_commit_mismatch():
    rows = [
        ("web", "SUCCESS", "a" * 40),
        ("slh-mcp", "SUCCESS", "b" * 40),
    ]
    commits = {row[2] for row in rows if row[2]}
    assert len(commits) != 1


def test_release_status_detects_expected_commit_mismatch():
    rows = [
        ("web", "SUCCESS", "a" * 40),
        ("slh-mcp", "SUCCESS", "a" * 40),
    ]
    expected = "b" * 40
    assert not all(row[2] == expected for row in rows)
