SLH OS DEVELOPER QUICK START

Architecture:
- Telegram Bot
- Python handlers
- JSON state layer
- RBAC security layer
- Governance layer

Important files:

state/
 db.json
 governance.json

handlers/
 loader.py
 governance_handler.py

security/
 permissions.py

core/
 profile_manager.py
 identity.py


Current source of truth:
state/db.json


Developer rules:

1. Never edit state manually.
2. Always create backup before migration.
3. Always run syntax audit.
4. Never bypass RBAC.
5. All new modules register through loader.py.


Current status:

Governance foundation:
READY

RBAC:
READY

Next:
- Connect governance commands
- Migrate votes
- Add developer docs
- Production verification

