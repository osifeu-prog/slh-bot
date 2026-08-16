#!/usr/bin/env python3
"""
בודק אילו קבצים באמת נטענים על ידי הבוט ב-runtime,
לעומת קבצים שקיימים בריפו אבל הם ארכיון/גיבוי/מת.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEAD_MARKERS = ["archive", "_archive", "backup", "SLH_ADAPTER_BACKUP", ".bak", "before_"]

def is_dead_path(path_str):
    return any(marker.lower() in path_str.lower() for marker in DEAD_MARKERS)

print("=" * 70)
print("LIVE vs DEAD CODE AUDIT")
print("=" * 70)

try:
    import bot_gateway
    bot = bot_gateway.bot
    handlers = bot.message_handlers

    live_commands = {}
    for h in handlers:
        filters = h.get("filters") or {}
        fn = h.get("function")
        import inspect
        try:
            source = inspect.getsourcefile(fn)
            source = str(Path(source).relative_to(ROOT)) if source else "UNKNOWN"
        except Exception:
            source = "UNKNOWN"
        for c in filters.get("commands") or []:
            live_commands[c] = source

    print(f"\nפקודות שבאמת רשומות ורצות בבוט עכשיו: {len(live_commands)}")
    print("\n[LIVE COMMANDS BY FILE]")
    by_file = {}
    for cmd, src in live_commands.items():
        by_file.setdefault(src, []).append(cmd)
    for src in sorted(by_file):
        cmds = ", ".join(sorted(by_file[src]))
        print(f"  {src}\n    -> {cmds}")

    # בדיקת סטייקינג ספציפית - קריטי למשקיעים
    print("\n[STAKING — בדיקה ממוקדת]")
    staking_cmds = [c for c in live_commands if "stake" in c.lower()]
    if staking_cmds:
        for c in staking_cmds:
            print(f"  /{c} -> {live_commands[c]} {'⚠️ ARCHIVE/DEAD PATH!' if is_dead_path(live_commands[c]) else '✅ LIVE'}")
    else:
        print("  ❌ שום פקודת stake לא רשומה בפועל בבוט!")

except Exception as e:
    print("ERROR:", repr(e))

print("\n" + "=" * 70)
