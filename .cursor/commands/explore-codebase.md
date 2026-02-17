# Explore Codebase Before Breakdown

Inventory existing implementations in the codebase BEFORE creating a task breakdown.

## Purpose

Design documents describe **intent**, not **current state**. Coverage matrices and gap analyses become stale as development continues. This command ensures you understand what **actually exists** before scoping work.

## ⚠️ Why This Matters

**Feb 2026 Lesson:** A breakdown was created for "MVP Production Readiness" based on design documents. The design docs said certain endpoints were "missing." After exploration, ~60% of "missing" components **already existed**. The breakdown was over-scoped by 60%.

## Instructions

1. **Read the design document** to understand what features are expected

2. **Identify which services are involved** (e.g., deeptrail-control, deeptrail-gateway, SDK)

3. **Explore each service using parallel Task agents:**

   For `deeptrail-control/`:
   ```
   Use Task tool with subagent_type="explore" and prompt:
   "Inventory all existing implementations in deeptrail-control/:
   - List all API endpoints in app/api/v1/endpoints/ (method, path, handler)
   - List all services in app/services/ (class name, key methods)
   - List all models in app/models/ (model name, key fields)
   - List all middleware
   - Note any MVP-mode vs production-mode code paths"
   ```

   For `deeptrail-gateway/`:
   ```
   Use Task tool with subagent_type="explore" and prompt:
   "Inventory all existing implementations in deeptrail-gateway/:
   - List all MCP handlers in app/mcp/ (handler name, method type)
   - List all middleware in app/middleware/ (name, purpose)
   - List all backend clients in app/backends/ (client name, external service)
   - List security modules in app/security/
   - Note any MVP-mode vs production-mode code paths"
   ```

4. **Cross-reference design doc requirements with codebase:**

   For each "missing" or "to be implemented" item in the design doc:
   - Search codebase: `grep -r "endpoint_name" service/`
   - Check if basic implementation exists
   - Determine if it needs: Create / Modify / Verify / Skip

5. **Create CODEBASE_ANALYSIS.md:**

   Save to: `docs/workstreams/[feature-name]/CODEBASE_ANALYSIS.md`

   ```markdown
   # Codebase Analysis for: [Feature Name]
   
   ## Analysis Date: [date]
   
   ## Services Explored
   - [ ] deeptrail-control/
   - [ ] deeptrail-gateway/
   - [ ] deepsecure/ (SDK)
   
   ## Existing Implementations
   
   ### deeptrail-control
   
   | Component | Type | Location | Status |
   |-----------|------|----------|--------|
   | User login | Endpoint | app/api/v1/endpoints/auth.py | EXISTS - MVP mode |
   | UserService | Service | app/services/user_service.py | EXISTS |
   | ... | ... | ... | ... |
   
   ### deeptrail-gateway
   
   | Component | Type | Location | Status |
   |-----------|------|----------|--------|
   | tools/call handler | MCP Handler | app/mcp/handlers.py | EXISTS |
   | credential_injection | Middleware | app/middleware/credential_injection.py | EXISTS - mock tokens |
   | ... | ... | ... | ... |
   
   ## Design Doc "Missing" vs Actual Status
   
   | Design Doc Says | Actual Codebase Status | Task Type |
   |-----------------|------------------------|-----------|
   | "Create login endpoint" | EXISTS at /api/v1/auth/login | Verify |
   | "Create delegation service" | EXISTS with macaroons | Modify |
   | "Create OAuth flow" | NOT IMPLEMENTED | Create |
   | ... | ... | ... |
   
   ## True Implementation Gaps
   
   Only items that genuinely don't exist:
   1. [list]
   
   ## Verification Tasks
   
   Items that exist but need verification against requirements:
   1. [list]
   
   ## Modification Tasks
   
   Items that exist but need format/behavior changes:
   1. [list]
   
   ## Components NOT Needed for MVP
   
   Advanced features that are implemented but not required for MVP scope:
   1. [e.g., split-key secret storage - exists but OAuth tokens don't need it]
   2. [e.g., full macaroon attenuation chains - exists but MVP uses simpler delegation]
   ```

6. **Summarize findings** for the user:

   ```
   ## Exploration Summary
   
   | Category | Count |
   |----------|-------|
   | Components that EXIST | X |
   | True implementation gaps | Y |
   | Verification-only tasks | Z |
   | Modification tasks | W |
   
   **Recommendation:** The actual scope is ~[N]% smaller than design doc suggests.
   ```

7. **Proceed to breakdown** with accurate task classification

## Output

- `docs/workstreams/[feature-name]/CODEBASE_ANALYSIS.md`

## When to Use

- ALWAYS before `/breakdown-design`
- When design docs reference "missing" components
- When coverage matrices seem potentially stale
- When starting work on an existing codebase

## Anti-Patterns to Avoid

| Bad | Good |
|-----|------|
| Trust design doc "Not Implemented" labels | Grep codebase to verify |
| Assume coverage matrix is current | Compare matrix date vs recent commits |
| Create breakdown without exploration | Explore → Analyze → Breakdown |
| Skip exploration for "small" changes | Even small changes benefit from verification |

## Reference

See also:
- `docs/DEVELOPER_WORKFLOW.md` - Phase 0.5: Codebase Exploration
- `docs/CLAUDE.md` - Common Pitfalls: API Contract Verification
