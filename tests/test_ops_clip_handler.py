from handlers.admin_extras import OPS_CLIP_ITEMS


def test_ops_clip_items_are_single_line_read_only_commands():
    assert set(OPS_CLIP_ITEMS) == {"gates", "counts", "deposits", "exchange"}
    for item in OPS_CLIP_ITEMS.values():
        command = item["command"]
        assert command.startswith("/e ")
        assert "\n" not in command
        assert "\r" not in command
        lowered = command.lower()
        assert "settle_" not in lowered
        assert "atomic_update" not in lowered
        assert "write_text" not in lowered
        assert "approve_withdraw" not in lowered


def test_gate_clip_uses_existing_ton_gate_function():
    command = OPS_CLIP_ITEMS["gates"]["command"]
    assert "from core.ton_deposit_service import _deposits_open as ton_open" in command
    assert "bnb_deposits_open()" in command
    assert "bnb_settlement_allowed(" in command


def test_deposit_clip_masks_user_and_transaction_identifiers():
    command = OPS_CLIP_ITEMS["deposits"]["command"]
    assert "'uid...'" in command
    assert "'tx...'" in command
    assert "[-4:]" in command
    assert "[-8:]" in command
