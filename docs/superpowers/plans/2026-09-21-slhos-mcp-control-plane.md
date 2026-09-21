# SLH OS MCP Control Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a persistent, authenticated SLH MCP service on Railway that exposes governed system, agent, mission, economy, Railway, and GitHub capabilities while preserving the existing SLH authority and user financial state.

**Architecture:** `slh-mcp` is a separate Railway service in the `slh-bot` repository. It exposes MCP over Streamable HTTP, uses an explicit capability registry, resolves identity through `core/authority.py`, delegates agent execution to `core/runtime_service.py`, and keeps agent economy state isolated from existing user accounting.

**Tech Stack:** Python 3.11; official MCP Python SDK v2.2.0; Starlette ASGI app from `MCPServer.streamable_http_app()`; Uvicorn; existing SLH core modules; `unittest` plus the repository's GitHub Actions validation/full-regression workflows.

**Spec:** `docs/superpowers/specs/2026-09-21-slhos-mcp-control-plane-design.md`

## Global Constraints

- "MCP is the protocol-facing access layer to that control plane; it is not a second application state store, a replacement for Telegram handlers, or an alternate authority system."
- "`core/authority.py` remains the final application-level permission source."
- "The MCP service imports the same `core/` modules from the repository. It does not duplicate the state model."
- "no direct MCP writes to 'state/db.json'"
- "no direct manipulation of existing user `credits`, `token_balance`, `staked`, or staking positions"
- "every monetary mutation is idempotent"
- "Arbitrary command execution is explicitly outside the initial MCP surface."
- "Production MCP must run only over HTTPS and use authenticated requests."
- Pin the production MCP runtime to `mcp==2.2.0`; the current official Python SDK v2 stable line is 2.2.0 and requires Python 3.10+. citeturn995046search0turn995046search1
- Use Streamable HTTP via `MCPServer.streamable_http_app()` and a top-level ASGI lifespan that enters `mcp.session_manager.run()`; deployed hostnames require explicit transport security allowlists. citeturn784467search0turn784467search3
- No production package may be installed ad hoc into a running container.

## Review Focus

- **Wrong principal/permission:** a valid MCP request using a role without the capability must be denied before the canonical service is called. Test in Task 3 with a synthetic unauthorized principal.
- **Read/write confusion:** a resource or read tool must not mutate agent or financial state. Test in Task 4 with before/after state assertions.
- **Duplicate economic operation:** repeating the same operation id must return the original result without a second ledger entry or balance change. Test in Task 6.
- **Malformed/oversized input:** invalid agent ids, negative amounts, empty operation ids, and excessively long strings must fail validation without partial writes. Test in Tasks 4 and 6.
- **Secret leakage:** tool/resource output and audit metadata must redact bearer tokens and known credential formats. Test in Task 2.

---

### Task 1: Create the isolated MCP service skeleton

**Files:**
- Create: `mcp/__init__.py`
- Create: `mcp/server.py`
- Create: `mcp/auth.py`
- Create: `mcp/registry.py`
- Create: `mcp/requirements.txt`
- Create: `mcp/Dockerfile`
- Create: `tests/test_mcp_bootstrap.py`

**Interfaces:**
- Produces `build_mcp_app() -> Starlette`, `principal_from_request(request) -> Principal | None`, and `register_capabilities(server) -> None`.
- Uses `MCPServer` from the official v2 SDK and `streamable_http_app()` for `/mcp`. citeturn784467search0

- [ ] **Step 1: Write the failing bootstrap test**

```python
from unittest import TestCase

from mcp.server import MCPServer

from mcp.server import build_mcp_app


class MCPBootstrapTests(TestCase):
    def test_builds_asgi_app(self):
        app = build_mcp_app()
        self.assertIsNotNone(app)
        self.assertTrue(hasattr(app, "routes"))

    def test_server_is_real_mcp_server(self):
        server = MCPServer("SLH OS")
        self.assertEqual(server.name, "SLH OS")
```

- [ ] **Step 2: Run the bootstrap test to verify it fails**

Run: `python -m unittest tests.test_mcp_bootstrap -v`
Expected: FAIL because the `mcp.server` module does not yet expose `build_mcp_app`.

- [ ] **Step 3: Add the production dependency manifest**

Create `mcp/requirements.txt`:

