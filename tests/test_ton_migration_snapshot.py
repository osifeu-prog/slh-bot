import json
from pathlib import Path


def test_snapshot_tool_is_preflight_only():
    src = Path("tools/ton_migration_snapshot.py").read_text(encoding="utf-8")
    assert "execution_allowed" in src
    assert "PENDING_POLICY_APPROVAL" in src
    assert "No TON Jetton is created by this tool." in src
    assert "mint" not in src.lower().split("notes", 1)[0]


def test_snapshot_tool_supports_etherscan_v2_bsc():
    src = Path("tools/ton_migration_snapshot.py").read_text(encoding="utf-8")
    assert '"chainid": "56"' in src
    assert '"action": "tokenholderlist"' in src
    assert '"offset": min(offset, 1000)' in src


def test_snapshot_schema_does_not_auto_allocate():
    src = Path("tools/ton_migration_snapshot.py").read_text(encoding="utf-8")
    assert '"allocation_status": "PENDING_POLICY_APPROVAL"' in src
    assert 'if allocation_mode != "REVIEW_REQUIRED"' in src
