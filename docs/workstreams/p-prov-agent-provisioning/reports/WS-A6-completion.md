# WS-A6 Completion: Config Auth Tests

**Status:** ✅ Complete
**Date:** 2026-06-24

## Changes
- `deeptrail-control/tests/api/v1/test_agent_config_auth.py`: 10 tests covering auth enforcement

## Test Results
- 10/10 passing
- Covers: no auth, invalid token, admin read/update, agent self-read, agent cross-read blocked, non-admin blocked

## Acceptance Criteria
- [x] Tests verify 401 for no/invalid auth
- [x] Tests verify admin can GET and PUT config
- [x] Tests verify agent can GET own config but not PUT
- [x] Tests verify agent cannot GET other agent's config
- [x] Tests verify non-admin user gets 403
