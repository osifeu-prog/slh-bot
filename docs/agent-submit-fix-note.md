# Agent submission reward hardening

The public `/agent_submit` path is guarded before the legacy learning-path handler. New submissions are pending-only and do not issue Credits. Duplicate pending submissions are rejected. Approval uses the fixed 40-Credit policy through the guarded service.

This branch is intentionally not deployed by this change.
