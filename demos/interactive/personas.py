"""Persona definitions for Sarah's Journey interactive demo.

This module defines the 5 stakeholder personas who participate in the
DeepSecure Virtual MCP Server demonstration.
"""

from dataclasses import dataclass


@dataclass
class Persona:
    """Represents a stakeholder persona in the interactive demo.

    Each persona has a unique perspective on the DeepSecure Virtual MCP Server
    and participates in specific steps of Sarah's Journey.

    Attributes:
        id: Unique identifier used as dictionary key (e.g., "it_admin")
        name: Display name shown in UI (e.g., "IT Admin")
        title: Full role title (e.g., "Enterprise Administrator")
        color: Rich library color for terminal display (e.g., "blue")
        emoji: Emoji for visual identification in banners
        steps: List of journey step numbers this persona participates in
    """

    id: str
    name: str
    title: str
    color: str
    emoji: str
    steps: list[int]


PERSONAS: dict[str, Persona] = {
    "it_admin": Persona(
        id="it_admin",
        name="IT Admin",
        title="Enterprise Administrator",
        color="blue",
        emoji="🔧",
        steps=[1],
    ),
    "sarah": Persona(
        id="sarah",
        name="Sarah",
        title="Sales Development Representative",
        color="green",
        emoji="👩‍💼",
        steps=[2, 3, 4, 10],
    ),
    "vendor": Persona(
        id="vendor",
        name="AI Agent Vendor",
        title="Third-Party AI Platform Provider",
        color="yellow",
        emoji="🏭",
        steps=[4, 5, 6, 9, 10],
    ),
    "agent": Persona(
        id="agent",
        name="SDR-Assistant",
        title="AI Agent (running on vendor infrastructure)",
        color="cyan",
        emoji="🤖",
        steps=[5, 6, 7, 8, 9],
    ),
    "security": Persona(
        id="security",
        name="Security Officer",
        title="Enterprise Security & Compliance",
        color="red",
        emoji="🛡️",
        steps=[9, 10],
    ),
}


def get_persona(persona_id: str) -> Persona:
    """Get persona by ID, raising KeyError if not found."""
    return PERSONAS[persona_id]


def get_personas_for_step(step: int) -> list[Persona]:
    """Get all personas that participate in a given step."""
    return [p for p in PERSONAS.values() if step in p.steps]


def get_primary_persona_for_step(step: int) -> Persona:
    """Get the primary (first) persona for a step."""
    personas = get_personas_for_step(step)
    if not personas:
        raise ValueError(f"No persona defined for step {step}")
    return personas[0]
