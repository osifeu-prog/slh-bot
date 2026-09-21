# SLH OS — Operator Guide

**Updated:** 2026-09-21  
**Canonical repository:** `osifeu-prog/slh-bot`  
**Canonical branch:** `main`

## 1. Operating model

SLH is operated through three layers:

1. **Telegram Control Plane** — fastest interactive operations.
2. **SLH MCP** — machine-readable, authenticated capability interface for AI agents and external MCP clients.
3. **Canonical Core** — authority, agent registry/runtime, mission lifecycle, economics, audit, Railway and GitHub adapters.

Telegram handlers are a UI layer. They are not the MCP registry and must not become a second source of truth.

## 2. Daily Telegram operations

### Health

`/health`
- Basic health summary.

`/doctor`
- Full operational diagnostic.

`/status`
- Short gateway/Railway status.

`/logs`
- Recent deployment/log surface.

`/megadiag`
- Runtime and disk diagnostics.

### Control Plane

`/admin`
- Paginated Super Admin Control Plane catalog.

`/admin_status`
- Refresh Control Plane status.

`/unified_map`
- Canonical architecture/federation map.

`/services`
- Registered services.

`/project`
- Project information.

### Agents and Missions

`/agents`
- Agent registry.

`/agent`
- Agent control surface.

`/task`
- Task management.

`/mission`
- Mission control.

`/progress`
- Progress/read model.

`/monitor`
- Monitoring.

### Development / Railway

`/e railway`
- Safe Railway project inspection.

`/e railway inspect <project_id>`
- Inspect a project.

`/e railway up [full_sha]`
- Guarded deployment through the existing Railway control path.

`/e <command>`
- OWNER execution gateway. Python snippets beginning with `import` / `from` are normalized into Python execution before the existing policy gates run.

`/exec <command>`
- Gated execution path.

`/execr`
- Approval-request surface.

`/autoexec`
- Gated batch execution.

### Economy

`/me`
- User account read model.

`/wallet`
- User wallet surface.

`/positions`
- Staking positions.

`/transfer <uid> <amount>`
- User Credits P2P transfer.

`/claim`
- Deposit/claim path.

`/ton`
- TON deposit status.

User financial state remains behind the canonical economy/staking gates.

## 3. MCP client operating model

Production MCP endpoint contract:

`https://<slh-mcp-domain>/mcp`

Health:

`https://<slh-mcp-domain>/health`

Authentication:

- Bearer credential configured as `SLH_MCP_BEARER_TOKEN`.
- Principal identity configured as `SLH_MCP_PRINCIPAL_ID`.
- Authorization resolves through `core/authority.py`.
- MCP does not maintain its own OWNER/ADMIN list.

### MCP resources

```
slh://system
slh://agents
slh://agent/{agent_id}
slh://agent/{agent_id}/economy
slh://missions
slh://economy
slh://railway
slh://github
```

### MCP capabilities currently defined

Read:

```
system.health
system.snapshot

agents.list
agents.get
agents.runtime_status

missions.list

economy.agent_balance
economy.agent_ledger
economy.ledger
economy.propose_transfer

bots.registry
bots.federation

railway.projects
railway.services
railway.deployments

github.repositories
github.ci_status
```

Governed mutations:

```
agents.execute
agents.create
agents.update

missions.create
missions.assign
missions.complete

economy.commit_transfer

railway.deploy
```

Raw shell execution is intentionally not an MCP capability.

## 4. Agent workflow

The intended autonomous workflow is:

```
Discover
  ↓
Read system/agent/mission state
  ↓
Select capability
  ↓
Authority check
  ↓
Canonical runtime/service
  ↓
Audit
  ↓
Result
```

For missions:

```
Mission assigned
  ↓
Agent runtime executes
  ↓
Evidence verified
  ↓
Mission lifecycle commits
  ↓
Agent reward is attempted
  ↓
Agent economy ledger
```

A mission reward does not write to the existing user Credits ledger.

## 5. Agent Economy

Agent money is a separate accounting domain:

```
state/agent_economy.json

accounts
ledger
operations
```

The domain contains an internal `AGENT_TREASURY`.

Rules:

- New revenue requires evidence and a unique `operation_id`.
- Treasury funding is a real debit from the agent treasury; it is not a hidden mint.
- Agent transfers are atomic.
- Repeating an already committed `operation_id` is idempotent.
- Reusing an operation id with different parameters is rejected.
- Insufficient balances are rejected before mutation.
- User `credits`, `token_balance`, `staked`, staking positions, provenance and historical user ledger records are outside this state domain.

### Agent economic lifecycle

```
Verified revenue
  ↓
AGENT_TREASURY
  ↓
fund agent
  ↓
agent executes missions/work
  ↓
agent-to-agent transfer
  ↓
future verified revenue
```

The current code intentionally does not auto-convert arbitrary external assets into agent-economy units.

## 6. Federation operations

The bot registry is the canonical ownership map:

`bots.registry`

The federation read model cross-checks registered targets against Railway:

`bots.federation`

Interpretation:

- `READY` — registered target has a SUCCESS deployment.
- `ATTENTION` — target exists but latest deployment is not terminal SUCCESS.
- `PROJECT_MISSING` — registered Railway project was not found.
- `SERVICE_OR_DEPLOYMENT_UNKNOWN` — project exists but target service/deployment could not be resolved.

The federation layer is read-only.

## 7. Production safety rules

Never paste Telegram, Railway, GitHub, database or MCP credentials into chat.

Never enable a second Telegram service unless its token is proven to belong to a distinct bot.

Never expose `state/db.json` as an MCP write surface.

Never redeploy a service from a deployment that is still `NEEDS_APPROVAL`.

Do not scale the file-backed Agent Economy horizontally until shared-state locking or transactional storage is introduced.

Before any economy mutation, preserve a financial regression snapshot.

## 8. Current rollout state

### Completed

- MCP SDK/runtime foundation.
- Streamable HTTP service implementation.
- Authentication and principal bridge.
- Canonical authority enforcement.
- Explicit capability registry.
- Agent Registry/Runtime integration.
- Mission read/completion integration.
- Isolated Agent Economy.
- Agent economy idempotency.
- Canonical economic read model.
- Bot registry/federation read model.
- Railway/GitHub read adapters.
- CI + full regression + security checks.

### Still required for full external MCP operation

- Confirm that a dedicated Railway service named `slh-mcp` exists.
- Configure its MCP bearer secret and principal.
- Configure its allowed Host/origin values.
- Expose its HTTPS domain.
- Connect an external MCP client/Inspector.
- Run the live protocol smoke test.
- Only then treat MCP as externally reachable infrastructure.

The presence of `slh_mcp/` in the `web` deployment does not by itself prove that an independent MCP service is externally reachable.

## 9. Recommended operating rhythm

Use Telegram for fast interactive control and incident response.

Use MCP for structured agent operations, discovery and future autonomous workflows.

Use GitHub as the source for code and review.

Use Railway as the production runtime and deployment authority.

Use the Control Plane/read models as the cross-system observability layer.

The intended long-term loop is:

```
Human / AI Agent
      ↓
MCP / Telegram
      ↓
Control Plane
      ↓
Authority
      ↓
Canonical service
      ↓
Audit + Read Model
      ↓
Next action
```
