"""Interactive prompt UI for Sarah's Journey demo.

This module provides the PromptUI class that handles all interactive
prompts and display formatting using rich and questionary libraries.
"""

import json
from typing import Any

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from demos.interactive.personas import Persona


class PromptUI:
    """Interactive prompt UI using rich and questionary.

    Provides formatted prompts, banners, and display methods
    for the interactive demo experience.

    Attributes:
        console: Rich Console for formatted output
        auto_mode: If True, skip interactive prompts and use defaults
    """

    def __init__(
        self,
        console: Console | None = None,
        auto_mode: bool = False,
    ) -> None:
        """Initialize the prompt UI.

        Args:
            console: Optional Rich Console. Creates new if not provided.
            auto_mode: If True, skip interactive prompts and use defaults.
        """
        self.console = console or Console()
        self.auto_mode = auto_mode

    def role_banner(
        self,
        persona: Persona,
        step: int,
        title: str,
    ) -> None:
        """Display a role-specific banner for a step.

        Shows persona emoji, name, and step title in persona's color.
        Creates a visually distinct marker for role switches.

        Args:
            persona: The Persona for styling
            step: Current step number (1-10)
            title: Step title text
        """
        banner_text = f"{persona.emoji} {persona.name} - Step {step}: {title}"
        self.console.print(
            Panel(
                Text(banner_text, style=f"bold {persona.color}"),
                border_style=persona.color,
                padding=(0, 1),
            )
        )

    async def multi_select(
        self,
        prompt: str,
        choices: list[str],
        default: list[str] | None = None,
    ) -> list[str]:
        """Present multi-select prompt using questionary.

        Uses checkbox style for multiple selections.
        In auto_mode, returns default selections or all choices.

        Args:
            prompt: Question text to display
            choices: List of available choices
            default: Pre-selected choices (optional)

        Returns:
            List of selected choices (may be empty)

        Raises:
            ValueError: If choices list is empty
        """
        if not choices:
            raise ValueError("choices cannot be empty")

        # In auto mode, return default or all choices
        if self.auto_mode:
            result = default if default else choices
            self.console.print(f"[dim]{prompt}[/dim]")
            self.console.print(f"[dim]  Auto-selected: {result}[/dim]")
            return result

        # Build choices with default selections
        if default:
            checkbox_choices = [
                questionary.Choice(title=c, checked=(c in default))
                for c in choices
            ]
        else:
            checkbox_choices = choices

        result = await questionary.checkbox(
            prompt,
            choices=checkbox_choices,
        ).ask_async()

        return result if result is not None else []

    async def confirm(
        self,
        prompt: str,
        default: bool = True,
    ) -> bool:
        """Present yes/no confirmation prompt.

        In auto_mode, returns the default value.

        Args:
            prompt: Question text to display
            default: Default answer (True = yes)

        Returns:
            True if confirmed, False otherwise
        """
        # In auto mode, return default
        if self.auto_mode:
            self.console.print(f"[dim]{prompt}[/dim]")
            self.console.print(f"[dim]  Auto-confirmed: {'Yes' if default else 'No'}[/dim]")
            return default

        result = await questionary.confirm(
            prompt,
            default=default,
        ).ask_async()

        return result if result is not None else default

    async def select(
        self,
        prompt: str,
        choices: list[str],
        default: str | None = None,
    ) -> str:
        """Present single-select prompt.

        In auto_mode, returns the default or first choice.

        Args:
            prompt: Question text to display
            choices: List of available choices
            default: Pre-selected choice (optional)

        Returns:
            Selected choice string

        Raises:
            ValueError: If choices list is empty
        """
        if not choices:
            raise ValueError("choices cannot be empty")

        # In auto mode, return default or first choice
        if self.auto_mode:
            result = default if default else choices[0]
            self.console.print(f"[dim]{prompt}[/dim]")
            self.console.print(f"[dim]  Auto-selected: {result}[/dim]")
            return result

        result = await questionary.select(
            prompt,
            choices=choices,
            default=default,
        ).ask_async()

        return result if result is not None else choices[0]

    def show_json(
        self,
        data: dict[str, Any],
        title: str | None = None,
    ) -> None:
        """Display formatted JSON panel.

        Uses rich.syntax for syntax highlighting.

        Args:
            data: Dictionary to display as JSON
            title: Optional panel title
        """
        json_str = json.dumps(data, indent=2)
        syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)

        panel_title = f"[bold blue]{title}[/bold blue]" if title else None

        self.console.print(
            Panel(
                syntax,
                title=panel_title,
                border_style="blue",
                padding=(0, 1),
            )
        )

    def show_insight(
        self,
        message: str,
        persona: Persona,
    ) -> None:
        """Display persona-specific insight or commentary.

        Shows a styled panel with persona's emoji and color.

        Args:
            message: Insight message text
            persona: Persona for styling
        """
        insight_text = Text()
        insight_text.append(f"{persona.emoji} ", style="bold")
        insight_text.append(f"{persona.name}'s Insight:\n", style=f"bold {persona.color}")
        insight_text.append(message)

        self.console.print(
            Panel(
                insight_text,
                border_style=persona.color,
                padding=(0, 1),
            )
        )

    def wait_for_continue(
        self,
        message: str = "Press Enter to continue...",
    ) -> None:
        """Wait for user to press Enter.

        Displays message and blocks until Enter is pressed.
        In auto_mode, skips the wait.

        Args:
            message: Prompt message to display
        """
        # In auto mode, skip the wait
        if self.auto_mode:
            self.console.print(f"\n[dim]{message} (auto-skipped)[/dim]")
            return

        self.console.print(f"\n[dim]{message}[/dim]")
        input()
