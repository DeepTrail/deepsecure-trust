# WS-C5 Completion Report: Prompt CRUD Endpoints

**Task:** WS-C5 — GET/POST/DELETE prompt endpoints with delegation-based RBAC
**Status:** ✅ Complete
**Date:** 2026-06-24

## Files Modified
- `deeptrail-control/app/api/v1/endpoints/agents.py`

## Endpoints Added
- `GET /agents/{id}/prompts` — List prompts (requires delegation or admin)
- `POST /agents/{id}/prompts` — Add prompt (validates service tags against delegation)
- `DELETE /agents/{id}/prompts/{index}` — Delete prompt (author or admin only)

## RBAC Logic
- Admin: full access to all prompt operations
- Delegated user: can view prompts, add prompts for delegated services only
- Non-delegated user: 403 Forbidden
- Delete: only prompt author or admin

## Tests
- 11/11 prompt tests pass

## Acceptance Criteria
- [x] CRUD endpoints with correct RBAC
- [x] Service tag validation via prompt_validation service
- [x] added_by tracking on new prompts
- [x] Author-only deletion (or admin override)
