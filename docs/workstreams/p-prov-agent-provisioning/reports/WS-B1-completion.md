# WS-B1 Completion: Terraform agent_slots.tf

**Status:** ✅ Complete
**Date:** 2026-06-24

## Changes
- `infra/terraform/agent_slots.tf`: Created with SA, IAM, Cloud Run Job, Cloud Scheduler, and `agent_slots_json` output

## Acceptance Criteria
- [x] `google_service_account` with count-based naming
- [x] IAM bindings for run.developer, secretmanager.secretAccessor, iam.serviceAccountTokenCreator, run.invoker
- [x] Cloud Run Job per slot with agent container image
- [x] Cloud Scheduler per slot (paused by default)
- [x] `agent_slots_json` output for env var injection
- [x] `terraform validate` passes
