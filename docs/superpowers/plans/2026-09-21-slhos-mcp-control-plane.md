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
- The repository package is named `slh_mcp`, not `mcp`, to avoid shadowing the third-party SDK package named `mcp`.

## Review Focus

- Wrong principal/permission: denied before business code; covered by Task 2 and Task 3 authorization tests.
- Read/write confusion: read resources leave all state unchanged; covered by Task 3.
- Duplicate economic operation: one operation id produces one committed ledger effect; covered by Task 5.
- Malformed economic input: empty/negative/oversized inputs fail with no partial write; covered by Task 5.
- Secret leakage: auth headers and credential-like values never appear in responses or audit data; covered by Task 2 and Task 8.

---

### Task 1: Create the isolated MCP service skeleton

**Files:**
- Create: `slh_mcp/__init__.py`
- Create: `slh_mcp/server.py`
- Create: `slh_mcp/auth.py`
- Create: `slh_mcp/registry.py`
- Create: `slh_mcp/requirements.txt`
- Create: `slh_mcp/Dockerfile`
- Create: `tests/test_mcp_bootstrap.py`

**Interfaces:**
- `build_mcp_app() -> Starlette`
- `principal_from_request(request) -> Principal | None`
- `register_capabilities(server) -> None`

- [ ] **Step 1: Write the failing bootstrap test**

```python
from unittest import TestCase
from slh_mcp.server import build_mcp_app

class MCPBootstrapTests(TestCase):
    def test_builds_asgi_app(self):
        app = build_mcp_app()
        self.assertTrue(hasattr(app, "routes"))
```

- [ ] **Step 2: Run it**

Run: `python -m unittest tests.test_mcp_bootstrap -v`
Expected: FAIL because `slh_mcp.server` does not yet exist.

- [ ] **Step 3: Pin dependencies**

`slh_mcp/requirements.txt`:

```text
mcp==2.2.0
uvicorn==0.35.0
```

- [ ] **Step 4: Implement the server factory**

```python
import contextlib
import os

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

mcp = MCPServer("SLH OS")

@contextlib.asynccontextmanager
async def lifespan(_app):
    async with mcp.session_manager.run():
        yield

def build_mcp_app():
    hosts = [x.strip() for x in os.getenv("SLH_MCP_ALLOWED_HOSTS", "").split(",") if x.strip()]
    origins = [x.strip() for x in os.getenv("SLH_MCP_ALLOWED_ORIGINS", "").split(",") if x.strip()]
    return mcp.streamable_http_app(
        transport_security=TransportSecuritySettings(
            allowed_hosts=hosts or ["localhost:*", "127.0.0.1:*"]
            , allowed_origins=origins
        )
    )

app = build_mcp_app()
```

- [ ] **Step 5: Add the service Dockerfile**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY slh_mcp/requirements.txt /tmp/slh-mcp-requirements.txt
RUN pip install --no-cache-dir -r /tmp/slh-mcp-requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "exec uvicorn slh_mcp.server:app --host 0.0.0.0 --port ${PORT:-8080}"]
```

Configure Railway to build from repository root with Dockerfile path `slh_mcp/Dockerfile` so shared `core/` remains importable.

- [ ] **Step 6: Run the test after installing `slh_mcp/requirements.txt`**

Run: `python -m unittest tests.test_mcp_bootstrap -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add slh_mcp tests/test_mcp_bootstrap.py
git commit -m "feat(mcp): add isolated service skeleton"
```

### Task 2: Implement authenticated principals and redaction

**Files:**
- Modify: `slh_mcp/auth.py`
- Create: `slh_mcp/security.py`
- Create: `tests/test_mcp_auth.py`

**Interfaces:**
- `Principal(subject: str, role: str, permissions: frozenset[str])`
- `Principal.from_headers(headers, expected, subject, role, permissions) -> Principal | None`
- `authorize(principal, permission: str) -> bool`
- `redact(value: str) -> str`

- [ ] **Step 1: Write tests for missing/wrong/valid bearer credentials and redaction**

```python
def test_missing_token_has_no_principal(self):
    self.assertIsNone(Principal.from_headers({}, "expected", "owner", "OWNER", ("*",)))

