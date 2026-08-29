#!/usr/bin/env python3
import subprocess, json, os, sys

R = []
def check(name, fn):
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, f"EXCEPTION: {e}"
    R.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} -> {detail}")

# 1. האם הבוט באמת רץ (לא git diff!)
def t_runtime():
    out = subprocess.run(
        "pgrep -af 'python3.*bot_stable' | grep -v real_audit",
        shell=True, capture_output=True, text=True
    ).stdout.strip()
    return (bool(out), out or "no matching process")
check("BOT_RUNNING", t_runtime)

# 2. OWNER - לא לנחש שמות, לבדוק מה באמת קיים
def t_owner():
    import core.identity as idn
    names = [n for n in dir(idn) if not n.startswith("_")]
    return (True, f"identity exports: {names}")
check("IDENTITY_MODULE_CONTENTS", t_owner)

# 3. הרשאות אמיתיות (permissions/admin_utils, לא identity.py)
def t_perm():
    from admin_utils import is_admin
    class M:
        class U: id = 8789977826
        from_user = U()
    result = is_admin(M())
    return (result is True, f"is_admin(8789977826) = {result}")
check("REAL_PERMISSION_CHECK", t_perm)

# 4. guard() - האם באמת יש הגנת כפילויות
def t_guard():
    from core.ask_guard import guard
    r1 = guard("test question 123")
    r2 = guard("test question 123")
    # אם guard תמיד מחזיר True, אין הגנה אמיתית
    return (r1 != r2 or r1 is False, f"call1={r1} call2={r2} (if both True -> NO real dedup)")
check("ASK_GUARD_REAL_DEDUP", t_guard)

# 5. GROQ key + quota status
def t_groq():
    key = bool(os.getenv("GROQ_API_KEY"))
    return (key, f"GROQ_API_KEY set: {key}")
check("GROQ_KEY", t_groq)

# 6. Gemini - מותקן בפועל?
def t_gemini():
    try:
        import google.generativeai
        return (True, "google.generativeai importable")
    except ImportError as e:
        return (False, str(e))
check("GEMINI_INSTALLED", t_gemini)

# 7. local_answer - keyword collision test (הבאג שמצאנו)
def t_local_answer_bug():
    from handlers.advanced_ask_handler import local_answer
    real_question = "מהי מטרת מערכת SLH OS?"
    r = local_answer(real_question, "0")
    return (r is None, f"question='{real_question}' -> {r!r} (should be None to reach LLM)")
check("LOCAL_ANSWER_FALSE_POSITIVE", t_local_answer_bug)

# 8. git state
def t_git():
    ahead = subprocess.run("git status --short --branch", shell=True, capture_output=True, text=True).stdout.splitlines()[0]
    dirty_count = subprocess.run("git status --short | wc -l", shell=True, capture_output=True, text=True).stdout.strip()
    return (True, f"{ahead} | dirty files: {dirty_count}")
check("GIT_STATE", t_git)

print("\n=== SUMMARY ===")
fails = [r for r in R if not r[1]]
print(f"Total: {len(R)}  Failed: {len(fails)}")
for name, ok, detail in fails:
    print(f"  ❌ {name}: {detail}")
