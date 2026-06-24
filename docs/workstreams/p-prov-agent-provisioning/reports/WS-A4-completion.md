# WS-A4 Completion: Populate created_by on Register

**Status:** ✅ Complete
**Date:** 2026-06-24

## Changes
- `deeptrail-control/app/api/v1/endpoints/agents.py`: Modified `register_agent` to accept optional Authorization header, extract caller email from JWT, set `created_by` and `owner_user_id`

## Acceptance Criteria
- [x] Optional Authorization header parsed for caller identity
- [x] `created_by` and `owner_user_id` set from JWT `sub` claim
- [x] Graceful handling if no token or invalid token (fields stay null)
