# Task Specification: E1 Create Main Interactive Entry Point

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** Interactive Demo Plan - Main Entry Point

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | E1 |
| **Task Name** | Create main interactive entry point |
| **Type** | Demo Script (CLI Application) |
| **Location** | `demos/demo_sarah_journey_interactive.py` |
| **Validates** | Complete interactive demo experience |

---

## Component Specification

### Script: `demo_sarah_journey_interactive.py`

| Field | Value |
|-------|-------|
| **Module** | `demos.demo_sarah_journey_interactive` |
| **Type** | CLI Application |
| **Purpose** | Main entry point orchestrating the interactive demo |
| **Pattern** | Async main with argparse CLI |

---

## CLI Interface

```bash
python demos/demo_sarah_journey_interactive.py [OPTIONS]

Options:
  --persona PERSONA_ID   Start as specific persona [default: sarah]
                         Choices: it_admin, sarah, vendor, agent, security
  --start-step N         Start from step N (1-10) [default: 1]
  --auto                 Auto-advance without user prompts (non-interactive)
  --skip-api             Skip actual API calls (dry run mode)
  -v, --verbose          Enable verbose output
  -h, --help             Show help message
```

### CLI Examples

```bash
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
```

---

## Main Function Specification

```python
import argparse
import asyncio

from demos.interactive import (
    DemoContext,
    PERSONAS,
    get_persona,
)
from demos.interactive.prompts import PromptUI
from demos.interactive.role_switcher import RoleSwitcher
from demos.interactive.api_client import APIClient
from demos.interactive.step_handlers import STEP_HANDLERS


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Interactive Sarah's Journey Demo - DeepSecure Virtual MCP Server"
    )
    parser.add_argument(
        "--persona",
        choices=list(PERSONAS.keys()),
        default="sarah",
        help="Starting persona [default: sarah]",
    )
    parser.add_argument(
        "--start-step",
        type=int,
        choices=range(1, 11),
        default=1,
        help="Start from step N (1-10) [default: 1]",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-advance without user prompts",
    )
    parser.add_argument(
        "--skip-api",
        action="store_true",
        help="Skip actual API calls (dry run)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    return parser.parse_args()


async def run_demo(args: argparse.Namespace) -> None:
    """Run the interactive demo.
    
    Args:
        args: Parsed command-line arguments
    """
    # Initialize components
    ui = PromptUI()
    api = APIClient() if not args.skip_api else None
    switcher = RoleSwitcher(ui=ui)
    
    # Create context
    ctx = DemoContext(
        api=api,
        ui=ui,
        switcher=switcher,
        auto_mode=args.auto,
        verbose=args.verbose,
    )
    
    # Set starting persona
    switcher.switch_to(args.persona, step=args.start_step, title="Starting Demo")
    
    # Run steps
    for step in range(args.start_step, 11):
        handler = STEP_HANDLERS[step]
        await handler(ctx)
        ctx.advance_step()
    
    # Show completion
    ui.show_insight("Demo complete! All 10 steps executed.", get_persona("sarah"))


def main() -> None:
    """Main entry point."""
    args = parse_args()
    asyncio.run(run_demo(args))


if __name__ == "__main__":
    main()
```

---

## Dependencies

| Dependency | Type | Purpose |
|------------|------|---------|
| `argparse` | Standard library | CLI argument parsing |
| `asyncio` | Standard library | Async execution |
| `context` | Internal | DemoContext |
| `personas` | Internal | PERSONAS, get_persona |
| `prompts` | Internal | PromptUI |
| `role_switcher` | Internal | RoleSwitcher |
| `api_client` | Internal | APIClient |
| `step_handlers` | Internal | STEP_HANDLERS registry |

---

## Execution Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    demo_sarah_journey_interactive.py         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  parse_args()   │
                    └────────┬────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │  Initialize Components        │
              │  - PromptUI                   │
              │  - APIClient (or None)        │
              │  - RoleSwitcher               │
              │  - DemoContext                │
              └───────────────┬───────────────┘
                              │
                              ▼
              ┌───────────────────────────────┐
              │  For step in start..10:       │
              │    handler = STEP_HANDLERS[step]
              │    await handler(ctx)         │
              │    ctx.advance_step()         │
              └───────────────┬───────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Show Complete  │
                    └─────────────────┘
```

---

## DemoContext Integration

The main script creates a `DemoContext` with all components:

```python
ctx = DemoContext(
    api=api,           # APIClient for HTTP calls
    ui=ui,             # PromptUI for display
    switcher=switcher, # RoleSwitcher for role changes
    auto_mode=args.auto,
    verbose=args.verbose,
    current_step=args.start_step,
)
```

---

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Backend unavailable | Show error message, offer to continue in skip-api mode |
| User cancels (Ctrl+C) | Graceful exit with summary of completed steps |
| Invalid step number | argparse rejects with error message |
| Step handler fails | Show error, offer retry or skip |

---

## File Location Rules

| Artifact | Correct Location |
|----------|------------------|
| Implementation | `demos/demo_sarah_journey_interactive.py` |
| Tests | N/A (demo script, manual testing) |

---

## Contract Verification Checklist

Before marking implementation complete, verify:

### CLI Interface
- [ ] `--persona` accepts all 5 persona IDs
- [ ] `--start-step` accepts 1-10
- [ ] `--auto` runs without prompts
- [ ] `--skip-api` runs without API calls
- [ ] `-v/--verbose` enables verbose output
- [ ] `-h/--help` shows help message

### Component Integration
- [ ] Creates PromptUI instance
- [ ] Creates APIClient instance (unless --skip-api)
- [ ] Creates RoleSwitcher instance
- [ ] Creates DemoContext with all components

### Execution Flow
- [ ] Runs all 10 steps in order
- [ ] Respects --start-step for partial runs
- [ ] Calls correct handler for each step
- [ ] Advances context step after each handler

### Error Handling
- [ ] Graceful exit on Ctrl+C
- [ ] Meaningful error messages
- [ ] Offers recovery options

---

## Usage Examples

### Full Interactive Demo

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
python demos/demo_sarah_journey_interactive.py
```

### Quick Test Run

```bash
python demos/demo_sarah_journey_interactive.py --auto --skip-api
```

### Resume from Step 5

```bash
python demos/demo_sarah_journey_interactive.py --start-step 5
```

### Vendor Perspective

```bash
python demos/demo_sarah_journey_interactive.py --persona vendor
```

---

## Technical Requirements

| Requirement | Value |
|-------------|-------|
| Python version | 3.10+ |
| Async | Required (asyncio.run) |
| Internal deps | All Batch 1-3 components |
| Type hints | Required on all functions |
| Docstrings | Required on all functions |

---

## References

- **Design Doc:** Interactive Demo Plan
- **Related Specs:** All previous specs (A1-D1)
- **Upstream Dependencies:** A1, A2, A3, B1, B2, C1, D1
- **Downstream Dependents:** F1 (README documentation)
