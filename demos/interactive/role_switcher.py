"""Role switcher for Sarah's Journey interactive demo.

This module provides the RoleSwitcher class that manages transitions
between different stakeholder personas during the demo.
"""

from rich.console import Console

from demos.interactive.personas import PERSONAS, Persona, get_persona
from demos.interactive.prompts import PromptUI


class RoleSwitcher:
    """Manages role switching between personas during the interactive demo.

    Handles transitions between different stakeholder perspectives,
    displaying appropriate banners and maintaining role state.

    Attributes:
        ui: PromptUI instance for display
        current_persona: Currently active Persona
        console: Rich Console for output
    """

    def __init__(
        self,
        ui: PromptUI | None = None,
        console: Console | None = None,
    ) -> None:
        """Initialize the role switcher.

        Args:
            ui: Optional PromptUI instance. Creates new if not provided.
            console: Optional Rich Console. Creates new if not provided.
        """
        self.console = console or Console()
        self.ui = ui or PromptUI(console=self.console)
        # Default starting persona is Sarah (primary demo protagonist)
        self.current_persona = get_persona("sarah")

    def switch_to(
        self,
        persona_id: str,
        step: int,
        title: str,
        show_banner: bool = True,
    ) -> Persona:
        """Switch to a different persona role.

        Displays role banner and updates internal state.

        Args:
            persona_id: ID of persona to switch to (e.g., "sarah", "it_admin")
            step: Current step number (1-10)
            title: Step title for banner display
            show_banner: Whether to display the role banner (default: True)

        Returns:
            The Persona that was switched to

        Raises:
            ValueError: If persona_id is not valid
        """
        if persona_id not in PERSONAS:
            raise ValueError(
                f"Invalid persona_id: '{persona_id}'. "
                f"Valid IDs: {list(PERSONAS.keys())}"
            )

        self.current_persona = get_persona(persona_id)

        if show_banner:
            self.ui.role_banner(self.current_persona, step, title)

        return self.current_persona

    def get_current(self) -> Persona:
        """Get the currently active persona.

        Returns:
            Currently active Persona
        """
        return self.current_persona

    def show_vendor_perspective(
        self,
        step: int,
        title: str,
    ) -> None:
        """Switch to vendor perspective for split-view steps.

        Used for steps 4, 5-6, 9 where vendor sees agent's actions.

        Args:
            step: Current step number
            title: Step title
        """
        self.switch_to("vendor", step, title)

    def show_all_perspectives(
        self,
        step: int,
        title: str,
        personas: list[str] | None = None,
    ) -> None:
        """Show perspectives from multiple personas (round-robin).

        Used for step 10 (audit) where all personas review.

        Args:
            step: Current step number
            title: Step title
            personas: List of persona IDs to cycle through (default: all 5)
        """
        if personas is None:
            personas = list(PERSONAS.keys())

        for persona_id in personas:
            self.switch_to(persona_id, step, title)

    async def prompt_role_switch(
        self,
        available_personas: list[str] | None = None,
    ) -> str:
        """Prompt user to select a persona to switch to.

        Uses PromptUI.select() to let user choose.

        Args:
            available_personas: List of persona IDs to offer (default: all 5)

        Returns:
            Selected persona ID
        """
        if available_personas is None:
            available_personas = list(PERSONAS.keys())

        # Build display choices with emoji and name
        choices = []
        id_map = {}
        for pid in available_personas:
            persona = get_persona(pid)
            display = f"{persona.emoji} {persona.name} ({persona.title})"
            choices.append(display)
            id_map[display] = pid

        selected = await self.ui.select(
            prompt="Select a persona to switch to:",
            choices=choices,
        )

        return id_map[selected]
