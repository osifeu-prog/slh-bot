import os, re
from pathlib import Path

EXCLUDE_PARTS = {
    '.git', '.venv', 'venv', '__pycache__', '_archive', 'archive',
    'p0_backups', '_release_backup', '_slh_audit', 'SLH_DASHBOARD_RECOVERY_BACKUP'
}

PATTERNS = [
    re.compile(r"db\.get\(\s*[\"']agents[\"']\s*,\s*\{\s*\}\)"),
    re.compile(r"db\.get\(\s*[\"']agents[\"']\s*\)"),
]

for pyfile in Path('.').rglob('*.py'):
    # skip if any part is in exclude
    if any(part in EXCLUDE_PARTS for part in pyfile.parts):
        continue

    try:
        # Read with utf-8-sig to strip BOM if present
        text = pyfile.read_text(encoding='utf-8-sig')
    except Exception:
        continue

    new_text = text
    changed = False

    for pat in PATTERNS:
        new_text, n = pat.subn('state_manager.get_agents()', new_text)
        if n:
            changed = True

    if changed:
        # ensure import state_manager exists
        if 'import state_manager' not in new_text:
            new_text = 'import state_manager\n' + new_text
        # write back without BOM
        pyfile.write_text(new_text, encoding='utf-8')
        print(f'UPDATED: {pyfile}')
