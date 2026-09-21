import contextlib
import os

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.middleware import Middleware
from starlette.routing import Mount, Route

from slh_mcp.auth import (
    principal_from_scope,
    reset_current_principal,
    set_current_principal,
)
from slh_mcp.registry import register_capabilities


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


def _validate_production_config():
    if os.getenv("RAILWAY_SERVICE_NAME", "").strip() != "slh-mcp":
        return
    missing = [
        name for name in ("SLH_MCP_BEARER_TOKEN", "SLH_CORE_API_URL", "SLH_CORE_INTERNAL_KEY")
        if not os.getenv(name, "").strip()
    ]
    if missing:
        raise RuntimeError("SLH_MCP_PRODUCTION_CONFIG_MISSING:" + ",".join(missing))


_validate_production_config()


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


@contextlib.asynccontextmanager
async def lifespan(_app):
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