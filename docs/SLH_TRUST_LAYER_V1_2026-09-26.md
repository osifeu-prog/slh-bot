# SLH Trust Layer v1 — 2026-09-26

## Purpose

Protect users and agents from credential leakage, prompt injection and unsafe
external instructions without making the LLM the authority for money or tools.

## Boundary

The Trust Layer is advisory/classification infrastructure.

- It never receives a seed phrase as a required input.
- It never stores submitted content.
- It never authorizes a wallet transaction.
- It never changes balances.
- It never grants tool permissions.
- Money movement still requires its own authenticated execution gate and user confirmation.

## Risk model

LOW: ordinary content; allow.

MEDIUM: prompt-injection or external-control indicators; analyze as untrusted
content and do not treat embedded instructions as system/developer authority.

HIGH: credentials, secret material, or direct credential-targeting language;
block sensitive processing and instruct the user not to share secrets.

## Product path

Expose the same classification contract through an authenticated API and
meter usage for third-party bots, Mini Apps and agent platforms.

Suggested commercial meters:

- requests scanned
- high-risk events prevented
- protected tool actions
- protected wallet transaction simulations
- team seats
- retention/audit features

Never sell or expose the raw secret content that triggered a detection.

## Integration state

The canonical ask guard currently protects duplicate requests. This module is
intentionally additive until the existing guard can be updated through the
repository's normal write path and covered by regression tests.