```text
mcp==2.2.0
uvicorn==0.35.0
```

- [ ] **Step 4: Implement the minimal server factory**

Create `mcp/server.py` with this shape:

```python
import contextlib
import os

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from mcp.auth import principal_from_request
from mcp.registry import register_capabilities

mcp = MCPServer("SLH OS")
register_capabilities(mcp)

@contextlib.asynccontextmanager
async def lifespan(_app):
    async with mcp.session_manager.run():
        yield

def build_mcp_app():
    hostnames = [h.strip() for h in os.getenv("SLH_MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
    origins = [h.strip() for h in os.getenv("SLH_MCP_ALLOWED_ORIGINS", "").split(",") if h.strip()]
    transport_security = TransportSecuritySettings(
        allowed_hosts=hostnames or ["localhost:*", "127.0.0.1:*"] ,
        allowed_origins=origins,
    )
    app = mcp.streamable_http_app(transport_security=transport_security)
    return app

app = build_mcp_app()
```

The exact import path for `MCPServer` must be confirmed during implementation against the pinned SDK before commit; the v2 migration guide documents `MCPServer` as the replacement for v1 `FastMCP`. citeturn784467search3

- [ ] **Step 5: Add the service Dockerfile**

Create `mcp/Dockerfile`:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY mcp/requirements.txt /tmp/mcp-requirements.txt
RUN pip install --no-cache-dir -r /tmp/mcp-requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "exec uvicorn mcp.server:app --host 0.0.0.0 --port ${PORT:-8080}"]
```

Because the server imports shared `core/` code, Railway will build from repository root and select `mcp/Dockerfile`; the service root must not be changed to `mcp/` unless imports are adjusted to preserve access to `core/`.

- [ ] **Step 6: Run the bootstrap test to verify it passes**

Run: `python -m unittest tests.test_mcp_bootstrap -v`
Expected: PASS after the dependency environment contains `mcp==2.2.0`.

- [ ] **Step 7: Commit the skeleton**

```bash
git add mcp tests/test_mcp_bootstrap.py
git commit -m "feat(mcp): add isolated control-plane service skeleton"
```

### Task 2: Implement authentication, principals, and redaction

**Files:**
- Modify: `mcp/auth.py`
- Create: `mcp/security.py`
- Create: `tests/test_mcp_auth.py`

**Interfaces:**
- Produces `Principal(subject: str, role: str, permissions: frozenset[str])`.
- Produces `authorize(principal, permission: str) -> bool` and `redact(value: str) -> str`.

- [ ] **Step 1: Write tests for missing, wrong, and valid bearer credentials**

```python
from unittest import TestCase

from mcp.auth import Principal, authorize


class MCPAuthTests(TestCase):
    def test_missing_token_has_no_principal(self):
        self.assertIsNone(Principal.from_headers({}))

    def test_wrong_token_has_no_principal(self):
        self.assertIsNone(Principal.from_headers({"authorization": "Bearer wrong"}, expected="expected"))

    def test_valid_token_resolves_owner(self):
        principal = Principal.from_headers(
            {"authorization": "Bearer expected"},
            expected="expected",
            subject="owner",
            role="OWNER",
            permissions=("*",),
        )
        self.assertEqual(principal.subject, "owner")
        self.assertTrue(authorize(principal, "anything"))
```

- [ ] **Step 2: Run the auth tests to verify they fail**

Run: `python -m unittest tests.test_mcp_auth -v`
Expected: FAIL because `Principal` and `authorize` do not yet exist.

- [ ] **Step 3: Implement bearer authentication as an environment-backed adapter**

Use `SLH_MCP_BEARER_TOKEN` only as a Railway secret; never hard-code it. The adapter must reject non-Bearer schemes, empty secrets, and malformed headers. It must map the configured subject/role only to the canonical SLH identity model, never create a parallel OWNER/ADMIN list.

- [ ] **Step 4: Implement secret redaction**

Reuse the existing redaction patterns from `core/exec_policy.py` and add bearer-header masking:

```python
def redact(value):
    text = str(value)
    text = re.sub(r"(?i)(authorization\\s*:\\s*bearer\\s+)[^\\s]+", r"\\1[REDACTED]", text)
    return text
