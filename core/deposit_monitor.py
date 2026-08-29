"""
SLH Onchain Deposit Monitor v1
"""
import json
from pathlib import Path
from web3 import Web3
from core.binance_connector import get_bsc_config


ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
]


def get_onchain_status():
    try:
        cfg = get_bsc_config()
        db = json.loads(Path("state/db.json").read_text(encoding="utf-8"))
        if "bsc_settings" in db:
            cfg = {**cfg, **db["bsc_settings"]}

        if not cfg.get("treasury_wallet") or not cfg.get("token_contract"):
            return {
                "ok": False,
                "error": "onchain not configured",
                "treasury_wallet": None,
                "token_contract": None,
                "treasury_bnb": 0,
                "treasury_slh": 0,
            }

        w3 = Web3(Web3.HTTPProvider(cfg["rpc"]))
        treasury = w3.to_checksum_address(cfg["treasury_wallet"])
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(cfg["token_contract"]),
            abi=ERC20_ABI,
        )
        slh_raw = contract.functions.balanceOf(treasury).call()
        dec = contract.functions.decimals().call()
        slh = slh_raw / (10**dec)
        bnb = w3.from_wei(w3.eth.get_balance(treasury), "ether")

        return {
            "ok": True,
            "chain_id": w3.eth.chain_id,
            "block": w3.eth.block_number,
            "treasury_wallet": cfg["treasury_wallet"],
            "token_contract": cfg["token_contract"],
            "treasury_bnb": float(bnb),
            "treasury_slh": float(slh),
            "symbol": "SLH",
            "network": cfg.get("network", "bsc"),
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }

def verify_bnb_deposit(tx_hash):
    import json
    from web3 import Web3
    cfg = get_bsc_config()
    with open("state/db.json", encoding="utf-8") as f:
        db = json.load(f)
    cfg = {**cfg, **db.get("bsc_settings", {})}
    w3 = Web3(Web3.HTTPProvider(cfg["rpc"]))
    try:
        tx = w3.eth.get_transaction(tx_hash)
        receipt = w3.eth.get_transaction_receipt(tx_hash)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    if not receipt or receipt.get("status") != 1:
        return {"ok": False, "status": receipt.get("status") if receipt else None}
    treasury = w3.to_checksum_address(cfg["treasury_wallet"])
    to_addr = tx.get("to")
    if to_addr is None or str(to_addr).lower() != str(treasury).lower():
        return {"ok": False, "to": str(to_addr), "treasury": str(treasury)}
    amount = w3.from_wei(tx.get("value", 0), "ether")
    return {
        "ok": True,
        "from": str(tx.get("from")),
        "to": str(to_addr),
        "amount_bnb": float(amount),
        "block": int(receipt.get("blockNumber", 0)),
        "tx_hash": str(tx_hash),
    }
