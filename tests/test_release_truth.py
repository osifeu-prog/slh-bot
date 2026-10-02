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


def test_release_truth_allows_service_specific_commits(monkeypatch):
    deployments = [
        {
            "id": "current-mcp",
            "status": "SUCCESS",
            "meta": {"commitHash": "b" * 40},
        },
        {
            "id": "current-web",
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

    rows = []
    for name, target in sorted(
        deploy_handler._release_truth_targets().items()
    ):
        dep = deploy_handler._latest_deployment("token", target)
        rows.append((name, dep["status"], dep["meta"]["commitHash"]))

    assert all(row[1] == "SUCCESS" for row in rows)
    assert {row[2] for row in rows} == {"a" * 40, "b" * 40}


def test_release_truth_expected_commit_applies_to_web_only():
    rows = [
        ("slh-mcp", "SUCCESS", "b" * 40),
        ("web", "SUCCESS", "a" * 40),
    ]
    expected = "a" * 40

    success = all(row[1] == "SUCCESS" for row in rows)
    web_commit = next(row[2] for row in rows if row[0] == "web")
    expected_ok = web_commit == expected

    assert success
    assert expected_ok


def test_release_truth_blocks_failed_service():
    rows = [
        ("slh-mcp", "FAILED", "b" * 40),
        ("web", "SUCCESS", "a" * 40),
    ]

    assert not all(row[1] == "SUCCESS" for row in rows)
