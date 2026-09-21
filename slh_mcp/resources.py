    server.resource(
        "slh://railway",
        name="railway",
        description="Safe Railway project metadata.",
    )(railway_resource)
    server.resource(
        "slh://github",
        name="github",
        description="Safe GitHub repository metadata.",
    )(github_resource)


def economic_resource():
    principal = _principal_or_raise()
    from slh_mcp.tools.economic_ledger import economic_ledger_summary
    from slh_mcp.auth import authorize
    if not authorize(principal, "exec.audit"):
        raise PermissionError("ECONOMIC_LEDGER_FORBIDDEN")
    return economic_ledger_summary(principal)


def register_economic_resources(server) -> None:
    server.resource(
        "slh://economy",
        name="economy",
        description="Canonical normalized SLH economic read model.",
    )(economic_resource)