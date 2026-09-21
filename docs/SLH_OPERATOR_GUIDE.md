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
agents.consistency

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

### Agent state consistency

`agents.consistency` is a read-only diagnostic. It treats `state/db.json` as the canonical live source and `state/agents.json` as the derived snapshot. It reports count/state drift and adds display-only numbering per owner; internal agent IDs are never rewritten.

### Current MCP deployment distinction

The presence of `slh_mcp/` in the `web` deployment does not prove that a standalone `slh-mcp` HTTPS endpoint exists. A dedicated Railway service must be verified separately before external MCP connectivity is declared live.
