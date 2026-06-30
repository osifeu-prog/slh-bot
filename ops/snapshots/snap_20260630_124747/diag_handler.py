import re, os, sys, time, datetime

def diagnose(m):
    issues = []
    cwd = os.path.expanduser("~/slh_clean")
    code_path = os.path.join(cwd, "bot.py")
    
    # 1. Bot file exists
    if not os.path.exists(code_path):
        issues.append("❌ bot.py not found")
        bot.reply_to(m, "\n".join(issues))
        return
    
    with open(code_path, "r") as f:
        code = f.read()
    
    # 2. Check guard
    if 'SLH_LOCAL' not in code:
        issues.append("❌ SLH_LOCAL guard missing")
    else:
        issues.append("✅ SLH_LOCAL guard present")
    
    # 3. Check essential functions
    essential = ['sync', 'id', 'request', 'vbackup', 'fullcheck', 'diagnose']
    for cmd in essential:
        if f"commands=['{cmd}']" in code:
            issues.append(f"✅ /{cmd} exists")
        else:
            issues.append(f"❌ /{cmd} missing")
    
    # 4. Syntax check
    import py_compile
    try:
        py_compile.compile(code_path, doraise=True)
        issues.append("✅ Syntax OK")
    except py_compile.PyCompileError as e:
        issues.append(f"❌ Syntax error: {e}")
    
    # 5. Imports
    try:
        import slh
        issues.append("✅ slh importable")
    except:
        issues.append("❌ slh import failed")
    
    # 6. DB
    db_path = os.path.join(cwd, "db.json")
    if os.path.exists(db_path):
        issues.append("✅ db.json exists")
    else:
        issues.append("❌ db.json missing")
    
    # 7. Python version
    issues.append(f"🐍 Python {sys.version.split()[0]}")
    
    # 8. Overall
    if any("❌" in i for i in issues):
        issues.insert(0, "⚠️ Issues found:")
    else:
        issues.insert(0, "✅ No issues detected.")
    
    bot.reply_to(m, "\n".join(issues))
