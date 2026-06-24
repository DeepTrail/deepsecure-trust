# WS-C3 Completion Report: POST /admin/agents/provision Endpoint

**Task:** WS-C3 — Composite provision API endpoint
**Status:** ✅ Complete
**Date:** 2026-06-24

## Files Modified
- `deeptrail-control/app/api/v1/endpoints/admin_fleet.py`

## Implementation Summary
Added `POST /admin/agents/provision` endpoint that:
- Requires admin auth (`Depends(require_admin)`)
- Delegates to `AgentProvisionService.provision()`
- Returns 201 with agent, config, delegation_template, scheduler_resumed
- Returns 409 on duplicate selector via ProvisionError
- Returns 409 on IntegrityError fallback

## Bug Fix
- Fixed ProvisionError handler to use `exc.status_code` instead of hardcoded 400

## Tests
- 8/8 provision tests pass

## Acceptance Criteria
- [x] Endpoint exists at correct path
- [x] Admin-only access enforced
- [x] Correct status codes (201, 403, 409)
