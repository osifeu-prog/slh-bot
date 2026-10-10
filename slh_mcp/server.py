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
    authorize,
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
        has_view_self = authorize(principal, "agents.view_self")
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


def _telegram_bridge_principal(request: Request, permission: str):
    expected = os.getenv("SLH_MCP_BRIDGE_TOKEN", "").strip()
    subject = (
        os.getenv("SLH_MCP_BRIDGE_PRINCIPAL_ID", "").strip()
        or os.getenv("SLH_MCP_PRINCIPAL_ID", "").strip()
    )
    if not expected or not subject:
        return None, JSONResponse({"error": "MCP_BRIDGE_NOT_CONFIGURED"}, status_code=503)
    principal = Principal.from_headers(
        headers=request.headers,
        expected=expected,
        subject=subject,
    )
    if principal is None:
        return None, JSONResponse({"error": "MCP_BRIDGE_AUTH_REQUIRED"}, status_code=401)
    if not authorize(principal, permission):
        return None, JSONResponse({"error": "MCP_BRIDGE_FORBIDDEN"}, status_code=403)
    return principal, None


def _safe_control_plane_error(exc: Exception) -> str:
    message = str(exc or "").upper()
    known = (
        "RAILWAY_CONTROL_TOKEN_MISSING",
        "RAILWAY_AUTHENTICATION_FAILED",
        "RAILWAY_ACCESS_DENIED",
        "RAILWAY_TARGET_NOT_FOUND",
        "RAILWAY_API_UNREACHABLE",
        "RAILWAY_VARIABLE_READ_FAILED",
        "RAILWAY_VARIABLE_VERIFY_FAILED",
        "RAILWAY_VARIABLE_UPDATE_REJECTED",
        "RAILWAY_GRAPHQL_SCHEMA_OR_REQUEST_ERROR",
        "RAILWAY_DEPLOY_ID_MISSING",
        "RAILWAY_API_ERROR",
        "EXCHANGE_GATE_CLOSE_NOT_VERIFIED",
    )
    for code in known:
        if code in message:
            return code
    if "CONTROL_PLANE_HTTP_401" in message:
        return "CONTROL_PLANE_AUTH_FAILED"
    if "CONTROL_PLANE_HTTP_403" in message:
        return "CONTROL_PLANE_ACCESS_DENIED"
    if "CONTROL_PLANE_UNAVAILABLE" in message:
        return "CONTROL_PLANE_UNAVAILABLE"
    if "CONTROL_PLANE_BRIDGE_NOT_CONFIGURED" in message:
        return "CONTROL_PLANE_BRIDGE_NOT_CONFIGURED"
    if "CONTROL_PLANE_INVALID_RESPONSE" in message or "CONTROL_PLANE_INVALID_JSON" in message:
        return "CONTROL_PLANE_INVALID_RESPONSE"
    return "CONTROL_PLANE_REQUEST_FAILED"


async def telegram_exchange_gate_status(request: Request):
    _principal, error = _telegram_bridge_principal(request, "agents.view_self")
    if error:
        return error
    try:
        result = control_plane_client.exchange_gate_status()
        configured = str(result.get("configured") or "UNKNOWN")
        if result.get("status") != "PASS" or configured not in {"0", "1", "MISSING", "INVALID", "UNKNOWN"}:
            return JSONResponse({"status": "ERROR", "error": "CONTROL_PLANE_INVALID_RESPONSE"}, status_code=502)
        return JSONResponse({
            "status": "PASS",
            "configured": configured,
            "configured_open": configured == "1",
        })
    except Exception as exc:
        return JSONResponse({
            "status": "ERROR",
            "error": _safe_control_plane_error(exc),
        }, status_code=502)


async def telegram_exchange_gate_close(request: Request):
    _principal, error = _telegram_bridge_principal(request, "agents.manage")
    if error:
        return error
    try:
        result = control_plane_client.exchange_gate_close()
        commit = str(result.get("commit") or "")
        deployment_id = str(result.get("deployment_id") or "")
        if result.get("status") != "DEPLOY_TRIGGERED" or result.get("configured") != "0" or not commit or not deployment_id:
            return JSONResponse({"status": "ERROR", "error": "CONTROL_PLANE_INVALID_RESPONSE"}, status_code=502)
        return JSONResponse({
            "status": "DEPLOY_TRIGGERED",
            "configured": "0",
            "commit": commit,
            "deployment_id": deployment_id,
        })
    except Exception as exc:
        return JSONResponse({
            "status": "ERROR",
            "error": _safe_control_plane_error(exc),
        }, status_code=502)


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
        Route("/internal/telegram/exchange-gate", telegram_exchange_gate_status, methods=["GET"]),
        Route("/internal/telegram/exchange-gate/close", telegram_exchange_gate_close, methods=["POST"]),
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
