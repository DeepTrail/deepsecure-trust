# P-PROV Agent Provisioning & Goal Management: Task Status

> **Global Status:** [EXECUTION_STATUS.md](../../EXECUTION_STATUS.md) ← Portfolio overview
>
> **Workstream Details:** [WORKSTREAM.md](./WORKSTREAM.md)
>
> **Last Updated:** June 24, 2026

---

## Current Task Overview

| Metric | Value |
|--------|-------|
| **Current Batch** | Batch 1 ✅ Complete → Batch 2 |
| **Tasks Complete** | 12/27 (44%) |
| **Tasks In Progress** | 0 |
| **Tasks Ready** | 3 (C1, C2, C4 — Wave 1 of Batch 2) |
| **Tasks Blocked** | 0 |
| **Active Worktrees** | 0 (single-branch) |
| **Contract Verified** | ✅ |
| **Files at Correct Location** | ✅ |
| **E2E Tests Passing** | ✅ 18/18 |

---

## Verification Status (BLOCKING)

| Check | Status | Notes |
|-------|--------|-------|
| Config endpoints have auth | ✅ Complete | WS-A1 + WS-A2 |
| Endpoints match design spec | ✅ Complete | Audited in Step 6 |
| Test endpoints match impl | ✅ Complete | 18/18 passing |
| Async fixtures correct | ✅ N/A | Sync tests only in B1 |
| All tests passing | ✅ Complete | 18 tests pass |

---

## Batch Progress

```
Batch 1  [██████████] 100%  ✅ COMPLETE (Phase A: Security + SA Pool)
Batch 2  [░░░░░░░░░░] 0%   ← CURRENT (Phase B: Composite Provisioning + Prompt RBAC)
Batch 3  [░░░░░░░░░░] 0%   (blocked by Batch 2 / MP2)
```

---

## Current Batch: Batch 1 — Phase A: Security Fix + SA Pool ✅ COMPLETE

| Task ID | Task Name | Status | Wave | Deps |
|---------|-----------|--------|------|------|
| WS-A1 | `get_admin_or_agent_self` auth dependency | ✅ Complete | 1 | None |
| WS-A3 | Agent model ownership + Alembic migration | ✅ Complete | 1 | None |
| WS-A5 | `TaggedPrompt.added_by` field | ✅ Complete | 1 | None |
| WS-B1 | `agent_slots.tf` Terraform resources | ✅ Complete | 1 | None |
| WS-B3 | Runner SA `cloudscheduler.admin` IAM | ✅ Complete | 1 | None |
| WS-B4 | `AGENT_SLOTS_JSON` config setting | ✅ Complete | 1 | None |
| WS-A2 | Add auth to config endpoints | ✅ Complete | 2 | A1 |
| WS-A4 | Set `created_by` on register | ✅ Complete | 2 | A3 |
| WS-B2 | `variables.tf` + `terraform.tfvars` slot count | ✅ Complete | 2 | B1 |
| WS-B5 | `GET /admin/agent-slots` endpoint | ✅ Complete | 2 | B4 |
| WS-A6 | Auth enforcement tests | ✅ Complete | 3 | A1, A2 |
| WS-B6 | `GET /admin/health/agents` endpoint + tests | ✅ Complete | 3 | B3 |

---

## Workstream Status

| WS | Name | Status | Progress | Tasks Done |
|----|------|--------|----------|------------|
| **A** | Security Fix + Ownership | ✅ Complete | 100% | 6/6 |
| **B** | SA Identity Pool | ✅ Complete | 100% | 6/6 |
| **C** | Composite Provisioning + Prompts | ⏳ Ready (MP1 done) | 0% | 0/9 |
| **D** | Frontend (Wizard + Goals + My Agents) | ⏸️ Blocked (MP2) | 0% | 0/6 |

---

## Merge Points Status

| Point | Converging Tasks | Status | Merged At |
|-------|------------------|--------|-----------|
| **MP1** | WS-A (all 6) + WS-B (all 6) | ✅ Complete | 2026-06-24 |
| **MP2** | WS-C (all 9) | ⏸️ Pending | — |

---

## All Tasks by Status

### ✅ Completed (12)

