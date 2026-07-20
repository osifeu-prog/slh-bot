import os, sqlite3

def get_context():
    ctx = {
        "system": "SLH OS",
        "status": "online",
        "users": 0,
        "agents": 0,
        "tasks": 0,
        "last_error": None
    }
    if os.path.exists('slh_state.db'):
        try:
            conn = sqlite3.connect('slh_state.db')
            tables = [r[0] for r in conn.execute('SELECT name FROM sqlite_master WHERE type="table"').fetchall()]
            if 'users' in tables:
                ctx['users'] = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
            if 'agents' in tables:
                ctx['agents'] = conn.execute('SELECT COUNT(*) FROM agents').fetchone()[0]
            if 'tasks' in tables:
                ctx['tasks'] = conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
            conn.close()
        except: pass
    return ctx