```

- [ ] **Step 5: Pin the authority bridge**

`authorize(principal, permission)` must call `core.authority.has_permission(principal.subject, permission)` for non-owner wildcard permissions. There must be no MCP-local role decision beyond constructing the principal from the authenticated configuration.

- [ ] **Step 6: Run auth/security tests**

Run: `python -m unittest tests.test_mcp_auth -v`
Expected: PASS, including redaction and unauthorized-principal cases.

- [ ] **Step 7: Commit the security layer**

```bash
git add mcp/auth.py mcp/security.py tests/test_mcp_auth.py
git commit -m "feat(mcp): add governed authentication and redaction"
```

### Task 3: Build the explicit capability registry and read-only system resources

**Files:**
- Modify: `mcp/registry.py`
- Create: `mcp/capabilities.py`
- Create: `mcp/resources.py`
- Create: `tests/test_mcp_capabilities.py`

**Interfaces:**
- `Capability(name, description, permission, mutating, handler)`
- `get_capability(name) -> Capability`
- `list_capabilities() -> list[Capability]`
- `register_capabilities(server) -> None`

- [ ] **Step 1: Write registry contract tests**

```python
from unittest import TestCase

from mcp.capabilities import get_capability, list_capabilities


class MCPCapabilityTests(TestCase):
    def test_initial_read_capabilities_exist(self):
        names = {c.name for c in list_capabilities()}
        self.assertIn("system.health", names)
        self.assertIn("agents.list", names)
        self.assertIn("economy.agent_balance", names)

    def test_shell_is_not_a_capability(self):
        with self.assertRaises(KeyError):
            get_capability("exec.shell")
```

- [ ] **Step 2: Implement typed capability metadata**

Use an immutable dataclass for capability metadata and keep the handlers separate from registration. Mutation capabilities must have `mutating=True` and a non-empty permission.

- [ ] **Step 3: Implement `system.health` without private state**

Return only service name, version, and process status. Do not expose env variables, filesystem paths, tokens, database URLs, or raw exception traces.

- [ ] **Step 4: Implement read-only resources**

Expose `slh://system`, `slh://agents`, and `slh://agent/{agent_id}` as projections. Agent reads must use `core.agent_registry.get_agent` and `core.authority.get_visible_agents` rather than returning `STORE.get_all()` indiscriminately.

- [ ] **Step 5: Add the review-focus authorization test**

Call an agent read through a principal that lacks the required permission and assert that the canonical `get_visible_agents` path is not bypassed.

- [ ] **Step 6: Run registry/resource tests**

Run: `python -m unittest tests.test_mcp_capabilities -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add mcp/registry.py mcp/capabilities.py mcp/resources.py tests/test_mcp_capabilities.py
git commit -m "feat(mcp): add explicit capabilities and safe resources"
```

### Task 4: Connect MCP to canonical agent runtime and mission state

**Files:**
- Create: `mcp/tools/agents.py`
- Create: `mcp/tools/missions.py`
- Create: `tests/test_mcp_agents.py`

**Interfaces:**
- `agents_list(principal) -> list[dict]`
- `agents_get(principal, agent_id: str) -> dict`
- `agents_runtime_status(principal, agent_id: str) -> dict`
- `agents_execute(principal, agent_id: str, command: str, source: str | None = None) -> dict`
- `missions_list(principal) -> list[dict]`

- [ ] **Step 1: Write failing tests for scoped reads and execution delegation**

```python
def test_agent_execute_uses_runtime_service(self):
    result = agents_execute(owner, "1", "ping", "mcp-test")
    self.assertIn("status", result)

def test_invalid_agent_id_does_not_write_state(self):
    with self.assertRaises(KeyError):
        agents_get(owner, "missing-agent")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m unittest tests.test_mcp_agents -v`
Expected: FAIL because the MCP tool modules do not yet exist.

- [ ] **Step 3: Implement scoped agent reads**

`agents_list` must call `core.authority.get_visible_agents(principal.subject, core.agent_registry.list_agents())`. It must not serialize `inbox`, `history`, `permissions`, or `owner_id` for roles where the authority layer already strips them.

- [ ] **Step 4: Implement runtime status**

Use `core.runtime_service.status()` for runtime health and identify the requested agent from the canonical registry. Do not instantiate an arbitrary runtime class directly.

