# SLH Security Model

Date:
2026-07-12

## Current Authentication

Telegram User ID

Current Gate:
SUPER_ADMIN

Legacy:
admin_utils.is_admin()


## Authorization Evolution

Phase 1:
Hardcoded Admin
Status:
Stable


Phase 2:
RBAC

Roles:
- owner
- admin
- teacher
- student
- agent
- system


Phase 3:
ABAC

Attributes:
- user_id
- role
- organization
- ownership
- permissions
- trust_level


## Command Security

System commands:
require admin/system permission

Core commands:
user access

Market:
financial permission layer

Agents:
agent permission layer


## Decision

Do NOT replace current security.

Build adapter layer:

Current:
is_admin()

Future:
permission_engine()


## Next Components

security/
    permissions.py
    roles.json
    policies.json

Future:
RBAC + ABAC + CRM integration
