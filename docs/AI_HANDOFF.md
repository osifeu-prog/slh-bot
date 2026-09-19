# AI Handoff Contract

This file is the short entry point for every AI session working on SLH OS.

## Before work

Read:
- `docs/SLH_CONTROL_PLANE.md`
- `docs/CURRENT_STATE.md`
- `docs/ACTIVE_WORK.md`
- `docs/INCIDENTS.md`
- subsystem-specific documentation when changing that subsystem.

## During work

Prefer read-only inspection first. Use the existing GitHub/Railway integrations and canonical state paths. Do not create a second source of truth merely to make a task easier.

## After work

Record:
- change made
- commit/PR/deployment
- verification performed
- remaining gap
- explicit no-touch constraints
- next action

## Parallel AI rule

Parallel sessions may work on independent tracks, but they must converge through GitHub and the canonical documentation. A chat transcript is not a source of truth.

## Public-release rule

Internal control-plane, forensic, infrastructure, credentials, and private operational data must not be published. Public release artifacts are generated from verified product state only.
