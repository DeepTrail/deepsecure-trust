# Create Workstream

Create a new workstream folder structure with overview document.

## Instructions

1. **Get workstream information from the user:**
   - Feature name (for folder: `docs/workstreams/[feature-name]/`)
   - Workstream ID (e.g., WS-A)
   - Workstream name/description
   - Link to parent design document
   - List of planned tasks (if known)

2. **Create the directory structure:**
   ```
   docs/workstreams/[feature-name]/
   ├── WORKSTREAM.md
   ├── STATUS.md           ← Execution progress tracking
   ├── tasks/
   │   └── .gitkeep
   └── reports/
       └── .gitkeep
   ```

2b. **Create git worktrees (if parallel execution):**
   ```bash
   # Create worktrees from dev branch (not main)
   git worktree add ../[worktree-name] -b feature/[branch-name] dev
   
   # Example:
   git worktree add ../vmcp-control -b feature/vmcp-control dev
   git worktree add ../vmcp-gateway -b feature/vmcp-gateway dev
   ```

2c. **Copy .cursor/commands to each worktree:**
   
   Cursor commands are only available in the main repo's `.cursor/` folder.
   For commands to work in worktrees, copy the folder:
   
   ```bash
   # For each worktree created:
   cp -r .cursor ../[worktree-name]/
   
   # Example:
   cp -r .cursor ../vmcp-control/
   cp -r .cursor ../vmcp-gateway/
   ```
   
   **Why:** Git worktrees share git history but NOT working directory files like `.cursor/`.
   Commands like `/execute-task` won't be found without this copy.

3. **Create WORKSTREAM.md** from template with:
   - All metadata filled in
   - **Batch assignments** (which batches this workstream's tasks belong to)
   - **Merge point dependencies** (which merge points this workstream contributes to or depends on)
   - Parallelization notes (what can run parallel, what's blocked)
   - Initial task table (can be empty or populated)
   - Files affected section
   - Risk assessment if applicable

4. **Update the workstreams README:**
   - Add entry to "Active Workstreams" table in `docs/workstreams/README.md`

5. **Update status files:**
   
   a. **Update `docs/EXECUTION_STATUS.md`** (global portfolio):
      - Add design to "Active Designs" if not present
      - Set phase to "Phase 2: Planning"
      - Link to `docs/workstreams/[design-name]/STATUS.md` for detailed tracking

## Template Location
`docs/workstreams/WORKSTREAM_TEMPLATE.md`

## Output Format

```markdown
## Workstream Created

**Location:** `docs/workstreams/[feature-name]/`

### Structure
```
[feature-name]/
├── WORKSTREAM.md      ✅ Created
├── tasks/             ✅ Created
└── reports/           ✅ Created
```

### Workstream Details
- **ID:** WS-[X]
- **Name:** [Workstream Name]
- **Design Doc:** [link]
- **Status:** planning
- **Batches:** [1, 2, 3] (which batches this workstream spans)
- **Contributes to Merge Point:** [MP1, or N/A]
- **Depends on Merge Point:** [MP2, or N/A]

### Next Steps
1. Review and refine the task breakdown in WORKSTREAM.md
2. Create individual task tickets with `/create-task-ticket`
3. Begin execution of ready tasks

---

Workstream is ready for task ticket creation.
```

## Example Usage

User: "Create a workstream for the MCP gateway token service feature"

Then create:
```
docs/workstreams/mcp-gateway-token-service/
├── WORKSTREAM.md
├── tasks/
└── reports/
```
