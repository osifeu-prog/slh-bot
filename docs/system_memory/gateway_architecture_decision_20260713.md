# SLH Gateway Architecture Decision

Date:
2026-07-13

Status:
ANALYSIS COMPLETE

Current finding:

SLH_GATEWAY.py exists and is the intended integration boundary.

Current flow:

External Service
        |
        v
SLH Gateway
        |
        v
Kernel
        |
        v
Modules


Required future evolution:

Gateway becomes protected microservice boundary.

Required layers:

1. Request validation
2. Authentication
3. Authorization
4. Audit logging
5. Sandbox routing
6. Deployment approval
7. Journal update


Important:

No external developer connects directly to:
- Telegram bot
- Core database
- Internal modules

All integrations must pass:

REQUEST
 ->
AUDIT
 ->
VALIDATION
 ->
GATEWAY
 ->
KERNEL
 ->
MODULE


Open issue:

Two kernel implementations detected:

SLH_KERNEL.py
core/kernel.py

Decision:
Do not modify until architecture migration plan exists.

Goal:

SLH Academy developers integrate through Gateway APIs only.
