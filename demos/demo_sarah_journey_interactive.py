#!/usr/bin/env python3
"""Interactive Sarah's Journey Demo - DeepSecure Virtual MCP Server.

This is the main entry point for the interactive demonstration of
DeepSecure's Identity-as-Code capabilities for AI agents.

The demo walks through Sarah's Journey in 10 steps, showing how:
- IT Admin configures the organization
- Sarah connects her tools and creates an agent
- The agent authenticates and operates with delegated permissions
- Security policies are enforced and audited

Usage:
    python demos/demo_sarah_journey_interactive.py [OPTIONS]

Examples:
    # Full interactive demo
    python demos/demo_sarah_journey_interactive.py

    # Start as IT Admin
    python demos/demo_sarah_journey_interactive.py --persona it_admin

    # Start from step 5
    python demos/demo_sarah_journey_interactive.py --start-step 5

    # Auto mode (no prompts, for testing)
    python demos/demo_sarah_journey_interactive.py --auto

    # Dry run without API calls
    python demos/demo_sarah_journey_interactive.py --skip-api
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports when running directly
_parent_dir = Path(__file__).parent.parent
if str(_parent_dir) not in sys.path:
    sys.path.insert(0, str(_parent_dir))

from rich.console import Console  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.text import Text  # noqa: E402

from demos.interactive import PERSONAS, DemoContext  # noqa: E402
from demos.interactive.api_client import APIClient  # noqa: E402
from demos.interactive.prompts import PromptUI  # noqa: E402
from demos.interactive.role_switcher import RoleSwitcher  # noqa: E402
from demos.interactive.step_handlers import STEP_HANDLERS  # noqa: E402


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Interactive Sarah's Journey Demo - DeepSecure Virtual MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                      Full interactive demo
  %(prog)s --persona it_admin   Start as IT Admin
  %(prog)s --start-step 5       Start from step 5
  %(prog)s --auto               Auto-advance (no prompts)
  %(prog)s --skip-api           Dry run without API calls
        """,
    )

    parser.add_argument(
        "--persona",
        choices=list(PERSONAS.keys()),
        default="sarah",
        metavar="PERSONA",
        help="Starting persona: %(choices)s [default: %(default)s]",
    )

    parser.add_argument(
        "--start-step",
        type=int,
        choices=range(1, 11),
        default=1,
        metavar="N",
        help="Start from step N (1-10) [default: %(default)s]",
    )

    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-advance without user prompts",
    )

    parser.add_argument(
        "--skip-api",
        action="store_true",
        help="Skip actual API calls (dry run mode)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    return parser.parse_args()


def show_welcome_banner(console: Console, args: argparse.Namespace) -> None:
    """Display the welcome banner.

    Args:
        console: Rich Console for output
        args: Parsed command-line arguments
    """
    banner_text = Text()
    banner_text.append("Sarah's Journey\n", style="bold cyan")
    banner_text.append("DeepSecure Virtual MCP Server Demo\n\n", style="dim")
    banner_text.append("This interactive demo shows how DeepSecure provides\n")
    banner_text.append("Identity-as-Code for AI agents, enabling secure\n")
    banner_text.append("credential management without exposing secrets.\n\n")

    mode_info = []
    if args.auto:
        mode_info.append("Auto mode (no prompts)")
    if args.skip_api:
        mode_info.append("Dry run (no API calls)")
    if args.start_step > 1:
        mode_info.append(f"Starting at step {args.start_step}")
    if args.persona != "sarah":
        mode_info.append(f"Starting as {args.persona}")

    if mode_info:
        banner_text.append("Mode: ", style="bold")
        banner_text.append(", ".join(mode_info), style="yellow")

    console.print(
        Panel(
            banner_text,
            title="[bold green]Welcome[/bold green]",
            border_style="green",
            padding=(1, 2),
        )
    )
    console.print()


def show_step_overview(console: Console) -> None:
    """Display overview of the 10 steps.

    Args:
        console: Rich Console for output
    """
    steps = [
        ("1", "IT Admin", "Organization Setup"),
        ("2", "Sarah", "Install SDK & Authenticate"),
        ("3", "Sarah", "Connect External Tools"),
        ("4", "Sarah + Vendor", "Create Agent Identity"),
        ("5", "Agent + Vendor", "Agent Registration"),
        ("6", "Sarah + Vendor", "Grant Permissions"),
        ("7", "Agent", "Tool Discovery"),
        ("8", "Agent", "Agent Runtime"),
        ("9", "Agent + Security", "Permission Enforcement"),
        ("10", "All Personas", "Audit Review"),
    ]

    overview = Text()
    overview.append("The 10 Steps of Sarah's Journey:\n\n", style="bold")

    for step_num, persona, title in steps:
        overview.append(f"  Step {step_num:>2}: ", style="cyan")
        overview.append(f"[{persona}] ", style="dim")
        overview.append(f"{title}\n")

    console.print(
        Panel(
            overview,
            title="[bold blue]Journey Overview[/bold blue]",
            border_style="blue",
            padding=(0, 2),
        )
    )
    console.print()


async def run_demo(args: argparse.Namespace) -> int:
    """Run the interactive demo.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    console = Console()

    # Show welcome banner
    show_welcome_banner(console, args)

    # Show step overview if starting from beginning
    if args.start_step == 1 and not args.auto:
        show_step_overview(console)

    # Initialize components
    ui = PromptUI(console=console, auto_mode=args.auto)

    if args.skip_api:
        api = APIClient(console=console)  # Still create for display methods
        if args.verbose:
            console.print("[yellow]Running in dry-run mode (no actual API calls)[/yellow]\n")
    else:
        api = APIClient(console=console)

    switcher = RoleSwitcher(ui=ui, console=console)

    # Create context with all components
    ctx = DemoContext(
        api=api,
        ui=ui,
        switcher=switcher,
        auto_mode=args.auto,
        verbose=args.verbose,
        current_step=args.start_step - 1,  # Will be incremented on first step
    )

    # Confirm to start (unless auto mode)
    if not args.auto:
        if not await ui.confirm(
            f"Ready to start the demo from step {args.start_step}?",
            default=True,
        ):
            console.print("[yellow]Demo cancelled.[/yellow]")
            return 0

    console.print()

    try:
        # Run steps from start_step to 10
        for step in range(args.start_step, 11):
            ctx.go_to_step(step)

            if args.verbose:
                console.print(f"[dim]Executing step {step}...[/dim]")

            handler = STEP_HANDLERS[step]
            await handler(ctx)

            # Brief pause between steps in auto mode for readability
            if args.auto and step < 10:
                await asyncio.sleep(0.5)

    except KeyboardInterrupt:
        console.print("\n[yellow]Demo interrupted by user.[/yellow]")
        console.print(f"[dim]Completed through step {ctx.current_step}[/dim]")
        return 1

    except Exception as e:
        console.print(f"\n[red]Error during step {ctx.current_step}: {e}[/red]")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1

    # Clean up API client
    if api:
        await api.close()

    return 0


def main() -> None:
    """Main entry point."""
    args = parse_args()

    try:
        exit_code = asyncio.run(run_demo(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nDemo cancelled.")
        sys.exit(1)


if __name__ == "__main__":
    main()
