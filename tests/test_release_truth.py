import pytest

from handlers import deploy_handler


def test_release_truth_targets_include_canonical_web_and_mcp(monkeypatch):
    monkeypatch.setattr(
        deploy_handler,
        "_load_registry",
        lambda: {
            "canonical": {
                "railway_project": "endearing-amazement",
                "railway_project_id": "project-1",
                "railway_environment_id": "env-1",
            },
            "railway_projects": [
                {
                    "name": "endearing-amazement",
                    "id": "project-1",
                    "environment_id": "env-1",
                    "services": [
                        {"name": "web", "id": "web-1", "class": "primary"},
                        {"name": "slh-mcp", "id": "mcp-1", "class": "mcp_control_plane"},
                    ],
                },
                {
                    "name": "legacy",
                    "id": "legacy-1",
                    "environment_id": "env-1",
                    "services": [
                        {"name": "web", "id": "legacy-web", "class": "primary"},
                    ],
                },
            ],
        },
    )

    targets = deploy_handler._release_truth_targets()

    assert set(targets) == {"web", "slh-mcp"}
    assert targets["web"]["railway_service_id"] == "web-1"
    assert targets["slh-mcp"]["railway_service_id"] == "mcp-1"


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
    monkeypatch.setattr(
        deploy_handler,
        "_latest_deployment",
        lambda token, target: next(calls),
    )
    monkeypatch.setattr(
        deploy_handler,
        "_release_truth_targets",
        lambda: {
            "web": {"service": "web"},
            "slh-mcp": {"service": "slh-mcp"},
        },
    )

    targets = deploy_handler._release_truth_targets()
    rows = []
    for name, target in sorted(targets.items()):
        dep = deploy_handler._latest_deployment("token", target)
        rows.append((name, dep["status"], dep["meta"]["commitHash"]))

    assert [row[0] for row in rows] == ["slh-mcp", "web"]
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