def test_wrong_token_has_no_principal(self):
    self.assertIsNone(Principal.from_headers({"authorization": "Bearer wrong"}, "expected", "owner", "OWNER", ("*",)))

def test_valid_token_resolves_principal(self):
    p = Principal.from_headers({"authorization": "Bearer expected"}, "expected", "owner", "OWNER", ("*",))
    self.assertEqual(p.subject, "owner")

def test_redaction_masks_bearer(self):
    self.assertIn("[REDACTED]", redact("Authorization: Bearer secret-value"))
```

- [ ] **Step 2: Run the tests**

Run: `python -m unittest tests.test_mcp_auth -v`
Expected: FAIL because the auth/security interfaces are absent.

- [ ] **Step 3: Implement environment-backed bearer authentication**

Read `SLH_MCP_BEARER_TOKEN` from the Railway environment. Reject missing, empty, non-Bearer, or mismatched credentials. Never store the configured token in a `Principal`.

- [ ] **Step 4: Bridge authorization to canonical SLH authority**

`authorize()` must call `core.authority.has_permission(principal.subject, permission)`; MCP must not maintain another OWNER/ADMIN list.

- [ ] **Step 5: Implement redaction**

Mask Authorization bearer values and reuse the credential patterns already protected by `core.exec_policy.redact_secrets`.

- [ ] **Step 6: Run tests**

Run: `python -m unittest tests.test_mcp_auth -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add slh_mcp/auth.py slh_mcp/security.py tests/test_mcp_auth.py
git commit -m "feat(mcp): add authenticated principals and redaction"
```

### Task 3: Add explicit capabilities and safe resources

**Files:**
- Modify: `slh_mcp/registry.py`
- Create: `slh_mcp/capabilities.py`
- Create: `slh_mcp/resources.py`
- Create: `tests/test_mcp_capabilities.py`

**Interfaces:**
- `Capability(name: str, description: str, permission: str, mutating: bool, handler)`
- `list_capabilities() -> list[Capability]`
- `get_capability(name: str) -> Capability`
- `register_capabilities(server) -> None`

- [ ] **Step 1: Write registry and immutability tests**

```python
def test_initial_reads_exist(self):
    names = {c.name for c in list_capabilities()}
    self.assertIn("system.health", names)
    self.assertIn("agents.list", names)
    self.assertIn("economy.agent_balance", names)

def test_shell_is_not_exposed(self):
    with self.assertRaises(KeyError):
        get_capability("exec.shell")
```

- [ ] **Step 2: Implement immutable metadata**

Store capability definitions in code, with explicit `mutating` flags, required permissions, handler references, and redaction policy.

- [ ] **Step 3: Implement `system.health`**

Return only service status/version metadata. Do not return environment variables, filesystem contents, stack traces, tokens, or database URLs.

- [ ] **Step 4: Implement agent resources**

`slh://system` returns system metadata. `slh://agents` uses `core.authority.get_visible_agents(principal.subject, list_agents())`. `slh://agent/{agent_id}` uses `get_agent()` and enforces visibility before serializing.

- [ ] **Step 5: Add read/write isolation test**

Snapshot the relevant agent state, call a read resource, then assert the state is byte-for-byte unchanged.

- [ ] **Step 6: Run tests and commit**

Run: `python -m unittest tests.test_mcp_capabilities -v`
Expected: PASS.

```bash
git add slh_mcp/registry.py slh_mcp/capabilities.py slh_mcp/resources.py tests/test_mcp_capabilities.py
git commit -m "feat(mcp): add explicit capabilities and safe resources"
```

### Task 4: Connect agent control and canonical mission reads

**Files:**
- Create: `slh_mcp/tools/agents.py`
- Create: `slh_mcp/tools/missions.py`
- Create: `tests/test_mcp_agents.py`

