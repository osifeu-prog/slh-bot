"""
SLH TON Lab v2
Reads TON wallets, records experiments, estimates valuation.
No private keys. No transaction broadcasting.
"""
import json
import time
import requests
from pathlib import Path

DB = Path("state/db.json")


def get_wallets():
    with DB.open("r", encoding="utf-8") as f:
        db = json.load(f)
    ts = db.get("ton_settings", {})
    return {
        "primary": ts.get("wallet"),
        "all": ts.get("wallets", []),
        "rate": ts.get("rate"),
        "testnet": ts.get("testnet"),
    }


def record_experiment(name, payload):
    with DB.open("r", encoding="utf-8") as f:
        db = json.load(f)
    exp = {
        "name": name,
        "timestamp": time.time(),
        "payload": payload,
    }
    db.setdefault("experiments", []).append(exp)
    with DB.open("w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    return exp


def estimate_valuation(hourly_rate_usd=80):
    with DB.open("r", encoding="utf-8") as f:
        db = json.load(f)

    users = db.get("users", {})
    dev_count = sum(
        1 for u in users.values()
        if u.get("role") == "developer" and u.get("status") == "active"
    )
    total_credits = sum(
        u.get("wallet", {}).get("credits", 0)
        for u in users.values()
    )
    total_staked = sum(
        u.get("wallet", {}).get("staked", 0)
        for u in users.values()
    )
    tasks = db.get("tasks", {})
    task_count = len(tasks)
    total_progress = sum(t.get("progress", 0) for t in tasks.values()) if tasks else 0
    progress = int(total_progress / task_count) if task_count else 0

    experiments = db.get("experiments", [])
    experiments_count = len(experiments)

    bsc = db.get("bsc_settings", {})
    ton = db.get("ton_settings", {})

    dev_value = dev_count * 40 * hourly_rate_usd
    economic_value = total_credits * 0.01 + total_staked * 0.05
    infra_value = 5000
    experiment_value = experiments_count * 25

    total_estimated = dev_value + economic_value + infra_value + experiment_value

    return {
        "hourly_rate_usd": hourly_rate_usd,
        "users": len(users),
        "active_developers": dev_count,
        "total_credits": total_credits,
        "total_staked": total_staked,
        "task_progress": progress,
        "task_total_progress": total_progress,
        "task_count": task_count,
        "experiments": experiments_count,
        "bsc_treasury": bsc.get("treasury_wallet"),
        "ton_wallets": ton.get("wallets", []),
        "estimated_value_usd": total_estimated,
    }


def valuation_report():
    v = estimate_valuation()
    lines = [
        "📊 SLH Valuation Estimate",
        f"👥 Users: {v['users']}",
        f"🧑‍💻 Active Devs: {v['active_developers']}",
        f"💰 Credits: {v['total_credits']}",
        f"🔒 Staked: {v['total_staked']}",
        f"📋 Tasks: {v['task_count']} | Progress: {v['task_progress']}%",
        f"🧪 Experiments: {v['experiments']}",
        f"💠 BSC Treasury: {v['bsc_treasury']}",
        f"💎 TON Wallets: {len(v['ton_wallets'])}",
        "",
        f"💵 Estimated Value: ${v['estimated_value_usd']:,.2f}",
    ]
    for b in ton_balances():
        addr = str(b.get("address", ""))
        bal = b.get("balance_ton", 0.0)
        short = addr[:12] + "..." if addr else "unknown"
        lines.append(f"💎 TON {short}: {bal} TON")
    return "\n".join(lines)


def get_ton_balance(address):
    url = "https://toncenter.com/api/v2/getAddressInformation"
    try:
        r = requests.get(url, params={"address": address}, timeout=10)
        data = r.json()
        if data.get("ok") and "result" in data:
            return int(data["result"].get("balance", 0)) / 1e9
    except Exception:
        pass
    return None


def ton_balances():
    wallets = get_wallets()
    out = []
    for w in wallets.get("all", []):
        out.append({"address": w, "balance_ton": get_ton_balance(w)})
    return out


def verify_ton_deposit(tx_hash):
    import requests, json
    db = json.load(open("state/db.json", encoding="utf-8"))
    wallet = db.get("ton_settings", {}).get("wallet")
    if not wallet:
        return {"ok": False, "error": "TON wallet not configured"}
    url = "https://toncenter.com/api/v2/getTransactions"
    params = {"address": wallet, "limit": 20, "to_lt": 0, "archival": False}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if not data.get("ok"):
            return {"ok": False, "error": "toncenter error"}
        for tx in data.get("result", []):
            tx_hash_api = tx.get("transaction_id", {}).get("hash", "")
            if tx_hash_api.lower() == tx_hash.lower():
                in_msg = tx.get("in_msg", {})
                value = int(in_msg.get("value", 0))
                source = in_msg.get("source", "")
                amount_ton = value / 1e9
                return {"ok": True, "from": source, "amount_ton": amount_ton, "tx_hash": tx_hash}
        return {"ok": False, "error": "tx not found"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
