"""Deterministic Alpha readiness and open-state control plane.

Readiness is evaluated from concrete runtime/code/state contracts. No LLM-generated
readiness claim is accepted. ``evaluate`` is read-only; ``open_alpha`` is the only
state-changing operation and is owner-gated by its caller.
"""

import ast
from pathlib import Path
import json
import os
import time
from datetime import datetime, timezone

import state_manager
from core.exec_policy import is_owner

ROOT = Path(__file__).resolve().parent.parent
ALPHA_KEY = "alpha_control"


def _check(name, passed, detail=""):
    return {"name": name, "status": "PASS" if passed else "FAIL", "detail": detail}


def _token_integrity(users, ledger):
    """Validate SLH state without requiring a historical ledger for zero supply.

    A ledger is mandatory once any wallet carries a non-zero SLH balance. A
    fresh/legacy state with every token balance at zero is valid before the
    first canonical distribution and must not be blocked solely because no
    ledger entries exist yet. This never creates or changes token balances.
    """
    if isinstance(ledger, list):
        return True, "SLH token ledger available"

    nonzero = []
    for uid, user in (users or {}).items():
        wallet = user.get("wallet", {}) if isinstance(user, dict) else {}
        try:
            balance = float(wallet.get("token_balance", 0) or 0)
        except (TypeError, ValueError):
            return False, f"invalid token_balance for {uid}"
        if balance != 0:
            nonzero.append(str(uid))

    if nonzero:
        return False, "non-zero SLH balances require a token ledger"
    return True, "zero SLH supply; ledger not yet required"


def _source_tree(path):
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeError):
        return None


def _function_names(tree):
    if tree is None:
        return set()
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _decorator_commands(tree):
    """Return command names declared by telebot message-handler decorators."""
    commands = set()
    if tree is None:
        return commands
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if not isinstance(decorator.func, ast.Attribute) or decorator.func.attr != "message_handler":
                continue
            for keyword in decorator.keywords:
                if keyword.arg != "commands":
                    continue
                value = keyword.value
                if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
                    for item in value.elts:
                        if isinstance(item, ast.Constant) and isinstance(item.value, str):
                            commands.add(item.value.lstrip("/"))
    return commands


def _call_names(tree):
    if tree is None:
        return set()
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
    return names


def _static_contract(path, *, functions=(), commands=(), calls=()):
    tree = _source_tree(path)
    if tree is None:
        return False, "source unavailable or invalid Python"
    found_functions = _function_names(tree)
    found_commands = _decorator_commands(tree)
    found_calls = _call_names(tree)
    missing = []
    missing.extend(f"function:{name}" for name in functions if name not in found_functions)
    missing.extend(f"command:/{name}" for name in commands if name not in found_commands)
    missing.extend(f"call:{name}" for name in calls if name not in found_calls)
    if missing:
        return False, "missing " + ", ".join(missing)
    return True, "static contract present"


def _course_contract():
    course_file = ROOT / "courses.json"
    try:
        catalog = json.loads(course_file.read_text(encoding="utf-8"))
        course = catalog.get("bitcoin_mastery", {})
        stages = course.get("stages", [])
        first = next((item for item in stages if int(item.get("id")) == 1), None)
        lesson_path = ROOT / str(first.get("lesson", "")) if first else None
        ok = bool(first and lesson_path and lesson_path.is_file())
        return ok, "bitcoin_mastery stage 1 and lesson file present" if ok else "bitcoin_mastery stage 1/lesson missing"
    except Exception as exc:
        return False, f"course catalog invalid: {type(exc).__name__}"


def _evaluate_safety():
    """Static guard that keeps evaluate() read-only."""
    tree = _source_tree(Path(__file__))
    if tree is None:
        return False, "alpha control plane source unavailable"
    evaluate_node = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "evaluate"),
        None,
    )
    if evaluate_node is None:
        return False, "evaluate function missing"
    forbidden = {
        "atomic_update", "create_agent", "record_transaction",
        "record_stars_payment", "record_vip_subscription_payment",
        "open_alpha", "stake_credits", "unstake_credits",
    }
    used = set()
    for node in ast.walk(evaluate_node):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                used.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                used.add(node.func.attr)
    violations = sorted(used & forbidden)
    return (False, "evaluate uses forbidden mutation calls: " + ", ".join(violations)) if violations else (True, "evaluate is statically read-only")