**Interfaces:**
- `agents_list(principal) -> list[dict]`
- `agents_get(principal, agent_id: str) -> dict`
- `agents_runtime_status(principal, agent_id: str) -> dict`
- `agents_execute(principal, agent_id: str, command: str) -> dict`
- `missions_list(principal) -> list[dict]`

- [ ] **Step 1: Write failing tests for scoped reads and runtime delegation**

```python
def test_missing_agent_is_rejected(self):
    with self.assertRaises(KeyError):
        agents_get(owner, "missing")

def test_execution_delegates_to_runtime_service(self):
    result = agents_execute(owner, "1", "ping")
    self.assertIsInstance(result, dict)
```

- [ ] **Step 2: Implement agent reads through canonical registry/authority**

Use `core.agent_registry.list_agents`, `get_agent`, and `core.authority.get_visible_agents`; do not expose raw STORE internals.

- [ ] **Step 3: Implement runtime status and execution**

Use `core.runtime_service.status()` and `core.runtime_service.execute_agent(agent_id, command, source="mcp")`. Reject empty commands and commands longer than 2000 characters.

- [ ] **Step 4: Implement mission reads**

Use `MissionLifecycleService(".").load_state()` and `MissionLifecycleService(".").find_mission()` over the canonical mission board. Do not read arbitrary state files.

- [ ] **Step 5: Run tests and commit**

Run: `python -m unittest tests.test_mcp_agents -v`
Expected: PASS.

```bash
git add slh_mcp/tools/agents.py slh_mcp/tools/missions.py tests/test_mcp_agents.py
git commit -m "feat(mcp): connect governed agents and missions"
```

### Task 5: Build the isolated agent economy

**Files:**
- Create: `core/agent_economy.py`
- Create: `slh_mcp/tools/economy.py`
- Create: `state/agent_economy.json`
- Create: `tests/test_agent_economy.py`

**Interfaces:**
- `get_agent_balance(agent_id: str) -> Decimal`
- `get_agent_ledger(agent_id: str, limit: int = 100) -> list[dict]`
- `propose_transfer(source_agent: str, target_agent: str, amount: Decimal, operation_id: str, actor: str) -> dict`
- `commit_transfer(source_agent: str, target_agent: str, amount: Decimal, operation_id: str, actor: str) -> dict`
- `record_reward(agent_id: str, amount: Decimal, operation_id: str, mission_id: str, actor: str) -> dict`

- [ ] **Step 1: Add empty isolated state schema**

`state/agent_economy.json`:

```json
{"version":1,"wallets":{},"ledger":[],"operations":{}}
```

- [ ] **Step 2: Write duplicate/invalid-input tests**

```python
def test_duplicate_commit_is_idempotent(self):
    first = commit_transfer("a", "b", Decimal("10"), "op-1", "owner")
    second = commit_transfer("a", "b", Decimal("10"), "op-1", "owner")
    self.assertEqual(first["operation_id"], second["operation_id"])
    self.assertEqual(get_agent_balance("a"), Decimal("90"))

def test_negative_amount_is_rejected_without_write(self):
    with self.assertRaises(ValueError):
        commit_transfer("a", "b", Decimal("-1"), "op-2", "owner")
```

- [ ] **Step 3: Implement atomic agent-only state mutation**

Use the repository's atomic state writer under the new agent-economy namespace. A committed `operation_id` must return the stored result without applying another debit/credit.

- [ ] **Step 4: Implement proposal and commit separation**

`propose_transfer` validates actor, agents, positive amount, maximum input length, and policy without changing balances. `commit_transfer` re-validates and atomically records debit, credit, and ledger entry.

- [ ] **Step 5: Implement reward entry**

`record_reward` adds an agent-economy credit keyed by `operation_id` and mission id. It must never call `core.mission_reward_service.issue_mission_reward`, which writes to the existing user-credit ledger.

- [ ] **Step 6: Add financial regression test**

Snapshot existing user wallet and staking data before the tests and assert it is unchanged afterward.

