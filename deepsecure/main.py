'''Main CLI application entry point.'''
import typer
import importlib.metadata
import sys
from typing_extensions import Annotated
import logging

from .commands import (
    agent,
    configure,
    bootstrap,
)
from . import __version__
from ._core.config import get_cli_log_level, set_cli_log_level
from .utils import setup_logging

# Initialize logging as early as possible
# Call setup_logging() with the configured level
try:
    current_log_level = get_cli_log_level()
    setup_logging(current_log_level)
except Exception as e:
    # Fallback in case config or logging setup fails catastrophically before proper error handling
    print(f"Initial logging setup failed: {e}. Using default logging.", file=sys.stderr)
    setup_logging() # Attempt with default level

app = typer.Typer(
    name="deepsecure",
    help=(
        "DeepSecure CLI: Tools for managing agent identities, secure credentials, "
        "and security governance for AI agent ecosystems.\n\n"
        "🛡️ Enhance Agent Security | 🆔 Strong Agent Identities | 🔑 Secure Key Storage"
    ),
    rich_markup_mode="markdown",
    no_args_is_help=True,
    add_completion=False # Optional: disable shell completion for simplicity if not needed
)

app.add_typer(agent.app, name="agent", help="Manage agents.")
app.add_typer(configure.app, name="configure", help="Configure the DeepSecure CLI.")
app.add_typer(bootstrap.app, name="bootstrap", help="Bootstrap agent identity and obtain a JWT.")

try:
    from .commands import vault
    app.add_typer(vault.app, name="vault", help="Manage secrets in the vault.")
except ImportError:
    pass

try:
    from .commands import policy
    app.add_typer(policy.app, name="policy", help="Manage security policies.")
except ImportError:
    pass

try:
    from .commands import gateway
    app.add_typer(gateway.app, name="gateway", help="Manage and monitor the DeepSecure gateway service.")
except ImportError:
    pass

# Register other commands as they're implemented
# app.add_typer(audit.app, name="audit")
# app.add_typer(risk.app, name="risk")
# app.add_typer(policy.app, name="policy")
# app.add_typer(sandbox.app, name="sandbox")
# app.add_typer(scan.app, name="scan")
# app.add_typer(harden.app, name="harden")
# app.add_typer(deploy.app, name="deploy")
# app.add_typer(scorecard.app, name="scorecard")
# app.add_typer(inventory.app, name="inventory")
# app.add_typer(ide.app, name="ide")

# Version callback
def version_callback(value: bool):
    if value:
        print(f"DeepSecure CLI Version: {__version__}")
        raise typer.Exit()

@app.callback()
def main_callback(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-v",
            callback=version_callback,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
):
    """
    DeepSecure CLI: Secure your AI agent ecosystem.
    """
    # This callback runs before any command.
    # You can add global flags or initial checks here if needed.
    pass

@app.command("login")
def login(
    endpoint: str = typer.Option(None, help="API endpoint to authenticate with"),
    interactive: bool = typer.Option(True, help="Use interactive login flow")
):
    """Authenticate with DeepSecure backend."""
    from . import auth, utils
    
    if endpoint:
        utils.console.print(f"Authenticating with endpoint: [bold]{endpoint}[/]")
    else:
        utils.console.print("Authenticating with default endpoint")
    
    # Placeholder for actual login logic
    if interactive:
        # Ensure authenticated (will use placeholder flow if needed)
        auth.ensure_authenticated()
    else:
        # Non-interactive might rely on env vars or existing token
        token = auth.get_token()
        if not token:
            utils.print_error("Authentication required. Use interactive login or set DEEPSECURE_API_TOKEN.")
            # Exit handled by print_error
        else:
             utils.print_success("Using existing authentication.")

if __name__ == "__main__":
    app() 