# WS-B3 Completion: IAM + API Enablement

**Status:** ✅ Complete
**Date:** 2026-06-24

## Changes
- `infra/terraform/iam.tf`: Added `roles/cloudscheduler.admin` to `runner_roles`
- `infra/terraform/apis.tf`: Added `cloudscheduler.googleapis.com` to `required_apis`

## Acceptance Criteria
- [x] deepsecure-runner SA can manage Cloud Scheduler jobs
- [x] Cloud Scheduler API enabled in project
