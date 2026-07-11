# SLH State Architecture Map

Date:
2026-07-12

## Source Of Truth

Primary:
state/db.json

Managed by:
state_manager.py


## State Domains

### Users / CRM
Location:
state/db.json
Key:
users


### Learning
Location:
state/db.json
Keys:
students
courses


### Agents
Location:
state/db.json
Key:
agents


### Tasks
Location:
state/db.json
Key:
tasks


### Governance
Location:
state/db.json
Keys:
votes
admins


### Memory

Current:
state/db.json memory key

Legacy:
memory.db

New:
state/system_memory.json

Decision:
system_memory.json = system snapshot layer


### Audit

Current:
memory.db audit table
state/audit_logs/


## Future Control Plane

RBAC
ABAC
CRM
Memory Kernel
Health Checks
Automatic Checkpoints


## Current Status

Runtime:
ONLINE

Railway:
ONLINE

Telegram:
ONLINE

Architecture Phase:
Memory Kernel Preparation
