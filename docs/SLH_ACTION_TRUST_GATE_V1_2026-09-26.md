# SLH Action Trust Gate v1 — 2026-09-26

The Action Trust Gate is the second half of the SLH Trust architecture.

The Trust Layer asks: "What risk signals are present in this input?"

The Action Trust Gate asks: "Given authentication, authorization, confirmation and
risk signals, may an execution path proceed?"

The AI cannot authorize execution. A model response is evidence/input only.

Sensitive actions include wallet sends, wallet binding, payments, payouts,
exchange orders, external tools, deployments and secret access.

Policy:
- missing authentication -> BLOCK
- missing authorization -> BLOCK
- high trust risk -> BLOCK
- sensitive action from untrusted external content -> REVIEW
- money/sensitive action without explicit user confirmation -> REVIEW
- only ALLOW when all required gates are satisfied
- this module never executes an action
