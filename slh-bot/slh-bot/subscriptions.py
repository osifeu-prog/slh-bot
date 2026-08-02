import json, os, time

PLANS = {
    "free": {"name": "Free", "price": 0, "agents": 5, "tasks": 50, "plugins": 2},
    "pro": {"name": "Pro", "price": 99, "agents": 50, "tasks": 500, "plugins": 10},
    "enterprise": {"name": "Enterprise", "price": 499, "agents": 999, "tasks": 9999, "plugins": 999}
}

DB_FILE = "subscriptions.json"

def load_subscriptions():
    try:
        with open(DB_FILE) as f:
            return json.load(f)
    except:
        return {}

def save_subscriptions(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def get_user_plan(user_id):
    subs = load_subscriptions()
    user = subs.get(str(user_id), {"plan": "free", "since": time.strftime("%Y-%m-%d")})
    return user["plan"]

def set_user_plan(user_id, plan):
    if plan not in PLANS:
        return False
    subs = load_subscriptions()
    subs[str(user_id)] = {"plan": plan, "since": time.strftime("%Y-%m-%d")}
    save_subscriptions(subs)
    return True

def get_plan_info(plan):
    return PLANS.get(plan, PLANS["free"])

def list_plans():
    return PLANS

def check_limit(user_id, resource):
    plan = get_user_plan(user_id)
    info = PLANS.get(plan, PLANS["free"])
    return info.get(resource, 0)
