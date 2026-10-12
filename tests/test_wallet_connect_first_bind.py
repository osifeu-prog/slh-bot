from pathlib import Path


def test_wallet_connect_allows_first_time_binding_with_valid_wallet_session():
    source = Path("wallet_connect.html").read_text(encoding="utf-8")
    init = source.split("async function init(){", 1)[1].split(
        "async function verifyWithProvider", 1
    )[0]
    verify = source.split("async function verifyWithProvider", 1)[1].split(
        "async function discoverMetaMaskProvider", 1
    )[0]

    # An authenticated handoff with no wallet binding is a valid first-run state.
    assert 'const d=await api("/api/wallet/bnb");' in init
    assert 'if(smokeMode&&!binding?.address)throw Error("BNB_WALLET_NOT_VERIFIED");' in init
    assert 'if(!binding?.address)throw Error("BNB_WALLET_NOT_VERIFIED")' not in init
    assert "עדיין אין ארנק BNB מאומת — אפשר להתחיל כאן" in init

    # The canonical one-time challenge signs a message, then verifies server-side.
    assert "if(binding?.address&&address.toLowerCase()!==binding.address.toLowerCase())" in verify
    assert 'api("/api/wallet/bnb/challenge"' in verify
    assert 'method:"personal_sign"' in verify
    assert 'api("/api/wallet/bnb/verify"' in verify
    assert "לא נשלחה עסקה ולא הועבר BNB" in verify


def test_wallet_connect_keeps_transfer_smoke_gated_by_verified_binding():
    source = Path("wallet_connect.html").read_text(encoding="utf-8")
    init = source.split("async function init(){", 1)[1].split(
        "async function verifyWithProvider", 1
    )[0]

    assert 'if(smokeMode&&!binding?.address)throw Error("BNB_WALLET_NOT_VERIFIED");' in init
    assert 'if(String(address).toLowerCase()!==String(binding.address).toLowerCase())' in source
