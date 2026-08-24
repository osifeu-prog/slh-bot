"""
SLH TON Lab v1
Reads TON wallets, records experiments, estimates valuation.
No private keys. No transaction broadcasting.
"""
import json
import time
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
    total_progress = sum(t.get("progress", 0) for t in tasks.values())
    progress = int(total_progress / task_count) if task_count else 0
    task_count = len(tasks)

    experiments = db.get("experiments", [])
    experiments_count = len(experiments)

    bsc = db.get("bsc_settings", {})
    ton = db.get("ton_settings", {})

    # Rough valuation: time invested + economic activity + infra
    dev_value = dev_count * 40 * hourly_rate_usd  # 40h/week baseline
    economic_value = total_credits * 0.01 + total_staked * 0.05
    infra_value = 5000  # baseline for working OS + bot + DB + onchain monitors
    experiment_value = experiments_count * 25  # each experiment adds knowledge

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
    return "\n".join(lines)