- [ ] **Step 5: Implement governed agent execution**

Call `core.runtime_service.execute_agent(agent_id, command, source="mcp")` only after capability authorization. Reject empty commands and commands longer than 2000 characters before delegation. MCP must not expose `core.exec_policy.run_gated` as a generic shell tool.

- [ ] **Step 6: Implement mission reads using the existing mission source**

Inspect the canonical mission handler/store at implementation time and adapt it behind `missions_list`; do not read arbitrary `state/` files from MCP.

- [ ] **Step 7: Run the tests**

Run: `python -m unittest tests.test_mcp_agents -v`
Expected: PASS with execution routed through `core.runtime_service`.

- [ ] **Step 8: Commit**

```bash
git add mcp/tools/agents.py mcp/tools/missions.py tests/test_mcp_agents.py
git commit -m "feat(mcp): connect agent and mission control"
```

### Task 5: Add agent-only economy state with an idempotent ledger

**Files:**
- Create: `core/agent_economy.py`
- Create: `mcp/tools/economy.py`
- Create: `tests/test_agent_economy.py`
- Create or initialize: `state/agent_economy.json` with an empty schema only if the repository's state policy allows committing an empty catalog; otherwise create the file at first runtime through the atomic store.

**Interfaces:**
- `get_agent_balance(agent_id: str) -> Decimal`
- `get_agent_ledger(agent_id: str, limit: int = 100) -> list[dict]`
- `propose_transfer(source_agent: str, target_agent: str, amount: Decimal, operation_id: str, actor: str) -> dict`
- `commit_transfer(source_agent: str, target_agent: str, amount: Decimal, operation_id: str, actor: str) -> dict`

- [ ] **Step 1: Write the failing duplicate/concurrency tests**

```python
def test_duplicate_commit_is_idempotent(self):
    first = commit_transfer("a", "b", Decimal("10"), "op-1", "owner")
    second = commit_transfer("a", "b", Decimal("10"), "op-1", "owner")
    self.assertEqual(first["operation_id"], second["operation_id"])
    self.assertEqual(get_agent_balance("a"), Decimal("90"))

def test_negative_transfer_is_rejected_without_write(self):
    with self.assertRaises(ValueError):
        commit_transfer("a", "b", Decimal("-1"), "op-2", "owner")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_agent_economy -v`
Expected: FAIL because the isolated agent ledger does not exist.

- [ ] **Step 3: Define the isolated schema**

Use a separate agent economy namespace containing `wallets`, `ledger`, and `operations`. Each ledger row must include `operation_id`, `actor`, `source_agent`, `target_agent`, `amount`, `created_at`, and `status`.

- [ ] **Step 4: Implement atomic persistence and idempotency**

Use the repository's canonical atomic state writer only for the new agent-economy namespace. Before applying a mutation, look up `operation_id`; if it already has a committed result, return that result unchanged. Never touch user wallet fields.

- [ ] **Step 5: Implement MCP economy reads**

`economy.agent_balance` and `economy.agent_ledger` must require the agent visibility/ownership permission and must expose only agent-economy records.

- [ ] **Step 6: Implement proposal/commit separation**

`economy.propose_transfer` validates actor, agents, amount, and policy but does not mutate balances. `economy.commit_transfer` re-validates the proposal, checks idempotency, then atomically writes the debit, credit, and ledger entry as one operation.

- [ ] **Step 7: Add the financial-regression guard**

Capture a checksum or exact serialized snapshot of existing user wallet/staking fields before and after agent-economy tests and assert equality. The regression test must fail if any existing user balance or staking position changes.

- [ ] **Step 8: Run the full economy test suite**

Run: `python -m unittest tests.test_agent_economy -v`
Expected: PASS, including duplicate operation, invalid amount, and financial-state isolation tests.

- [ ] **Step 9: Commit**

```bash
git add core/agent_economy.py mcp/tools/economy.py tests/test_agent_economy.py
git commit -m "feat(economy): add isolated idempotent agent ledger"
```

### Task 6: Connect missions to governed agent rewards

**Files:**
- Modify: `mcp/tools/missions.py`
- Modify: `core/agent_economy.py`
- Create: `tests/test_mcp_mission_rewards.py`

