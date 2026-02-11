"""Interactive demo for Sarah's Journey - DeepSecure Virtual MCP Server."""

from demos.interactive.api_client import APIClient
from demos.interactive.context import DemoContext, STEP_PRIMARY_PERSONA
from demos.interactive.personas import (
    PERSONAS,
    Persona,
    get_persona,
    get_personas_for_step,
    get_primary_persona_for_step,
)
from demos.interactive.prompts import PromptUI
from demos.interactive.role_switcher import RoleSwitcher
from demos.interactive.step_handlers import (
    STEP_HANDLERS,
    StepHandler,
    run_all_steps,
    run_step,
)

__all__ = [
    # Context (A2)
    "DemoContext",
    "STEP_PRIMARY_PERSONA",
    # Personas (A1)
    "Persona",
    "PERSONAS",
    "get_persona",
    "get_personas_for_step",
    "get_primary_persona_for_step",
    # API Client (C1)
    "APIClient",
    # Prompts (B1)
    "PromptUI",
    # Role Switcher (B2)
    "RoleSwitcher",
    # Step Handlers (D1)
    "STEP_HANDLERS",
    "StepHandler",
    "run_step",
    "run_all_steps",
]
