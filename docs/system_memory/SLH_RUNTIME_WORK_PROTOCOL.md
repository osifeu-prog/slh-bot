# SLH Runtime Work Protocol v1.0

## 1. Environment Separation
- **TERMUX DEVELOPMENT ENVIRONMENT** (`~/slh_clean`) – code editing, git, scripts, snapshots.
- **BOT EXECUTION ENVIRONMENT** (via `/exec` on Railway) – runtime checks, state verification, logs.

## 2. No Command Without Environment
Every command must be tagged:
- `📍 TERMUX` – for local dev actions.
- `📍 EXEC / BOT RUNTIME` – for runtime checks.

## 3. Source of Truth
Before any state change, ask: *Who owns this data? Where is it stored? Who writes to it?*

## 4. Change Protocol
Backup → Edit → Syntax Check → Test → Commit → Push → Deploy Verification

## 5. Synthetic User Testing
- Use `test_user_NNN` with `TEST_MODE: true`.
- Phase 1: 10 users → Phase 2: 50 → Phase 3: 100.

## 6. Keyboard Layout Recovery
Any input that looks like reversed Hebrew (e.g., `nv gus`) must be normalized before routing to ASK.

## 7. ASK Router Classification
Incoming messages must be classified as: QUESTION, COMMAND, TASK_CREATION, DIAGNOSTIC, GOVERNANCE.
