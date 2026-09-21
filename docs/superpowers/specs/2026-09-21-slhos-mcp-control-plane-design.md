# SLH OS MCP Control Plane — Architecture Design

**Date:** 2026-09-21  
**Status:** Draft for user review before implementation planning  
**Scope:** SLH OS control, agents, economy, missions, Railway, GitHub, and MCP integration

## 1. Intent

SLH OS should expose one durable, governed control plane to humans, AI agents, and supported clients. MCP is the protocol-facing access layer to that control plane; it is not a second application state store, a replacement for Telegram handlers, or an alternate authority system.

Success means:
- A persistent Railway-hosted MCP service exists as 'slh-mcp'.
- MCP clients can discover explicit SLH capabilities through tools and resources.
- Every privileged operation passes the same canonical authority/policy gates used by SLH.
- Agent state and agent economics remain owned by SLH's canonical stores and services.
- Telegram remains a presentation/input layer; it is not the capability registry.
- Railway and GitHub operations are exposed through controlled capabilities rather than arbitrary shell access.
- All mutable economic actions are idempotent and auditable.
- No existing user financial balances, staking positions, token balances, provenance records, or ledger history are migrated or rewritten as part of MCP introduction.

## 2. Current System Anchors

The implementation must build on existing components rather than replace them:
- 'core/authority.py' is the canonical identity/role/permission gate.
- 'core/agent_registry.py' owns agent records and lifecycle operations.
- 'core/runtime_service.py' boots the canonical agent runtime and dispatches validated agent events.
- 'state/' remains the authoritative application state boundary.
- 'core/exec_policy.py' remains the policy boundary for arbitrary owner shell execution; MCP must not expose raw shell execution as a general-purpose tool.
- 'core/telegram_token_registry.py' is the non-secret bot-to-Railway ownership registry.
- 'core/railway_control.py' provides the existing Railway control-plane integration.
- 'handlers/loader.py' remains a Telegram registration layer and must not be introspected to auto-generate MCP tools.
- The main gateway currently combines Telegram polling and HTTP/Web routes; MCP must be a separate deployable service.

## 3. Target Architecture

```text
                     +----------------------+
                     |      SLH CORE        |
                     | authority            |
                     | agent registry       |
                     | runtime              |
                     | economy              |
                     | missions             |
                     | audit / policy       |
                     +----------+-----------+
                                |
                         +------+------+
                         | SLH MCP API |
                         | auth        |
                         | registry    |
                         | resources   |
                         | tools       |
                         +------+------+
                                |
             +------------------+------------------+
             |                  |                  |
         ChatGPT /         SLH Agents        Internal Clients
         MCP clients
```

Deployment topology:

```text
Railway project: endearing-amazement
  web       -> Telegram + Web gateway
  slh-mcp   -> standalone MCP HTTP service
```

The MCP service imports the same 'core/' modules from the repository. It does not duplicate the state model.

## 4. MCP Transport and Service Boundary

The MCP service will be an independent ASGI application using the current MCP Python SDK. The first production transport is Streamable HTTP over HTTPS.

Requirements:
- Dedicated service directory: 'mcp/'.
- Dedicated entrypoint: 'mcp/server.py'.
- Dedicated authentication module: 'mcp/auth.py'.
- Dedicated explicit capability registry: 'mcp/registry.py'.
- Tool/resource modules under 'mcp/tools/' and 'mcp/resources/'.
- No production dependency on packages installed ad hoc into a running container.
- MCP health endpoint/diagnostic capability must not expose secrets.
- The public endpoint must be HTTPS and protected by authentication.
- Deployment must be independently restartable from the Telegram service.

## 5. Capability Registry

Capabilities are declared explicitly. MCP discovery must not crawl Telegram handlers.

Initial read capabilities:
- 'system.health'
- 'system.snapshot'
- 'agents.list'
- 'agents.get'
- 'agents.runtime_status'
- 'missions.list'
- 'economy.agent_balance'
- 'economy.agent_ledger'
- 'railway.projects'
- 'railway.services'
- 'railway.deployments'
- 'github.repositories'
- 'github.ci_status'

