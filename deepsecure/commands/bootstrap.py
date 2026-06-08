"""``deepsecure bootstrap`` — obtain an agent JWT and optionally output MCP config."""

from __future__ import annotations

import json
import sys
from enum import Enum
from typing import Optional

import typer

app = typer.Typer(help="Bootstrap agent identity and obtain a JWT.")


class OutputFormat(str, Enum):
    jwt = "jwt"
    mcp_json = "mcp-json"
    env = "env"


@app.callback(invoke_without_command=True)
def bootstrap_command(
    agent_id: str = typer.Option(
        ...,
        "--agent-id",
        "-a",
        help="Agent ID to bootstrap (e.g. agent-abc123).",
    ),
    platform: str = typer.Option(
        "auto",
        "--platform",
        "-p",
        help="Platform to use: auto, gcp, aws, local.",
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.jwt,
        "--output",
        "-o",
        help="Output format: jwt (raw token), mcp-json (MCP config), env (shell exports).",
    ),
    control_url: Optional[str] = typer.Option(
        None,
        "--control-url",
        envvar="DEEPSECURE_DEEPTRAIL_CONTROL_URL",
        help="Control plane URL (default: from config or localhost:8000).",
    ),
    gateway_url: Optional[str] = typer.Option(
        None,
        "--gateway-url",
        envvar="DEEPSECURE_DEEPTRAIL_GATEWAY_URL",
        help="Gateway URL (default: from config or localhost:8002).",
    ),
    no_delegations: bool = typer.Option(
        False,
        "--no-delegations",
        help="Skip delegation fetching (faster, returns discovery JWT only).",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress informational output (only print the result).",
    ),
) -> None:
    """Bootstrap agent identity and print credentials.

    \b
    Examples:
      deepsecure bootstrap --agent-id agent-abc123 --platform gcp
      deepsecure bootstrap -a agent-abc123 -o mcp-json
      deepsecure bootstrap -a agent-abc123 -o env --quiet
    """
    from .._core.bootstrap import BootstrapClient, Platform

    valid_platforms = {p.value for p in Platform}
    if platform not in valid_platforms:
        typer.echo(
            f"Error: invalid platform '{platform}'. Choose from: {', '.join(sorted(valid_platforms))}",
            err=True,
        )
        raise typer.Exit(code=1)

    plat = Platform(platform)

    if not quiet:
        typer.echo(
            f"Bootstrapping agent '{agent_id}' on platform '{plat.value}'...",
            err=True,
        )

    try:
        with BootstrapClient(
            control_url=control_url, gateway_url=gateway_url
        ) as client:
            result = client.bootstrap(
                agent_id,
                plat,
                fetch_delegations=not no_delegations,
            )
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1)

    if not quiet:
        typer.echo(
            f"Bootstrap successful — platform={result.platform.value}, "
            f"delegations={len(result.delegations)}",
            err=True,
        )

    if output == OutputFormat.jwt:
        sys.stdout.write(result.jwt)
        sys.stdout.write("\n")
    elif output == OutputFormat.mcp_json:
        json.dump(result.to_mcp_json(), sys.stdout, indent=2)
        sys.stdout.write("\n")
    elif output == OutputFormat.env:
        sys.stdout.write(result.to_env())
        sys.stdout.write("\n")
