# Task: E1 Create Main Interactive Entry Point

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | E1 |
| **Status** | `pending` |
| **Dependencies** | D1 (step handlers) |
| **Complexity** | M (Medium) |
| **Batch** | 4 |
| **Wave** | 1 (first in batch) |
| **Worktree** | deepsecure-mvp (main repo) |

---

## Specification

> See full specification: [E1-spec.md](../specs/E1-spec.md)

### Key Contracts

| Contract | Value |
|----------|-------|
| **Module** | `demos.demo_sarah_journey_interactive` |
| **Type** | CLI Application |
| **File** | `demos/demo_sarah_journey_interactive.py` |
| **Pattern** | Async main with argparse CLI |

### CLI Interface

```bash
python demos/demo_sarah_journey_interactive.py [OPTIONS]

Options:
  --persona PERSONA_ID   Start as specific persona [default: sarah]
  --start-step N         Start from step N (1-10) [default: 1]
  --auto                 Auto-advance without user prompts
  --skip-api             Skip actual API calls (dry run)
  -v, --verbose          Enable verbose output
  -h, --help             Show help message
```

---

## Pre-Conditions

- [x] A1 complete: Persona dataclass and PERSONAS
- [x] A2 complete: DemoContext state manager
- [x] A3 complete: Package __init__.py
- [x] B1 complete: PromptUI class
- [x] B2 complete: RoleSwitcher class
- [x] C1 complete: APIClient class
- [ ] D1 complete: Step handlers (STEP_HANDLERS registry)

---

## Task Description

Create the main entry point script that orchestrates the interactive demo:

### 1. Create the Script

Create `demos/demo_sarah_journey_interactive.py` with:
- Argparse CLI for options
- Async main function
- Integration with all components

### 2. Implement CLI Parsing

```python
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(...)
    parser.add_argument("--persona", ...)
    parser.add_argument("--start-step", ...)
    parser.add_argument("--auto", ...)
    parser.add_argument("--skip-api", ...)
    parser.add_argument("-v", "--verbose", ...)
    return parser.parse_args()
```

### 3. Implement Main Flow

```python
async def run_demo(args: argparse.Namespace) -> None:
    # Initialize components
    ui = PromptUI()
    api = APIClient() if not args.skip_api else None
    switcher = RoleSwitcher(ui=ui)
    
    # Create context with all components
    ctx = DemoContext(api=api, ui=ui, switcher=switcher, ...)
    
    # Run steps from start_step to 10
    for step in range(args.start_step, 11):
        handler = STEP_HANDLERS[step]
        await handler(ctx)
        ctx.advance_step()
```

### 4. Error Handling

- Graceful exit on Ctrl+C
- Backend unavailable: offer skip-api mode
- Step failure: offer retry or skip

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `demos/demo_sarah_journey_interactive.py` | Create | Main CLI entry point |

---

## Acceptance Criteria

### CLI Interface
- [ ] `--persona` accepts all 5 persona IDs: it_admin, sarah, vendor, agent, security
- [ ] `--persona` defaults to "sarah"
- [ ] `--start-step` accepts integers 1-10
- [ ] `--start-step` defaults to 1
- [ ] `--auto` runs without user prompts
- [ ] `--skip-api` runs without making API calls
- [ ] `-v/--verbose` enables verbose output
- [ ] `-h/--help` shows help message with all options

### Component Integration
- [ ] Creates PromptUI instance
- [ ] Creates APIClient instance (unless --skip-api)
- [ ] Creates RoleSwitcher instance with PromptUI
- [ ] Creates DemoContext with all components
- [ ] Passes auto_mode and verbose flags to DemoContext

### Execution Flow
- [ ] Runs all steps from start_step to 10
- [ ] Uses STEP_HANDLERS registry to get handlers
- [ ] Calls each handler with DemoContext
- [ ] Calls ctx.advance_step() after each handler
- [ ] Shows completion message when done

### Error Handling
- [ ] Graceful exit on Ctrl+C (KeyboardInterrupt)
- [ ] Catches and displays API errors
- [ ] Offers recovery options on failure

### Code Quality
- [ ] Type hints on all functions
- [ ] Docstrings on all functions
- [ ] Async pattern with asyncio.run()
- [ ] Script executable with `if __name__ == "__main__"`

---

## Post-Conditions

After this task:
- Interactive demo can be run from command line
- All 10 steps execute in sequence
- User can customize persona, start step, and mode

---

## Validation Mapping

| Validates | Description |
|-----------|-------------|
| **Demo** | Complete interactive Sarah's Journey demo |
| **User Journey** | All 10 steps from org setup to audit review |

---

## Test Commands

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp

# Show help
python demos/demo_sarah_journey_interactive.py --help

# Quick test (no API calls, no prompts)
python demos/demo_sarah_journey_interactive.py --auto --skip-api

# Start from step 5
python demos/demo_sarah_journey_interactive.py --start-step 5 --auto --skip-api

# Full interactive (requires backend)
python demos/demo_sarah_journey_interactive.py
```

---

## Execution Command

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
/execute-task E1 interactive-demo
```

---

## References

- **Design Doc:** Interactive Demo Plan
- **Specification:** [E1-spec.md](../specs/E1-spec.md)
- **Related Tasks:** All Batch 1-3 tasks (dependencies)
- **Downstream:** F1 (README documentation)
