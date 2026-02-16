# Task: F1 Update README with Interactive Demo Docs

## Metadata

| Field | Value |
|-------|-------|
| **Task ID** | F1 |
| **Status** | `pending` |
| **Dependencies** | E1 (main entry point) |
| **Complexity** | S (Small) |
| **Batch** | 4 |
| **Wave** | 2 (after E1) |
| **Worktree** | deepsecure-mvp (main repo) |

---

## Specification

> **No spec required** - Documentation-only task

---

## Pre-Conditions

- [ ] E1 complete: Main interactive entry point exists at `demos/demo_sarah_journey_interactive.py`
- [ ] Demo is functional and can be run with `--help`

---

## Task Description

Update the demos README to document the new interactive demo:

### 1. Update `demos/README.md`

Add a section documenting the interactive demo with:
- Overview and purpose
- Prerequisites
- Installation (if any additional deps needed)
- Usage examples with all CLI options
- Persona descriptions
- Step descriptions

### 2. Content to Add

```markdown
## Interactive Sarah's Journey Demo

An interactive version of Sarah's Journey that lets you experience the demo from multiple stakeholder perspectives.

### Features

- **5 Personas**: Switch between IT Admin, Sarah (Developer), Vendor, Agent, and Security Officer
- **10 Steps**: Complete journey from org setup to audit review
- **Interactive Prompts**: Make choices at each step
- **Split Views**: See actions from both user and vendor perspectives
- **Auto Mode**: Run without prompts for quick testing

### Prerequisites

- Python 3.10+
- Backend services running (or use `--skip-api` for dry run)
- `pip install rich questionary`

### Usage

```bash
# Full interactive demo
python demo_sarah_journey_interactive.py

# Start as specific persona
python demo_sarah_journey_interactive.py --persona it_admin

# Start from a specific step
python demo_sarah_journey_interactive.py --start-step 5

# Quick test (no API calls, no prompts)
python demo_sarah_journey_interactive.py --auto --skip-api

# Show all options
python demo_sarah_journey_interactive.py --help
```

### CLI Options

| Option | Description | Default |
|--------|-------------|---------|
| `--persona` | Starting persona | `sarah` |
| `--start-step` | Start from step N (1-10) | `1` |
| `--auto` | Auto-advance without prompts | off |
| `--skip-api` | Skip API calls (dry run) | off |
| `-v, --verbose` | Verbose output | off |

### Personas

| ID | Name | Role |
|----|------|------|
| `it_admin` | Alex Martinez | IT Administrator |
| `sarah` | Sarah Chen | Developer |
| `vendor` | Jordan Lee | AI Agent Vendor |
| `agent` | SDR-Assistant | AI Agent |
| `security` | Morgan Taylor | Security Officer |

### Steps Overview

1. **Organization Setup** (IT Admin) - Create org and project
2. **Install SDK** (Sarah) - Set up DeepSecure SDK
3. **Connect Tools** (Sarah) - Add external providers
4. **Create Agent** (Sarah + Vendor) - Create agent identity
5. **Register Agent** (Sarah + Vendor) - Agent handshake
6. **Grant Permissions** (Sarah + Vendor) - Configure access
7. **Make API Calls** (Sarah) - Use gateway proxy
8. **Agent Runtime** (Agent) - Agent fetches credentials
9. **Credential Rotation** (Sarah + Vendor) - Rotate secrets
10. **Audit Review** (All) - Review audit log
```

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `demos/README.md` | Modify | Add interactive demo documentation |

---

## Acceptance Criteria

### Documentation Content
- [ ] Overview section explains the interactive demo
- [ ] Features list covers all key capabilities
- [ ] Prerequisites section includes Python version and dependencies
- [ ] Usage section shows basic command
- [ ] CLI Options table documents all flags
- [ ] Personas table lists all 5 personas with IDs and names
- [ ] Steps overview lists all 10 steps with primary persona

### Examples
- [ ] At least 4 usage examples covering common scenarios
- [ ] Examples are copy-paste ready
- [ ] `--help` example included

### Formatting
- [ ] Markdown renders correctly
- [ ] Code blocks use correct syntax highlighting
- [ ] Tables are properly aligned
- [ ] Headers follow existing README style

---

## Post-Conditions

After this task:
- Users can discover and understand the interactive demo
- Documentation matches the actual CLI options from E1
- All personas and steps are documented

---

## Validation Mapping

| Validates | Description |
|-----------|-------------|
| **Demo** | Documentation for interactive demo |
| **User Journey** | N/A (documentation) |

---

## Test Commands

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp

# Verify README was updated
grep -q "Interactive Sarah's Journey" demos/README.md && echo "✅ Section added"

# Verify all CLI options are documented
grep -q "\-\-persona" demos/README.md && echo "✅ --persona documented"
grep -q "\-\-start-step" demos/README.md && echo "✅ --start-step documented"
grep -q "\-\-auto" demos/README.md && echo "✅ --auto documented"
grep -q "\-\-skip-api" demos/README.md && echo "✅ --skip-api documented"
```

---

## Execution Command

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
/execute-task F1 interactive-demo
```

---

## References

- **Related Tasks:** E1 (main entry point - dependency)
- **Existing Docs:** `demos/README.md`
- **E1 Spec:** [E1-spec.md](../specs/E1-spec.md) - for CLI options reference
