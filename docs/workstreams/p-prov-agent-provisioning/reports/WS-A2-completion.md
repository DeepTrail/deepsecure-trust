# WS-A2 Completion: Apply Auth to Config Endpoints

**Status:** ✅ Complete
**Date:** 2026-06-24

## Changes
- `deeptrail-control/app/api/v1/endpoints/agents.py`: Added `Depends(get_admin_or_agent_self)` to `get_agent_config`, `Depends(require_admin)` to `update_agent_config`

## Acceptance Criteria
- [x] GET /agents/{id}/config requires admin or agent-self JWT
- [x] PUT /agents/{id}/config requires admin only
- [x] Unauthenticated requests return 401/422
