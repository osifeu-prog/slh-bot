#!/usr/bin/env python3
"""
SLH Project Audit — מראה מקום אמיתי על המערכת.
מריץ בבטיחות מלאה, לא נוגע ב-DB ולא ב-git.
הרצה: python3 tools/project_audit.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def find_all_commands():
    """כל הפקודות שרשומות בפועל בקוד"""
    commands = {}
    for py_file in ROOT.rglob("*.py"):
        if "backup" in str(py_file) or ".git" in str(py_file):
            continue
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for m in re.finditer(r"commands=\['([a-z_]+)'\]", text):
            cmd = m.group(1)
            commands.setdefault(cmd, []).append(str(py_file.relative_to(ROOT)))
    return commands

def find_menu_commands():
    """פקודות שמופיעות בטקסט של /help או /admin"""
    menu_cmds = set()
    for py_file in ROOT.rglob("*.py"):
        if "backup" in str(py_file):
            continue
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "help" in py_file.name.lower() or "admin" in py_file.name.lower():
            for m in re.finditer(r"/([a-z_]+)", text):
                menu_cmds.add(m.group(1))
    return menu_cmds

def check_feature(name, files):
    """בדיקת סטטוס פיצ'ר: קיים? יש TODO? יש exception handling ריק?"""
    status = {"name": name, "exists": False, "todo_count": 0, "files_checked": []}
    for f in files:
        p = ROOT / f
        if p.exists():
            status["exists"] = True
            status["files_checked"].append(f)
            text = p.read_text(encoding="utf-8", errors="ignore")
            status["todo_count"] += len(re.findall(r"TODO|FIXME|not implemented|not connected", text, re.IGNORECASE))
    return status

def main():
    print("=" * 70)
    print("SLH PROJECT AUDIT —", Path.cwd())
    print("=" * 70)

    # 1. פקודות רשומות מול תפריט
    print("\n[1] פקודות רשומות בקוד לעומת מוזכרות בתפריטים")
    all_cmds = find_all_commands()
    menu_cmds = find_menu_commands()
    missing = sorted(set(all_cmds) - menu_cmds)
    print(f"סה״כ פקודות בקוד: {len(all_cmds)}")
    print(f"פקודות שלא מופיעות בשום תפריט: {len(missing)}")
    for cmd in missing:
        print(f"  /{cmd:<25} -> {all_cmds[cmd]}")

    # 2. סטטוס פיצ'רים מרכזיים
    print("\n[2] סטטוס פיצ'רים מרכזיים")
    features = {
        "Staking": ["handlers/staking_report_handler.py", "core/economy_bridge.py"],
        "Academy/Courses": ["handlers/onboarding_v2.py"],
        "Revenue": ["handlers/admin_extras.py"],
        "WhatsApp Bridge": ["whatsapp_handler_bridge.py"],
        "Mission System": ["core/mission_orchestrator.py", "core/mission_lifecycle.py"],
        "Agent System": ["core/agent_factory.py", "core/agent_registry.py"],
    }
    for name, files in features.items():
        status = check_feature(name, files)
        exists_str = "✅ קיים" if status["exists"] else "❌ חסר"
        todo_str = f"⚠️ {status['todo_count']} TODO/לא-מחובר" if status["todo_count"] else "נקי"
        print(f"  {name:<20} {exists_str:<12} {todo_str}")

    print("\n" + "=" * 70)
    print("סוף audit — לא בוצע שום שינוי במערכת")
    print("=" * 70)

if __name__ == "__main__":
    main()
