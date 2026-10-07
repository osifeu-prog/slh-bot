from pathlib import Path


def test_bnb_smoke_has_existing_tx_verifier_and_poll():
    source = Path("bnb_smoke.html").read_text(encoding="utf-8")

    assert 'id="txHash"' in source
    assert 'id="verifyExisting"' in source
    assert "async function poll(txHash)" in source
    assert '"/api/wallet/bnb/empirical-smoke"' in source
    assert 'await poll(txHash);' in source
    assert 'BigInt(smoke.amount_wei)' in source
    assert "0.01 BNB" in source
