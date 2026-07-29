import sqlite3
from web3 import Web3

BSC_RPC = "https://bsc-dataseed.binance.org/"
SLH_CONTRACT = "0xACb0A09414CEA1C879c67bB7A877E4e19480f022"
DB_NAME = 'slh_empire.db'

w3 = Web3(Web3.HTTPProvider(BSC_RPC))

SLH_ABI = [{"constant":True,"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"type":"function"}]
contract = w3.eth.contract(address=w3.to_checksum_address(SLH_CONTRACT), abi=SLH_ABI)

def get_slh_balance(address):
    try:
        balance = contract.functions.balanceOf(w3.to_checksum_address(address)).call()
        return balance / (10**18)
    except:
        return 0

def sync_binance_users():
    users_map = {
        "OWNER": "0xכתובת_הארנק_שלך", # תחליף כאן
    }

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    for user_id, wallet in users_map.items():
        balance = get_slh_balance(wallet)
        c.execute("INSERT OR REPLACE INTO wallets VALUES (?,?)", (user_id, int(balance)))
        print(f"סונכרן {user_id}: {balance} SLH")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    sync_binance_users()