**Interfaces:**
- `complete_mission(principal, mission_id: str, agent_id: str, result: dict, operation_id: str) -> dict`

- [ ] **Step 1: Write tests for reward verification and duplicate completion**

```python
def test_duplicate_mission_completion_does_not_double_reward(self):
    first = complete_mission(owner, "m-1", "a", {"result": "ok"}, "reward-m-1")
    second = complete_mission(owner, "m-1", "a", {"result": "ok"}, "reward-m-1")
    self.assertEqual(first["operation_id"], second["operation_id"])
```

- [ ] **Step 2: Verify the test fails**

Run: `python -m unittest tests.test_mcp_mission_rewards -v`
Expected: FAIL because completion/reward integration is not implemented.

- [ ] **Step 3: Add mission policy validation**

Require an existing mission, an eligible agent, a non-empty result object, and an idempotency key. Reward amount must come from the mission policy, not from client input.

- [ ] **Step 4: Commit reward through the agent ledger**

Use `commit_transfer` or a dedicated reward entry in `core.agent_economy`; never mutate an existing user wallet. Record the mission id in the ledger metadata.

- [ ] **Step 5: Run the tests**

Run: `python -m unittest tests.test_mcp_mission_rewards -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add core/agent_economy.py mcp/tools/missions.py tests/test_mcp_mission_rewards.py
git commit -m "feat(mission): connect verified rewards to agent economy"
```

### Task 7: Add read-only Railway and GitHub capabilities

**Files:**
- Create: `mcp/tools/railway.py`
- Create: `mcp/tools/github.py`
- Create: `tests/test_mcp_integrations.py`

**Interfaces:**
- `railway_projects(principal) -> list[dict]`
- `railway_services(principal, project_id: str) -> list[dict]`
- `railway_deployments(principal, project_id: str, service_id: str | None = None) -> list[dict]`
- `github_repositories(principal) -> list[dict]`
- `github_ci_status(principal, repo: str, commit_sha: str) -> dict`

- [ ] **Step 1: Write read-only adapter tests**

```python
def test_railway_output_contains_no_credentials(self):
    result = railway_projects(owner)
    self.assertNotIn("token", repr(result).lower())

def test_github_status_is_read_only(self):
    result = github_ci_status(owner, "osifeu-prog/slh-bot", "main")
    self.assertIn("statuses", result)
```

- [ ] **Step 2: Verify tests fail**

Run: `python -m unittest tests.test_mcp_integrations -v`
Expected: FAIL because the adapters do not yet exist.

- [ ] **Step 3: Implement Railway reads through `core.railway_control` or a narrowly scoped adapter**

Return project/service/deployment identity and status only. Never return Railway environment-variable values.

- [ ] **Step 4: Implement GitHub reads through a dedicated connector adapter or repository metadata API available to the deployed service**

Return repository name, default branch, and CI status. Never return GitHub tokens.

- [ ] **Step 5: Run the integration tests**

Run: `python -m unittest tests.test_mcp_integrations -v`
Expected: PASS against mocked adapters and live read-only connector checks where credentials are available.

- [ ] **Step 6: Commit**

```bash
git add mcp/tools/railway.py mcp/tools/github.py tests/test_mcp_integrations.py
git commit -m "feat(mcp): expose governed infrastructure read capabilities"
```

### Task 8: Add controlled deployment capability and Railway service configuration

**Files:**
- Modify: `mcp/tools/railway.py`
- Create: `tests/test_mcp_railway_deploy.py`
- Modify or create: Railway service configuration after repository implementation is merged

**Interfaces:**
- `railway_deploy(principal, project_id: str, service_id: str, environment_id: str, commit_sha: str) -> dict`

- [ ] **Step 1: Write the deployment gate test**

```python
def test_deploy_requires_permission(self):
    with self.assertRaises(PermissionError):
        railway_deploy(read_only_principal, project, service, environment, commit_sha)
```

- [ ] **Step 2: Verify it fails**

Run: `python -m unittest tests.test_mcp_railway_deploy -v`
Expected: FAIL because the mutation capability does not yet exist.

- [ ] **Step 3: Implement target allowlisting**

Allow deployment only to explicitly registered project/service/environment triples. Reject arbitrary service ids and reject missing 40-character commit SHAs.

- [ ] **Step 4: Implement deploy + terminal-status verification**