- [ ] **Step 7: Run tests and commit**

Run: `python -m unittest tests.test_agent_economy -v`
Expected: PASS including duplicate, invalid amount, and financial-state isolation cases.

```bash
git add core/agent_economy.py slh_mcp/tools/economy.py state/agent_economy.json tests/test_agent_economy.py
git commit -m "feat(economy): add isolated idempotent agent ledger"
```

### Task 6: Connect verified mission completion to Agent rewards

**Files:**
- Modify: `slh_mcp/tools/missions.py`
- Modify: `core/agent_economy.py`
- Create: `tests/test_mcp_mission_rewards.py`

**Interfaces:**
- `complete_agent_mission(principal, mission_id: str, agent_id: str, result: dict, operation_id: str) -> dict`

- [ ] **Step 1: Write the duplicate-completion test**

```python
def test_duplicate_completion_does_not_double_reward(self):
    first = complete_agent_mission(owner, "m-1", "a", {"result":"ok"}, "reward-m-1")
    second = complete_agent_mission(owner, "m-1", "a", {"result":"ok"}, "reward-m-1")
    self.assertEqual(first["operation_id"], second["operation_id"])
```

- [ ] **Step 2: Implement canonical mission lifecycle transition**

Use `MissionLifecycleService.complete_mission(mission_id)` and reject a mission that is missing, already blocked, or assigned to a different agent.

- [ ] **Step 3: Resolve reward from mission policy, not client input**

Read `reward` from the canonical mission record. Reject client attempts to supply or increase the reward amount.

- [ ] **Step 4: Record the reward only in the agent economy**

Call `record_reward(agent_id, reward, operation_id, mission_id, principal.subject)` and return the resulting operation record.

- [ ] **Step 5: Run tests and commit**

Run: `python -m unittest tests.test_mcp_mission_rewards -v`
Expected: PASS with no mutation to existing user-credit ledger.

```bash
git add slh_mcp/tools/missions.py core/agent_economy.py tests/test_mcp_mission_rewards.py
git commit -m "feat(mission): route verified rewards to agent economy"
```

### Task 7: Add read-only Railway and GitHub integrations

**Files:**
- Create: `slh_mcp/tools/railway.py`
- Create: `slh_mcp/tools/github.py`
- Create: `tests/test_mcp_integrations.py`

**Interfaces:**
- `railway_projects(principal) -> list[dict]`
- `railway_services(principal, project_id: str) -> list[dict]`
- `railway_deployments(principal, project_id: str, service_id: str | None = None) -> list[dict]`
- `github_repositories(principal) -> list[dict]`
- `github_ci_status(principal, repo: str, commit_sha: str) -> dict`

- [ ] **Step 1: Write read-only adapter tests**

```python
def test_railway_read_has_no_secret_values(self):
    result = railway_projects(owner)
    self.assertNotIn("authorization", repr(result).lower())

def test_github_status_returns_status_data(self):
    result = github_ci_status(owner, "osifeu-prog/slh-bot", commit_sha)
    self.assertIsInstance(result, dict)
```

- [ ] **Step 2: Implement Railway reads**

Use `core.railway_control` or a narrow adapter to return project/service/deployment identity and status only. Do not expose variables or tokens.

- [ ] **Step 3: Implement GitHub reads**

Use the available GitHub REST/API adapter for repository metadata and CI status. Do not expose connector credentials.

- [ ] **Step 4: Run tests and commit**

Run: `python -m unittest tests.test_mcp_integrations -v`
Expected: PASS against mocked adapters plus live read-only checks where the deployed service has access.

```bash
git add slh_mcp/tools/railway.py slh_mcp/tools/github.py tests/test_mcp_integrations.py
git commit -m "feat(mcp): expose infrastructure read capabilities"
```

### Task 8: Controlled deployment, CI, protocol smoke test, and production rollout