Initial governed mutation capabilities:
- 'agents.create'
- 'agents.update'
- 'missions.create'
- 'missions.assign'
- 'missions.complete'
- 'economy.propose_transfer'
- 'economy.commit_transfer'
- 'railway.deploy'
- future token-rotation operation

Each capability definition contains:
- stable name
- description
- typed input schema
- typed output schema
- required permission
- mutation/read classification
- audit event name
- idempotency requirement where applicable
- implementation function
- redaction policy

Arbitrary command execution is explicitly outside the initial MCP surface.

## 6. Resources

MCP resources provide system context without requiring a client to know internal file layouts.

Initial resources:
- 'slh://system'
- 'slh://agents'
- 'slh://agent/{agent_id}'
- 'slh://agent/{agent_id}/economy'
- 'slh://missions'
- 'slh://railway'
- 'slh://github'

Resources are read-only projections. They must not expose secrets, raw tokens, private credentials, or unrestricted state internals.

## 7. Authority and Identity

MCP requests must resolve an authenticated principal to an SLH identity.

```text
MCP credential
   -> principal
   -> SLH identity / role
   -> capability permission
   -> operation-specific policy
   -> canonical service
   -> audit event
```

Rules:
1. 'core/authority.py' remains the final application-level permission source.
2. MCP must not maintain a second OWNER/ADMIN list.
3. Tool code must not mutate permissions directly.
4. Privileged operations must have explicit capability gates.
5. A read capability must not silently perform a write.
6. Any failed authorization attempt should be auditable without storing credentials.

## 8. Agent Model

MCP exposes agents as durable SLH entities, not as Telegram users.

Each agent may have:
- agent id
- owner
- role
- runtime class
- state
- mission
- capabilities
- budget/account
- ledger reference
- audit trail

Agent execution continues through 'core/runtime_service.py'. MCP provides a controlled front door to that execution path; it does not instantiate arbitrary Python classes.

## 9. Agent Economy

The agent economy is a new first-class layer and is explicitly separate from current user financial balances.

Target model:

```text
Agent Wallet
  + Agent Budget
  + Agent Ledger
  + Economic Policy
  + Mission Rewards
  + Idempotency
```

A governed economic operation follows:

```text
agent action
  -> economic proposal
  -> authority/policy
  -> canonical ledger mutation
  -> resulting agent balance
  -> audit event
```

Hard requirements:
- no direct MCP writes to 'state/db.json'
- no direct manipulation of existing user 'credits', 'token_balance', 'staked', or staking positions
- no migration of existing financial state as part of MCP rollout
- every monetary mutation is idempotent
- every monetary mutation records source, actor, target, amount, and stable operation id
- rejected operations do not partially mutate balances

The implementation may reuse existing atomic/idempotency patterns, but Agent Economy storage remains separate. Existing user ledger functions that mutate `state/db.json` are not used for Agent Economy.

## 10. Mission Economy Flow

The intended autonomous loop is:

```text
Mission
  -> Agent accepts
  -> Agent executes
  -> Result submitted
  -> Verification/policy
  -> Reward decision
  -> Agent ledger entry
  -> Agent balance update
  -> Next mission/action
```

Reward decisions must be deterministic or explicitly policy-driven and auditable. MCP itself is not the reward authority.

## 11. Control Plane Bridge

The `web` service owns live SLH user, agent, and mission state. `slh-mcp` communicates with it over authenticated HTTPS using `SLH_MCP_BRIDGE_TOKEN` and a principal identifier. Bridge routes are internal-only and must apply canonical `core.authority` checks before returning or mutating state.

Initial bridge routes include system summary, authorization, runtime status, agent list/get/execute, and mission list/get/complete. The bridge returns redacted projections only.

## 12. Railway Integration

The MCP Railway capabilities may wrap 'core/railway_control.py' and/or a dedicated safe adapter.

The MCP surface must:
- expose project/service/deployment identity
- expose deployment status
- allow controlled deployment only to authorized targets
- return deployment id/status without secrets
- verify terminal 'SUCCESS' before representing a deployment as completed
- keep destructive operations out of the initial capability set