Trigger deployment through the existing Railway control path, poll the deployment id through the Railway adapter, and return `SUCCESS` only after observing terminal `SUCCESS`. `NEEDS_APPROVAL`, `BUILDING`, `DEPLOYING`, `FAILED`, and other non-success states must remain explicit results.

- [ ] **Step 5: Configure the separate Railway service**

Create service `slh-mcp` in `endearing-amazement`, production environment, using repository `osifeu-prog/slh-bot`, Dockerfile path `mcp/Dockerfile`, root directory `/`, and start command supplied by the Dockerfile. Add only the required secret/environment variables; never copy Telegram bot tokens into the MCP service.

- [ ] **Step 6: Run the deployment capability tests**

Run: `python -m unittest tests.test_mcp_railway_deploy -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add mcp/tools/railway.py tests/test_mcp_railway_deploy.py
git commit -m "feat(mcp): add allowlisted Railway deployment control"
```

### Task 9: Production protocol tests, CI integration, deployment, and smoke verification

**Files:**
- Create: `tests/test_mcp_protocol.py`
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/deploy.yml` only if the existing workflow does not already support the new service
- Create: `mcp/README.md`

**Interfaces:**
- The production endpoint is `https://<slh-mcp-domain>/mcp`.
- `/health` returns a minimal unauthenticated JSON health response; `/mcp` requires authentication.

- [ ] **Step 1: Add protocol contract tests**

Test discovery, one read tool, one denied mutation, one successful authenticated mutation against an isolated fixture, and Host allowlist rejection.

- [ ] **Step 2: Add CI checks**

Add to `.github/workflows/ci.yml`:

```yaml
- name: Verify MCP service
  run: |
    python -m unittest tests.test_mcp_bootstrap tests.test_mcp_auth tests.test_mcp_capabilities tests.test_mcp_agents tests.test_agent_economy tests.test_mcp_mission_rewards tests.test_mcp_integrations tests.test_mcp_railway_deploy tests.test_mcp_protocol
    python -m py_compile mcp/server.py mcp/auth.py mcp/registry.py
```

- [ ] **Step 3: Document local run and production endpoint contract**

Create `mcp/README.md` with:

```text
Local:
  uvicorn mcp.server:app --host 127.0.0.1 --port 8080

MCP endpoint:
  /mcp

Health:
  /health

Required environment:
  SLH_MCP_BEARER_TOKEN
  SLH_MCP_ALLOWED_HOSTS
  SLH_MCP_ALLOWED_ORIGINS
```

Do not document or example any actual secret value.

- [ ] **Step 4: Run CI-equivalent checks locally**

Run: `python -m unittest tests.test_mcp_bootstrap tests.test_mcp_auth tests.test_mcp_capabilities tests.test_mcp_agents tests.test_agent_economy tests.test_mcp_mission_rewards tests.test_mcp_integrations tests.test_mcp_railway_deploy tests.test_mcp_protocol`
Expected: PASS.

- [ ] **Step 5: Commit the final CI/documentation changes**

```bash
git add .github/workflows/ci.yml mcp/README.md tests/test_mcp_protocol.py
git commit -m "test(mcp): enforce protocol and regression contracts"
```

- [ ] **Step 6: Merge after review and green CI**

Open the implementation PR, verify `validate`, `full-regression`, and security checks, then merge only after all required checks are green.

- [ ] **Step 7: Deploy the new service and verify terminal success**

Create/trigger the Railway `slh-mcp` deployment and inspect the newest deployment until its status is exactly `SUCCESS`. Do not report a queued/building deployment as live.

- [ ] **Step 8: Smoke-test the live endpoint**

Use an authenticated MCP client/Inspector against `/mcp`, verify capability discovery, call `system.health`, `agents.list`, and `economy.agent_balance`, then verify unauthorized access is rejected.

- [ ] **Step 9: Run the financial regression check after deployment**

Compare the existing user financial-state snapshot before and after smoke testing; assert no user `credits`, `token_balance`, `staked`, staking positions, or historical ledger rows changed.

- [ ] **Step 10: Record final acceptance evidence**

Record the final Git commit, CI checks, Railway deployment id/status, MCP endpoint, capability count, and financial regression result in the Control Plane journal without recording any credentials.