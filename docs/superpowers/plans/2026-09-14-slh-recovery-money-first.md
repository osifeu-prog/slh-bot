# SLH Recovery — Money First Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the SLH web/bot runtime and harden the money paths without creating new sources of truth or exposing ESP hardware access.

**Architecture:** Keep `state/db.json` as the canonical application/economy state, Railway `web` as the primary runtime, and Telegram/Mini App as clients. ESP remains an owner-only hardware boundary and is upgraded through an explicit, versioned protocol rather than becoming an unverified parallel ledger.

**Tech Stack:** Python 3.11, Flask, pyTelegramBotAPI, JSON state with atomic updates, Railway, GitHub Actions, ESP32 MQTT/PubSubClient.

**Spec:** `docs/SLH_TEAM_HANDOFF_2026-09-14.md`

## Global Constraints

- Money paths must be authenticated, authorized, atomic, idempotent, and auditable.
- `state/db.json` remains the canonical economy state.
- No manual production DB/state edits.
- No secrets or credentials in source, commits, tickets, or screenshots.
- ESP hardware access remains owner-only.
- Do not open Alpha solely because Post-Alpha hardening is incomplete.
- Do not create duplicate Telegram polling instances.

---

## Task 1 — Freeze and classify current runtime

- [ ] Record current `main` SHA and active Railway production deployment.
- [ ] Record active Railway services without reading secret values.
- [ ] Verify the primary bot process and `RUN_BOT` behavior.
- [ ] Verify website, `/health`, Mini App and `/api/v1/me` from runtime evidence.
- [ ] Preserve this evidence before changing code.

## Task 2 — Money-path verification

- [ ] Inventory Stars purchase → credit path.
- [ ] Inventory internal SLH distribution path.
- [ ] Inventory P2P transfer path.
- [ ] Inventory staking/reward settlement path.
- [ ] Inventory TON/BNB deposit/claim paths separately from internal SLH.
- [ ] Inventory withdrawal/on-chain settlement claims.
- [ ] For each path verify auth, authorization, atomicity, idempotency, ledger, retries and UI.
- [ ] Add only regression tests required to prove missing safety properties.

## Task 3 — Existing reward hardening

- [ ] Review open agent-submission reward PR #70 against current economy policy.
- [ ] Require fresh CI evidence before merge.
- [ ] If accepted, merge only after review and verification; do not deploy blindly.

## Task 4 — Website/runtime recovery

- [ ] Keep private `slh-bot` runtime and public `SLH.co.il` website repository distinct.
- [ ] Determine intended canonical public-site deployment before changing routing.
- [ ] Fix broken/garbled website copy in its own repository only when write access and exact scope are confirmed.
- [ ] Do not expose the internal dashboard as the public homepage.
- [ ] Ensure Mini App links back to the canonical public site where appropriate.

## Task 5 — Telegram bot recovery

- [ ] Map every intended bot to one runtime/token without exposing values.
- [ ] Confirm duplicate-token protection.
- [ ] Investigate group message delivery with evidence before changing handlers.
- [ ] Consolidate user-facing help while preserving owner/admin control boundaries.

## Task 6 — Mini App UX

- [ ] Consolidate navigation into a maximum of five primary user areas.
- [ ] Keep wallet, payments and staking visible and understandable.
- [ ] Keep audit/deploy/authority internals out of normal user navigation.
- [ ] Add tests for authenticated self-scoping and money action error states.

## Task 7 — ESP ledger-layer preparation

- [ ] Reconcile duplicate device identities without deleting history.
- [ ] Confirm server command topics use registry/config rather than hard-coded assumptions.
- [ ] Define a bounded protocol version and wallet-sync payload.
- [ ] Require explicit device ACK before treating a sync as applied.
- [ ] Ensure the device cannot mint, alter canonical balances, or become an unverified second authority.
- [ ] Keep all device operations owner-only during this phase.

## Task 8 — Final Alpha gate

- [ ] Economy sanity passes.
- [ ] Alpha control-plane state is correct.
- [ ] Smoke test passes on the deployed runtime.
- [ ] Only explicit Alpha promises are used to determine blockers.
- [ ] Produce a final 🟢/🟠/🔴 matrix with evidence.

## Verification rule

No task is marked complete based on code inspection alone when runtime behavior is claimed. Run the command/test that proves the claim and record the result before declaring success.
