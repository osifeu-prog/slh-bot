from pathlib import Path

p = Path("core/ask_guard.py")
s = p.read_text(encoding="utf-8")

if "def guard(" not in s:
    s += '''

def guard(text):
    return allow_request(text)
'''

    p.write_text(s, encoding="utf-8")
    print("ASK guard compatibility added")
else:
    print("guard already exists")