**Files:**
- Modify: `slh_mcp/tools/railway.py`
- Create: `tests/test_mcp_railway_deploy.py`
- Create: `tests/test_mcp_protocol.py`
- Create: `slh_mcp/README.md`
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/deploy.yml` only if required for the new service

**Interfaces:**
- `railway_deploy(principal, project_id: str, service_id: str, environment_id: str, commit_sha: str) -> dict`
- Live endpoint: `https://<slh-mcp-domain>/mcp`
- Health endpoint: `/health`

- [ ] **Step 1: Write deployment permission and target-allowlist tests**

```python
def test_read_only_principal_cannot_deploy(self):
    with self.assertRaises(PermissionError):
        railway_deploy(read_only, project_id, service_id, environment_id, commit_sha)

def test_unknown_target_is_rejected(self):
    with self.assertRaises(PermissionError):
        railway_deploy(owner, "unknown", service_id, environment_id, commit_sha)
```

- [ ] **Step 2: Implement deployment allowlist and terminal verification**

Only registered project/service/environment triples may deploy. Require a full 40-character commit SHA. Trigger deployment through the existing Railway control path and represent completion as success only after observing terminal `SUCCESS`.

- [ ] **Step 3: Add protocol contract tests**

Verify `/mcp` capability discovery, one authenticated read, one denied mutation, one successful isolated mutation, and Host-header rejection for an unapproved host.

- [ ] **Step 4: Add CI checks**

Append to `.github/workflows/ci.yml`:

```yaml
- name: Verify MCP contracts
  run: |
    python -m unittest tests.test_mcp_bootstrap tests.test_mcp_auth tests.test_mcp_capabilities tests.test_mcp_agents tests.test_agent_economy tests.test_mcp_mission_rewards tests.test_mcp_integrations tests.test_mcp_railway_deploy tests.test_mcp_protocol
    python -m py_compile slh_mcp/server.py slh_mcp/auth.py slh_mcp/registry.py
```

- [ ] **Step 5: Document local and production operation**

`slh_mcp/README.md` must document local Uvicorn execution, `/mcp`, `/health`, and required environment-variable names without containing any real secret values.

- [ ] **Step 6: Run the full MCP suite locally**

Run: `python -m unittest tests.test_mcp_bootstrap tests.test_mcp_auth tests.test_mcp_capabilities tests.test_mcp_agents tests.test_agent_economy tests.test_mcp_mission_rewards tests.test_mcp_integrations tests.test_mcp_railway_deploy tests.test_mcp_protocol -v`
Expected: PASS.

- [ ] **Step 7: Commit the production hardening changes**

```bash
git add slh_mcp tests/test_mcp_railway_deploy.py tests/test_mcp_protocol.py .github/workflows/ci.yml
git commit -m "test(mcp): enforce protocol and production contracts"
```

- [ ] **Step 8: Create the Railway service**

Create `slh-mcp` in `endearing-amazement` production with repository `osifeu-prog/slh-bot`, root `/`, Dockerfile `slh_mcp/Dockerfile`, and no Telegram token variables. Configure `SLH_MCP_BEARER_TOKEN`, `SLH_MCP_ALLOWED_HOSTS`, and `SLH_MCP_ALLOWED_ORIGINS` as secrets/configuration.

- [ ] **Step 9: Deploy and verify terminal success**

Observe the newest `slh-mcp` deployment until Railway reports `SUCCESS`. Do not report queued/building/deploying as live.

- [ ] **Step 10: Smoke-test the live MCP endpoint**

Connect an MCP client/Inspector to `/mcp`, verify discovery, call `system.health`, `agents.list`, and `economy.agent_balance`, then verify an unauthorized request is rejected.

- [ ] **Step 11: Run financial regression after smoke test**

Compare the pre/post snapshot of existing user `credits`, `token_balance`, `staked`, staking positions, and historical ledger rows. The expected result is zero changes.

- [ ] **Step 12: Record acceptance evidence**

Record commit, CI status, Railway deployment id/status, endpoint, capability count, and financial-regression result in the Control Plane journal. Exclude all credentials.