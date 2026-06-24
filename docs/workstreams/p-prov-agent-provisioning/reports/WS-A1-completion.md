# WS-A1 Completion: `get_admin_or_agent_self` Auth Dependency

**Status:** ✅ Complete
**Date:** 2026-06-24

## Changes
- `deeptrail-control/app/middleware/admin_auth.py`: Added `get_admin_or_agent_self` function with `Path` dependency injection for `agent_id`

## Acceptance Criteria
- [x] Function accepts admin user token or agent JWT (self-match on `sub` == path `agent_id`)
- [x] Returns `access_type: "admin"` or `access_type: "agent_self"`
- [x] Non-matching agents get 403 via `require_admin` fallthrough
