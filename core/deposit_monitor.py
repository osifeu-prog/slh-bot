"""
SLH Onchain Deposit Monitor v1
Reads BSC treasury balances from RPC.
"""
from web3 import Web3
from core.binance_connector import get_bsc_config

ERC20_ABI = [
    {"constant": True, "inputs": [{"name": "_owner", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}], "type": "function"},
    {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"name": "", "type": "uint8"}], "type": "function"},
]

def get_onchain_status():
    cfg = get_bsc_config()
    w3 = Web3(Web3.HTTPProvider(cfg["rpc"]))
    treasury = w3.to_checksum_address(cfg["treasury_wallet"])
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(cfg["token_contract"]),
        abi=ERC20_ABI,
    )

    slh_raw = contract.functions.balanceOf(treasury).call()
    dec = contract.functions.decimals().call()
    slh = slh_raw / (10 ** dec)
    bnb = w3.from_wei(w3.eth.get_balance(treasury), "ether")

    return {
        "chain_id": w3.eth.chain_id,
        "block": w3.eth.block_number,
        "treasury_wallet": cfg["treasury_wallet"],
        "token_contract": cfg["token_contract"],
        "treasury_bnb": float(bnb),
        "treasury_slh": float(slh),
        "symbol": "SLH",
        "network": cfg["network"],
    }
