"""CLI entry point for the DeepSecure stdio MCP proxy."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import typer

app = typer.Typer(
    name="deepsecure-proxy",
    help="Stdio MCP proxy with transparent JWT refresh for DeepSecure.",
    add_completion=False,
)


@app.command()
def proxy(
    agent_id: str = typer.Option(..., "--agent-id", "-a", help="Agent ID to authenticate as"),
    control_url: Optional[str] = typer.Option(None, "--control-url", help="Control plane URL"),
    gateway_url: Optional[str] = typer.Option(None, "--gateway-url", help="MCP gateway URL"),
    platform: str = typer.Option("auto", "--platform", "-p", help="Platform: auto, gcp, aws, local"),
    round_robin: bool = typer.Option(False, "--round-robin", help="Rotate through delegations"),
    delegation_id: Optional[str] = typer.Option(None, "--delegation-id", help="Pin to a specific delegation"),
    refresh_margin: int = typer.Option(300, "--refresh-margin", help="Seconds before expiry to refresh JWT"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
) -> None:
    """Start a stdio MCP proxy that reads JSON-RPC from stdin and forwards to the DeepSecure gateway."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s %(message)s")
    else:
        logging.basicConfig(level=logging.WARNING)

    from deepsecure._core.config import get_effective_deeptrail_control_url, get_effective_deeptrail_gateway_url
    from .server import DeepSecureProxy

    resolved_control = control_url or get_effective_deeptrail_control_url() or "http://localhost:8000"
    resolved_gateway = gateway_url or get_effective_deeptrail_gateway_url() or "http://localhost:8002"

    p = DeepSecureProxy(
        agent_id=agent_id,
        control_url=resolved_control,
        gateway_url=resolved_gateway,
        platform=platform,
        round_robin=round_robin,
        delegation_id=delegation_id,
        refresh_margin=refresh_margin,
    )
    asyncio.run(p.run())
