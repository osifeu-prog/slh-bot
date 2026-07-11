# SLH Phase 2 Roadmap

Date:
2026-07-12

Current Phase:
Foundation Complete

## Completed

- Runtime stability
- State architecture
- Memory checkpoint foundation
- Security adapter layer
- RBAC/ABAC design

---

# Phase 2: Autonomous Control Plane

## 1. Permission Engine

Goal:
Replace direct permission checks with policy evaluation.

Components:

security/
- permissions.py
- roles.json
- policies.json
- engine.py

---

## 2. Health Kernel

Goal:
Automatic system health reporting.

Checks:

- Telegram connection
- Railway status
- Database status
- Memory checkpoint status
- Security status

---

## 3. CRM State Layer

Goal:

Unified users:

- students
- teachers
- agents
- admins

Source:
state/db.json

---

## 4. Task Queue

Goal:

Manage:

- system tasks
- student tasks
- agent tasks
- maintenance tasks

---

## Rule

No runtime replacement until validation.

Current production path remains stable.
