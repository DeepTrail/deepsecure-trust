# WS-A5 Completion: `added_by` Field in TaggedPrompt Schema

**Status:** ✅ Complete
**Date:** 2026-06-24

## Changes
- `deeptrail-control/app/schemas/agent.py`: Added `added_by: Optional[str]` to `TaggedPrompt` Pydantic model

## Acceptance Criteria
- [x] `added_by` field is Optional[str], defaults to None
- [x] Description documents purpose (user who added, null for legacy)
- [x] No breaking change to existing API consumers (field is optional)
