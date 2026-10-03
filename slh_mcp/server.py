import contextlib
import os

from slh_mcp import control_plane_client

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.middleware import Middleware
from starlette.routing import Mount, Route

from slh_mcp.config import readiness
from slh_mcp.auth import (
    Principal,
    principal_from_scope,
    reset_current_principal,
    set_current_principal,
)
from slh_mcp.registry import register_capabilities
from slh_mcp.tools.agents import _tool_agents_runtime_status


class MCPAuthMiddleware:
    """ASGI bearer gate that exposes the verified principal through ContextVar."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        token = None
        if scope.get("type") == "http":
            path = scope.get("path", "")
            if path == "/mcp" or path.startswith("/mcp/"):
                principal = principal_from_scope(scope)
                if principal is None:
                    response = JSONResponse(
                        {"error": "AUTH_REQUIRED"},
                        status_code=401,
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                    await response(scope, receive, send)
                    return
                token = set_current_principal(principal)
        try:
            await self.app(scope, receive, send)
        finally:
            if token is not None:
                reset_current_principal(token)


mcp = MCPServer(
    "SLH OS",
    version=os.getenv("SLH_MCP_VERSION", "0.1.0"),
)
register_capabilities(mcp)


async def health(_request):
    return JSONResponse(
        {
            "status": "ok",
            "service": "SLH MCP",
            "version": os.getenv("SLH_MCP_VERSION", "0.1.0"),
        }
    )


async def ready(_request):
    state = readiness()
    return JSONResponse(
        state,
        status_code=200 if state["ready"] else 503,
    )


async def telegram_mcp_proof(request: Request):
    expected = os.getenv("SLH_MCP_BRIDGE_TOKEN", "").strip()
    subject = (
        os.getenv("SLH_MCP_BRIDGE_PRINCIPAL_ID", "").strip()
        or os.getenv("SLH_MCP_PRINCIPAL_ID", "").strip()
    )
    principal = Principal.from_headers(
        headers=request.headers,
        expected=expected,
        subject=subject,
    )
    if principal is None:
        return JSONResponse({"error": "AUTH_REQUIRED"}, status_code=401)

    token = set_current_principal(principal)
    try:
        has_view_self = "agents.view_self" in principal.permissions
        if not has_view_self:
            return JSONResponse(
                {
                    "error": "FORBIDDEN",
                    "diagnostic": {
                        "role": principal.role,
                        "has_agents_view_self": False,
                        "permission_count": len(principal.permissions),
                    },
                },
                status_code=403,
            )
        runtime = _tool_agents_runtime_status()
        return JSONResponse(
            {
                "status": "PASS",
                "tool": "agents.runtime_status",
                "runtime": runtime,
            }
        )
    except Exception as exc:
        return JSONResponse(
            {"status": "FAIL", "error": type(exc).__name__},
            status_code=502,
        )
    finally:
        reset_current_principal(token)


@contextlib.asynccontextmanager
async def lifespan(_app):
    control_plane_client.self_test()
    async with mcp.session_manager.run():
        yield


def _transport_security():
    hosts = [x.strip() for x in os.getenv("SLH_MCP_ALLOWED_HOSTS", "").split(",") if x.strip()]
    origins = [x.strip() for x in os.getenv("SLH_MCP_ALLOWED_ORIGINS", "").split(",") if x.strip()]
    return TransportSecuritySettings(
        allowed_hosts=hosts or ["localhost:*", "127.0.0.1:*", "[::1]:*"],
        allowed_origins=origins or ["http://localhost:*", "http://127.0.0.1:*", "http://[::1]:*"],
    )


def build_mcp_app():
    routes = [
        Route("/health", health, methods=["GET"]),
        Route("/ready", ready, methods=["GET"]),
        Route("/internal/telegram/mcp-proof", telegram_mcp_proof, methods=["GET"]),
        Mount(
            "/",
            app=mcp.streamable_http_app(
                transport_security=_transport_security(),
            ),
        ),
    ]
    return Starlette(
        routes=routes,
        lifespan=lifespan,
        middleware=[Middleware(MCPAuthMiddleware)],
    )


app = build_mcp_app()
