from pathlib import Path

p = Path(".\slh_dna_scan.py")
s = p.read_text(encoding="utf-8")

marker = 'EXCLUDED_FILES = {\n'
insert = '''ENTRYPOINT_FILENAMES = {
    "SLH_MAIN.py",
    "SLH_KERNEL.py",
    "SLH_GATEWAY.py",
    "SLH_BOT_ADAPTER.py",
    "bot_stable.py",
    "bot_gateway.py",
    "slh.py",
    "webapp.py",
}

'''

if "ENTRYPOINT_FILENAMES =" not in s:
    s = s.replace(marker, insert + marker, 1)

p.write_text(s, encoding="utf-8")
print("ENTRYPOINT_FILENAMES restored.")
