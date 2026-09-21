# SLH OS MCP Control Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a persistent, authenticated SLH MCP service on Railway that exposes governed system, agent, mission, agent-economy, Railway, and GitHub capabilities while preserving the existing SLH authority and user financial state.

**Architecture:** `slh-mcp` is a separate Railway service in the `slh-bot` repository. It exposes MCP over Streamable HTTP, uses an explicit capability registry, resolves identity through `core/authority.py`, delegates agent execution to `core/runtime_service.py`, and stores only new agent-economy state in its dedicated namespace.

**Tech Stack:** Python 3.11; official MCP Python SDK v2.2.0; Starlette ASGI via `MCPServer.streamable_http_app()`; Uvicorn; existing SLH core; `unittest`; GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-21-slhos-mcp-control-plane-design.md`

## Global Constraints

- MCP is the protocol-facing access layer, not a second SLH state store or Telegram replacement.
- `core/authority.py` remains the final application-level permission source.
- `handlers/loader.py` is not introspected to generate MCP tools.
- No direct MCP writes to `state/db.json`.
- Existing user `credits`, `token_balance`, `staked`, staking positions, provenance records, and historical ledger rows are not modified or migrated.
- Agent economy lives only in `state/agent_economy.json` and its canonical service.
- Every agent monetary mutation is idempotent and auditable.
- Arbitrary shell execution is not an MCP capability.
- Production MCP runs over HTTPS with authentication and an explicit Host allowlist.
- Pin `mcp==2.2.0`; the official v2 stable release requires Python 3.10+. (https://pypi.org/project/mcp/)
- Use `MCPServer.streamable_http_app()` with the service lifespan entering `mcp.session_manager.run()`; deployed hostnames require explicit transport-security configuration. (https://py.sdk.modelcontextprotocol.io/run/asgi/)
- The repository package is named `slh_mcp`, not `mcp`, to avoid shadowing the third-party SDK package named `mcp`. Use the public SDK import `from mcp.server import MCPServer`.

## Review Focus

- Wrong principal/permission: denied before business code; covered by Task 2 and Task 3 authorization tests.