def _user_journey_contracts():
    onboarding = ROOT / "handlers" / "onboarding_v2.py"
    join = ROOT / "handlers" / "join_handler.py"
    payment = ROOT / "handlers" / "payment_handler.py"
    agent = ROOT / "core" / "agent_registry.py"
    academy = ROOT / "core" / "academy_manager.py"
    referral = ROOT / "core" / "referral_reward.py"
    stars = ROOT / "core" / "stars_payment_authority.py"
    prices = ROOT / "core" / "stars_price_authority.py"

    checks = []
    ok, detail = _static_contract(onboarding, commands=("start",))
    checks.append(_check("entry_onboarding", ok, detail))
    ok, detail = _static_contract(join, functions=("register",), commands=("join",), calls=("create_agent", "update_user", "start_course"))
    checks.append(_check("join_chain", ok, detail))
    ok, detail = _static_contract(agent, functions=("create_agent",))
    checks.append(_check("personal_agent", ok, detail))
    ok, detail = _static_contract(academy, functions=("start_course", "complete_stage"))
    checks.append(_check("academy_authority", ok, detail))
    ok, detail = _course_contract()
    checks.append(_check("academy_lesson_1", ok, detail))
    ok, detail = _static_contract(join, calls=("_persist_referral", "maybe_award"))
    checks.append(_check("referral_chain", ok, detail))
    ok, detail = _static_contract(referral, functions=("maybe_award",), calls=("atomic_update",))
    checks.append(_check("referral_authority", ok, detail))
    ok, detail = _static_contract(payment, commands=("pay",), calls=("record_stars_payment", "record_vip_subscription_payment"))
    checks.append(_check("stars_payment_handler", ok, detail))
    ok, detail = _static_contract(stars, functions=("record_stars_payment", "record_vip_subscription_payment"), calls=("atomic_update",))
    checks.append(_check("stars_payment_authority", ok, detail))
    ok, detail = _static_contract(prices, functions=("resolve_credit_pack",))
    checks.append(_check("stars_price_authority", ok, detail))
    return checks


def evaluate():
    checks = []
    gateway = ROOT / "bot_gateway.py"
    checks.append(_check("runtime", gateway.exists(), "bot_gateway.py present"))

    # RUN_BOT is an optional deployment hint. If explicitly configured it must be 1;
    # absence must not falsely block an already-running gateway/runtime.
    run_bot = str(os.getenv("RUN_BOT", "")).strip()
    checks.append(_check("run_bot_config", run_bot in ("", "1"),
                         "RUN_BOT unset or RUN_BOT=1"))

    db_path = ROOT / "state" / "db.json"
    try:
        db = json.loads(db_path.read_text(encoding="utf-8"))
        checks.append(_check("canonical_state", isinstance(db, dict) and "users" in db,
                             "state/db.json readable with users"))
    except Exception as exc:
        db = {}
        checks.append(_check("canonical_state", False, type(exc).__name__))

    users = db.get("users", {}) if isinstance(db, dict) else {}
    checks.append(_check("economy", isinstance(users, dict), "users wallet store available"))
    ledger = db.get("slh_token_ledger") if isinstance(db, dict) else None
    token_ok, token_detail = _token_integrity(users, ledger)
    checks.append(_check("slh_integrity", token_ok, token_detail))
    checks.append(_check("slh_transfer", (ROOT / "core" / "slh_distribution.py").exists(),
                         "SLH distribution authority present"))
    checks.append(_check("payments", (ROOT / "handlers" / "payment_handler.py").exists(),
                         "payment handler present"))

    exchange = ROOT / "handlers" / "exchange_handler.py"
    if not exchange.exists():
        exchange = ROOT / "core" / "exchange_service.py"
    checks.append(_check("exchange", exchange.exists(), "exchange path present"))
    checks.append(_check("staking", (ROOT / "core" / "staking_service.py").exists(),
                         "staking service present"))

    settlement = ROOT / "core" / "reward_engine.py"
    try:
        from core.reward_engine import claim_reward
        settlement_ok = settlement.exists() and callable(claim_reward)
    except Exception:
        settlement_ok = False
    checks.append(_check("staking_reward_settlement", settlement_ok,
                         "staking reward claim authority present"))

    checks.append(_check("onboarding", (ROOT / "handlers" / "onboarding_v2.py").exists(),
                         "onboarding handler present"))

    checks.extend(_user_journey_contracts())
    safety_ok, safety_detail = _evaluate_safety()
    checks.append(_check("gate_safety", safety_ok, safety_detail))

    blockers = [c for c in checks if c["status"] != "PASS"]
    return {"status": "BLOCKED" if blockers else "READY", "blockers": blockers,
            "checks": checks, "timestamp": time.time()}


def format_report(result):
    lines = ["ALPHA CONTROL PLANE", "────────────────────"]
    for check in result["checks"]:
        lines.append(f"{check['name']:<28} {check['status']}")
    lines += ["────────────────────", f"BLOCKERS: {len(result['blockers'])}",
              f"STATUS: {result['status']}"]
    return "\n".join(lines)


def alpha_state():
    db = state_manager.load_db()
    value = db.get(ALPHA_KEY, {}) if isinstance(db, dict) else {}
    return dict(value) if isinstance(value, dict) else {}


def open_alpha(owner_id):
    """Open Alpha only when the deterministic gate is READY and caller is owner."""
    if not is_owner(owner_id):
        raise PermissionError("Owner only.")

    result = evaluate()
    if result["status"] != "READY":
        raise RuntimeError(format_report(result))
    owner_id = str(owner_id)

    def mutate(db):
        state = db.setdefault(ALPHA_KEY, {})
        if state.get("status") == "OPEN":
            return dict(state)
        now = datetime.now(timezone.utc).isoformat()
        state.update({"status": "OPEN", "opened_by": owner_id,
                      "opened_at": now, "gate_timestamp": result["timestamp"]})
        return dict(state)

    return state_manager.atomic_update(mutate)


if __name__ == "__main__":
    print(format_report(evaluate()))
