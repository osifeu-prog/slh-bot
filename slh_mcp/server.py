import contextlib
import os

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import JSONResponse

from slh_mcp.auth import (
    principal_from_headers,
    reset_current_principal,
    set_current_principal,
)
from slh_mcp.registry import register_capabilities


class MCPAuthMiddleware:
    """Protect the MCP transport while leaving health available."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        token = None
        if scope.get("type") == "http":
            path = scope.get("path", "")
            if path == "/mcp" or path.startswith("/mcp/"):
                from starlette.datastructures import Headers

                principal = principal_from_headers(Headers(scope=scope))
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


@contextlib.asynccontextmanager
async def lifespan(_app):
    async with mcp.session_manager.run():
        yield


def _transport_security():
    hosts = [
        x.strip()
        for x in os.getenv("SLH_MCP_ALLOWED_HOSTS", "").split(",")
        if x.strip()
    ]
    origins = [
        x.strip()
        for x in os.getenv("SLH_MCP_ALLOWED_ORIGINS", "").split(",")
        if x.strip()
    ]
    return TransportSecuritySettings(
        allowed_hosts=hosts or [
            "localhost", "localhost:*",
            "127.0.0.1", "127.0.0.1:*",
            "[::1]", "[::1]:*",
        ],
        allowed_origins=origins
        or [
            "http://localhost:*",
            "http://127.0.0.1:*",
            "http://[::1]:*",
        ],
    )


def build_mcp_app():
    # The MCP SDK application already owns the /mcp route and its lifespan.
    # Wrapping it in an outer ASGI app would duplicate the endpoint path.
    app = mcp.streamable_http_app(
        transport_security=_transport_security(),
    )
    app.add_middleware(MCPAuthMiddleware)
    return app


# Keep a named factory for tests and deployment introspection.
app = build_mcp_app()