| Task ID | Task Name | Completed | Report |
|---------|-----------|-----------|--------|
| WS-A1 | `get_admin_or_agent_self` auth dependency | 2026-06-24 | [report](./reports/WS-A1-completion.md) |
| WS-A2 | Add auth to config endpoints | 2026-06-24 | [report](./reports/WS-A2-completion.md) |
| WS-A3 | Agent model ownership + migration | 2026-06-24 | [report](./reports/WS-A3-completion.md) |
| WS-A4 | Set `created_by` on register | 2026-06-24 | [report](./reports/WS-A4-completion.md) |
| WS-A5 | `TaggedPrompt.added_by` field | 2026-06-24 | [report](./reports/WS-A5-completion.md) |
| WS-A6 | Auth enforcement tests | 2026-06-24 | [report](./reports/WS-A6-completion.md) |
| WS-B1 | `agent_slots.tf` Terraform resources | 2026-06-24 | [report](./reports/WS-B1-completion.md) |
| WS-B2 | `variables.tf` slot count variable | 2026-06-24 | [report](./reports/WS-B2-completion.md) |
| WS-B3 | Runner SA IAM + API enablement | 2026-06-24 | [report](./reports/WS-B3-completion.md) |
| WS-B4 | `AGENT_SLOTS_JSON` config setting | 2026-06-24 | [report](./reports/WS-B4-completion.md) |
| WS-B5 | `GET /admin/agent-slots` endpoint | 2026-06-24 | [report](./reports/WS-B5-completion.md) |
| WS-B6 | `GET /admin/health/agents` + tests | 2026-06-24 | [report](./reports/WS-B6-completion.md) |

### 🔄 In Progress (0)

| Task ID | Task Name | Started | Worktree |
|---------|-----------|---------|----------|
| _None_ | — | — | — |

### ⏳ Ready (3)

| Task ID | Task Name | Batch | Wave |
|---------|-----------|-------|------|
| WS-C1 | `provision_service.py` (atomic) | 2 | 1 |
| WS-C2 | Provision schemas | 2 | 1 |
| WS-C4 | `prompt_validation.py` | 2 | 1 |

### ⏸️ Pending (12)

<details>
<summary>Click to expand pending tasks</summary>

| Task ID | Task Name | Batch | Blocked By |
|---------|-----------|-------|------------|
| WS-C3 | `POST /admin/agents/provision` | 2 | C1, C2, B5 |
| WS-C5 | `GET /agents/{id}/prompts` | 2 | C4 |
| WS-C6 | `POST /agents/{id}/prompts` | 2 | C4, C5 |
| WS-C7 | `DELETE /agents/{id}/prompts/{index}` | 2 | C5 |
| WS-C8 | `PUT /agents/{id}/prompts` | 2 | C5 |
| WS-C9 | Provision + prompt RBAC tests | 2 | C3, C6, C7 |
| WS-D1 | My Agents / All Agents tab bar | 3 | C5 (MP2) |
| WS-D2 | `ProvisionWizard` (6-step) | 3 | B5, C3 (MP2) |
| WS-D3 | Create page wizard/quick-register tabs | 3 | D2 |
| WS-D4 | `PromptEditor` with service autocomplete | 3 | C5, C6 (MP2) |
| WS-D5 | Goals page | 3 | D4 |
| WS-D6 | Frontend integration tests | 3 | D1-D5 |

</details>

### 🚫 Blocked (0)

| Task ID | Task Name | Blocked By | Reason |
|---------|-----------|------------|--------|
| _None_ | — | — | — |

---

## Blockers & Issues

| ID | Description | Blocking | Severity | Status | Resolution |
|----|-------------|----------|----------|--------|------------|
| _None_ | — | — | — | — | — |

---

## Quick Commands Reference

### Execute Tasks
```bash
/run-batch P0-B2 p-prov-agent-provisioning --continue --auto-heal
```

### Run Quality Checks
```bash
cd deeptrail-control && python -m pytest tests/api/v1/test_agent_config_auth.py tests/api/v1/test_agent_slots.py -v
cd infra/terraform && terraform validate
```

---

## Status Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Complete |
| 🔄 | In Progress |
| ⏳ | Ready (can start) |
| ⏸️ | Pending (waiting on dependencies) |
| 🚫 | Blocked (external issue) |
