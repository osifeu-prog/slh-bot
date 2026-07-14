import json, requests, os

BSC_RPC = 'https://bsc-dataseed.binance.org/'
CONTRACT = "0xACb0A09414CEA1C879c67bB7A877E4e19480f022"
DEFAULT_WALLET = "0x693db6c817083818696a7228aEbfBd0Cd3371f02"

def get_total_supply():
    data = '0x18160ddd'
    r = requests.post(BSC_RPC, json={'jsonrpc':'2.0','method':'eth_call','params':[{'to':CONTRACT,'data':data},'latest'],'id':1})
    return int(r.json().get('result', '0x0'), 16) / 1e18 if r.ok else None

def get_balance(wallet):
    data = '0x70a08231' + wallet[2:].lower().rjust(64, '0')
    r = requests.post(BSC_RPC, json={'jsonrpc':'2.0','method':'eth_call','params':[{'to':CONTRACT,'data':data},'latest'],'id':1})
    return int(r.json().get('result', '0x0'), 16) / 1e18 if r.ok else None

def register(bot):
    @bot.message_handler(commands=['token'])
    def token_cmd(m):
        parts = m.text.split()
        if len(parts) < 2:
            bot.reply_to(m, "Usage: /token <supply|balance> [wallet]")
            return
        cmd = parts[1].lower()
        if cmd == "supply":
            s = get_total_supply()
            bot.reply_to(m, f"💰 SLH Total Supply: {s:,.2f}" if s else "❌ Error")
        elif cmd == "balance":
            wallet = parts[2] if len(parts) > 2 else DEFAULT_WALLET
            bal = get_balance(wallet)
            bot.reply_to(m, f"💰 Balance: {bal:,.4f} SLH" if bal is not None else "❌ Error")
        else:
            bot.reply_to(m, "Options: /token supply | /token balance [wallet]")

def get_supply():
    import json
    with open("state/db.json", "r") as f:
        db = json.load(f)
    return db.get("token", {}).get("supply", 0)

def get_balance(user_id):
    import json
    user_id = str(user_id)
    with open("state/db.json", "r") as f:
        db = json.load(f)
    return db.get("token", {}).get("balances", {}).get(user_id, 0)