Existing Railway token rotation must remain terminal-only unless a future explicit, separately authorized capability is designed.

## 13. GitHub Integration

GitHub capabilities are intended for repository/status visibility and governed development workflows.

Initial MCP GitHub operations are read-only. Future write operations may be introduced for:
- branch creation
- file changes
- PR creation
- CI verification
- merge

Every future write capability must preserve the existing GitHub permission model and require an explicit policy gate.

## 14. Authentication and Security

Production MCP must:
- run only over HTTPS
- use authenticated requests
- avoid embedding static secrets in source
- never return raw bot tokens, Railway tokens, GitHub tokens, database URLs, or other credentials
- log metadata/audit events without logging credential values
- enforce allowed Host/origin configuration appropriate to the deployed endpoint
- support shared request-state requirements when scaled to more than one worker

Security incidents already identified in public SLH control surfaces are out of scope for this MVP design but should be tracked separately as a remediation workstream.

## 15. Observability

MCP should emit structured events for:
- authentication success/failure
- capability discovery
- tool invocation
- authorization result
- mutation result
- idempotency hit
- downstream failure

Metrics should distinguish:
- read requests
- mutation requests
- authorization failures
- downstream failures
- latency
- deployment operations
- economy operation outcomes

No secret values are included in logs.

## 16. Testing Strategy

Before production exposure:
1. Unit tests for capability schemas and permission gates.
2. Unit tests for redaction and error handling.
3. Read-only integration tests against a non-financial or isolated fixture state.
4. Agent lifecycle tests through MCP -> authority -> runtime.
5. Economy tests covering duplicate operation ids and concurrent submissions.
6. Railway read/status tests.
7. MCP protocol compatibility tests using an MCP inspector/client.
8. Deployment smoke test against the live HTTPS endpoint.
9. Regression check confirming existing Telegram economy/staking data is unchanged.

## 17. Rollout

Phase A — Foundation:
- create 'mcp/'
- add MCP runtime dependency to a dedicated service dependency set
- implement auth, registry, health, and read-only system/agent resources

Phase B — Agent control:
- expose agent discovery/runtime operations
- connect to canonical runtime service

Phase C — Agent economy:
- add isolated agent wallet/budget/ledger primitives
- add mission reward integration
- prove idempotency and audit

Phase D — Infrastructure:
- Railway/GitHub capabilities
- deployment status verification
- controlled deploy operation

Phase E — External client integration:
- connect MCP clients
- validate capability discovery
- validate authenticated tool execution

No phase alters historical user financial state.

## 18. Acceptance Criteria

The design is considered implemented only when all are true:
- A persistent Railway 'slh-mcp' service exists and is independently deployable.
- An authenticated MCP client can discover SLH resources and initial capabilities.
- 'agents.list' and 'agents.get' resolve through canonical SLH state.
- A privileged mutation reaches 'core/authority.py' before execution.
- Agent execution reaches 'core/runtime_service.py'.
- Agent economic mutations are isolated from current user balances.
- Duplicate economic operation ids do not double-spend or double-reward.
- Railway deployment status is observable and terminal success is verified.
- Secrets are absent from MCP outputs and logs.
- CI and integration tests are green.
- Existing Telegram bot behavior remains green.
- Existing financial-state regression checks remain green.

## 19. Non-Goals

This project does not:
- auto-generate MCP tools from Telegram handlers
- replace Telegram handlers
- replace the current Control Plane
- create a second financial source of truth
- rewrite existing user accounting
- expose arbitrary shell execution through MCP
- rotate secrets automatically as part of initial rollout
- require ESP/device work for MCP Alpha readiness

## 20. Open Implementation Decisions

These are implementation details to resolve during the plan, not blockers to the architecture:
- exact auth provider/mechanism for the first external MCP client
- exact separation between agent ledger and any reusable existing ledger primitives
- exact Railway service root/build configuration
- MCP client/inspector used for production smoke testing
- scaling/worker count for the initial Railway service