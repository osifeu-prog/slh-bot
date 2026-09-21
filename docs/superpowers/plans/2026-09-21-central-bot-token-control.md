# Central Multi-Bot Token Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `@Me_ad_main_bot` a safe multi-bot control surface that can identify token ownership, show target Railway services, and drive terminal-only token rotation without ever accepting secrets through Telegram.

**Architecture:** A small non-secret registry maps each verified Telegram bot identity to its Railway project/environment/service IDs and exact variable name. The Telegram handler exposes read-only inventory and rotation instructions; the existing shell rotation script accepts only a bot alias and reads the secret interactively from the operator terminal. No token is stored in Git, `state/`, logs, or Telegram messages.

**Tech Stack:** Python, pytest, Bash, Railway CLI, existing SLH modular handler loader.

**Spec:** `docs/superpowers/plans/2026-09-21-central-bot-token-control.md`

## Global Constraints

- Never accept Telegram bot tokens through Telegram messages.
- Never persist raw Telegram bot tokens in Git, `state/`, config files, or logs.
- Do not mutate Credits, SLH balances, staking, Ledger, or the financial DB.
- Only register bot/service mappings whose ownership is verified from current runtime/source evidence.
- A single Telegram bot may target more than one Railway service when both services consume the same token.
- Token rotation must validate against Telegram `getMe` before changing Railway variables.

## Review Focus

- Unknown bot alias must fail closed instead of falling back to a default service/token.
- `TON_MNH_bot` must update both the webhook and worker services because both read `BOT_TOKEN`.
- `@SLH_AIR_bot` must use `TELEGRAM_TOKEN`, not the generic `BOT_TOKEN`.
- `@SLH_Claude_bot` must use `SLH_CLAUDE_BOT_TOKEN`.
- A token must never appear in the generated Telegram response or registry.

### Task 1: Non-secret registry

**Files:**
- Create: `core/telegram_token_registry.py`
- Test: `tests/test_telegram_token_registry.py`

**Interfaces:**
- Produces `get_bot(alias: str) -> dict`
- Produces `list_bots() -> list[dict]`
- Produces `targets_for(alias: str) -> list[dict]`

- [ ] Write failing tests for known aliases, exact variable names, multi-service TON target, and unknown-alias rejection.
- [ ] Run the focused pytest and verify the expected import/behavior failure.
- [ ] Implement the minimal registry with only verified mappings.
- [ ] Run the focused pytest and then the full test suite.
- [ ] Commit the registry and tests.

### Task 2: Central handler surface

**Files:**
- Modify: `refresh_token_handler.py`
- Test: `tests/test_telegram_token_registry.py`

**Interfaces:**
- `/bots` lists safe bot identity, project/service target, and variable name.
- `/refreshtoken <alias>` returns terminal-only rotation instructions and exact target scope.
- No handler path accepts a token value.

- [ ] Add failing tests for unknown alias and safe rotation message content.
- [ ] Run focused tests and verify failure.
- [ ] Update handler to consume the registry and fix the current script path resolution.
- [ ] Run focused and full tests.

### Task 3: Multi-service terminal rotation

**Files:**
- Modify: `rotate_telegram_token.sh`

- [ ] Add alias argument validation against the same non-secret mapping.
- [ ] Read the token from hidden terminal input only.
- [ ] Validate identity with Telegram `getMe`.
- [ ] Set the mapped variable on every mapped Railway service using Railway CLI project/service/environment flags and stdin.
- [ ] Redeploy each affected service explicitly.
- [ ] Ensure no token value is echoed or logged.

### Task 4: Verification

- [ ] Verify the branch contains no raw Telegram token strings.
- [ ] Verify the central handler is still loaded by `handlers/loader.py`.
- [ ] Verify registry entries match current Railway topology for AIR, Claude, and V2.
- [ ] Leave financial state untouched.
