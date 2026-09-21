import contextlib
import os

from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from slh_mcp.registry import register_capabilities

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
    return Starlette(routes=routes, lifespan=lifespan)


app = build_mcp_app()
