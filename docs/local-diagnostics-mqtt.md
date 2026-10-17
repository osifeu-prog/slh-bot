# SLH Local Diagnostics — MQTT v2

## Purpose

/local_status can report a current, authenticated operational snapshot for the local PC without returning logs or secrets. Until a PC agent publishes the new snapshot format, the Telegram command must continue to report local Docker/Git diagnostics as NOT REPORTED.

## Transport and trust

- Topic: slh/device/<device_id>/heartbeat (or the configured MQTT_TOPIC_ROOT).
- Allowed device IDs for PC diagnostics: PC_Osif2 and PC_MAIN_001.
- The PC process and Railway listener share MQTT_DEVICE_HEARTBEAT_SECRET; the secret must be at least 32 characters for the reporter.
- HMAC-SHA256 v2 signs the complete canonical JSON payload excluding only sig_v2: sorted keys, compact separators, UTF-8, no NaN. The MAC input is <device_id>:<ts formatted to 3 decimals>: followed by that canonical JSON.
- ts must be within the listener's configured timestamp-skew window. The read model measures freshness from the signed source timestamp, not receipt time.
- Legacy presence-only heartbeats remain supported. A payload containing diagnostics must use the v2 signature; the legacy signature cannot authenticate diagnostic data.
- Only a strict schema is accepted. Unknown fields, logs, arbitrary text, tokens, and environment-variable values are not accepted or stored.

## Diagnostic fields

The v1 snapshot contains only:
- Docker daemon state, container count, running count, and bounded names of restarting containers.
- PostgreSQL readiness and Redis PONG check status.
- Git branch, abbreviated commit, whether the worktree is dirty, and a count of changed paths (not their names).
- Compose UTF-8 status, count of byte 0x97, and presence/absence of two required env files (never their contents).
- Status of slh-ton-mnh, slh-nifti, and slh-crazy-panel.

The reporter uses a fixed list of subprocess argument vectors with shell=False. It does not accept commands from Telegram, read log files, or print environment values. Its output contains only a success/failure type, never a traceback or secret.

## Deployment and activation

The backend receiver, freshness-aware read model, and Telegram rendering may be deployed independently. Actual Docker/Git data appears only after the supervised Windows agent runs tools/slh_local_diagnostics_reporter.py with its existing MQTT configuration and heartbeat secret, or an equivalent implementation of this protocol. Do not start a second competing agent. Do not add an unrestricted remote-command listener to solve activation.

Suggested supervisor configuration:
- Run the reporter in the same trusted local agent service, or as a managed child of that service.
- Keep MQTT_DEVICE_HEARTBEAT_SECRET in the service's protected environment.
- Use TLS for MQTT where supported by the existing broker configuration.
- Keep reporting interval between 15 and 300 seconds (default 30).

## Validation gates

1. CI verifies HMAC compatibility, tamper rejection, strict schema validation, shell-free subprocess calls, and status rendering.
2. The local process publishes a signed snapshot from an approved device ID.
3. /local_status displays the snapshot only while it is fresh (default 120 seconds); otherwise it must show NOT REPORTED.
4. This mechanism is telemetry only. It cannot run commands, modify files or containers, change balances, or open Exchange/BNB/TON gates.
