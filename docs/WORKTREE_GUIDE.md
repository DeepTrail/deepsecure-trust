# Git Worktree Guide for DeepSecure Development

> **Purpose**: How to use git worktrees for parallel feature development across `deeptrail-control` and `deeptrail-gateway`.

---

## What Are Worktrees?

Git worktrees let you check out multiple branches simultaneously in separate directories. They share the same `.git` history but have independent working directories. This enables parallel development on different services without branch switching.

```
/Users/imaxxs/repositories/
├── deepsecure-mvp/              ← Main repo (dev branch)
├── idp-sso-control/             ← Worktree (feature/idp-sso-control branch)
└── idp-sso-gateway/             ← Worktree (feature/idp-sso-gateway branch)
```

All three share the same git history. A commit in any directory is visible from any other.

---

## 1. Listing Worktrees

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
git worktree list
```

**Example output:**
```
/Users/imaxxs/repositories/deepsecure-mvp    a5422b1 [dev]
/Users/imaxxs/repositories/idp-sso-control   b3f7a21 [feature/idp-sso-control]
/Users/imaxxs/repositories/idp-sso-gateway   c8e9d45 [feature/idp-sso-gateway]
```

---

## 2. Creating Fresh Worktrees

### Prerequisites

- Main repo is on `dev` branch and up to date
- No stale worktrees from previous features (see Section 3)

### Commands

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp

# Ensure dev is up to date
git checkout dev
git pull origin dev

# Create worktrees from current dev HEAD
git worktree add ../[feature]-control -b feature/[feature]-control dev
git worktree add ../[feature]-gateway -b feature/[feature]-gateway dev

# Copy .cursor commands (required for /execute-task to work in worktrees)
cp -r .cursor ../[feature]-control/
cp -r .cursor ../[feature]-gateway/

# Copy .envrc if using direnv
cp .envrc ../[feature]-control/ 2>/dev/null || true
cp .envrc ../[feature]-gateway/ 2>/dev/null || true

# Verify
git worktree list
```

### Naming Convention

| Worktree Directory | Branch Name | Service |
|-------------------|-------------|---------|
| `../[feature]-control` | `feature/[feature]-control` | deeptrail-control |
| `../[feature]-gateway` | `feature/[feature]-gateway` | deeptrail-gateway |

**Past examples:**

| Feature | Control Worktree | Gateway Worktree |
|---------|-----------------|------------------|
| Virtual MCP Server | `../vmcp-control` | `../vmcp-gateway` |
| MVP Production Readiness | `../mvp-prod-control` | `../mvp-prod-gateway` |
| IdP Enhanced SSO | `../idp-sso-control` | `../idp-sso-gateway` |

---

## 3. Cleaning Up Old Worktrees

Before creating new worktrees for a new feature, clean up worktrees from the previous feature.

### Check Current State

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
git worktree list

# Check if branches were already merged
git log --oneline dev..feature/[old-branch] | wc -l
# If 0 commits ahead → safe to delete
```

### Remove Worktrees

```bash
# Safe remove (fails if there are uncommitted changes)
git worktree remove ../[old-worktree-name]

# Force remove (discards uncommitted changes — use with caution)
git worktree remove ../[old-worktree-name] --force
```

### Delete Feature Branches

```bash
# Safe delete (fails if branch isn't merged)
git branch -d feature/[old-branch-name]

# Force delete (use when branch was merged via PR but git doesn't detect it)
git branch -D feature/[old-branch-name]
```

### Full Cleanup Example

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp

# Remove worktree directories
git worktree remove ../mvp-prod-control --force
git worktree remove ../mvp-prod-gateway --force

# Delete branches
git branch -D feature/mvp-prod-control
git branch -D feature/mvp-prod-gateway

# Clean up any orphaned references
git worktree prune

# Verify clean state
git worktree list
# Should show only: /Users/imaxxs/repositories/deepsecure-mvp  [dev]
```

---

## 4. Working in Worktrees

### Opening in Cursor

Each worktree is a separate directory. Open it as a separate Cursor window:

```bash
# Open control plane worktree
cursor /Users/imaxxs/repositories/[feature]-control

# Open gateway worktree
cursor /Users/imaxxs/repositories/[feature]-gateway
```

### Making Commits

Commits work the same as in the main repo. Each worktree is on its own branch:

```bash
cd /Users/imaxxs/repositories/[feature]-control
git add .
git commit -m "WS-A1: Add fetch_groups to IdPConfig"
```

### Pulling Changes from Dev

If `dev` has new commits you need:

```bash
cd /Users/imaxxs/repositories/[feature]-control
git fetch origin
git rebase origin/dev
# or: git merge origin/dev
```

### Pushing Feature Branches

```bash
cd /Users/imaxxs/repositories/[feature]-control
git push -u origin feature/[feature]-control
```

---

## 5. Merging Worktrees (Merge Points)

When a merge point is reached (all prerequisite tasks complete):

### Step 1: Push Both Branches

```bash
cd /Users/imaxxs/repositories/[feature]-control
git push -u origin feature/[feature]-control

cd /Users/imaxxs/repositories/[feature]-gateway
git push -u origin feature/[feature]-gateway
```

### Step 2: Create PRs

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp

gh pr create --base dev --head feature/[feature]-control \
  --title "[Feature]: Control Plane changes"

gh pr create --base dev --head feature/[feature]-gateway \
  --title "[Feature]: Gateway changes"
```

### Step 3: Merge PRs

```bash
# After review/approval
gh pr merge [control-pr-number] --merge
gh pr merge [gateway-pr-number] --merge
```

### Step 4: Update Main Repo

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
git checkout dev
git pull origin dev
```

### Step 5: Clean Up (if done with worktrees)

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp
git worktree remove ../[feature]-control
git worktree remove ../[feature]-gateway
git branch -d feature/[feature]-control
git branch -d feature/[feature]-gateway
git worktree prune
```

---

## 6. Troubleshooting

### "fatal: '[path]' is already checked out"

A branch can only be checked out in one worktree at a time.

```bash
# See which worktree has the branch
git worktree list

# If the worktree directory was manually deleted without git cleanup:
git worktree prune
```

### "fatal: could not create worktree dir"

The parent directory doesn't exist or there's a permissions issue.

```bash
# Verify parent directory exists
ls /Users/imaxxs/repositories/

# Ensure no leftover directory from a previous attempt
rm -rf /Users/imaxxs/repositories/[feature]-control
git worktree prune
```

### Worktree directory was manually deleted

If you `rm -rf` a worktree directory without using `git worktree remove`:

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp

# Prune stale worktree references
git worktree prune

# Now you can recreate or the branch is free for checkout
git worktree list
```

### `.cursor/commands` not found in worktree

Worktrees don't inherit `.cursor/` from the main repo. Copy it:

```bash
cp -r /Users/imaxxs/repositories/deepsecure-mvp/.cursor /Users/imaxxs/repositories/[feature]-control/
```

### Merge conflicts between worktrees

If both worktrees modified the same file (e.g., `sso.py`):

```bash
# Merge the first branch into dev
gh pr merge [first-pr] --merge

# Update the second branch with the merged changes
cd /Users/imaxxs/repositories/[feature]-gateway
git fetch origin
git rebase origin/dev
# Resolve conflicts, then push
git push --force-with-lease
```

### Stale worktrees blocking new feature

```bash
cd /Users/imaxxs/repositories/deepsecure-mvp

# Nuclear cleanup: remove all worktrees
git worktree list | tail -n +2 | awk '{print $1}' | while read wt; do
  git worktree remove "$wt" --force
done

# Delete all feature branches that are fully merged
git branch --merged dev | grep 'feature/' | xargs -r git branch -d

# Prune
git worktree prune

# Verify
git worktree list
```

---

## 7. Quick Reference

| Action | Command |
|--------|---------|
| List worktrees | `git worktree list` |
| Create worktree | `git worktree add ../[name] -b feature/[name] dev` |
| Remove worktree (safe) | `git worktree remove ../[name]` |
| Remove worktree (force) | `git worktree remove ../[name] --force` |
| Delete branch (safe) | `git branch -d feature/[name]` |
| Delete branch (force) | `git branch -D feature/[name]` |
| Prune stale refs | `git worktree prune` |
| Copy cursor commands | `cp -r .cursor ../[name]/` |
| Check divergence from dev | `git log --oneline dev..feature/[name] \| wc -l` |
| Open in Cursor | `cursor /Users/imaxxs/repositories/[name]` |

---

## 8. Worktree Lifecycle per Feature

Every feature that uses parallel worktrees follows this lifecycle:

```
┌──────────────────────────────────────────────────────────────────┐
│                     WORKTREE LIFECYCLE                           │
│                                                                  │
│  1. CLEANUP     Clean up worktrees from previous feature         │
│       │                                                          │
│       ▼                                                          │
│  2. CREATE      Create fresh worktrees from dev HEAD             │
│       │         + copy .cursor/                                  │
│       ▼                                                          │
│  3. DEVELOP     Work in worktrees (Batches 1..N)                 │
│       │         Each worktree = independent Cursor window        │
│       ▼                                                          │
│  4. MERGE       Push branches, create PRs, merge to dev          │
│       │         (at each Merge Point)                            │
│       ▼                                                          │
│  5. CLEANUP     Remove worktrees + delete branches               │
│                 + prune stale references                         │
└──────────────────────────────────────────────────────────────────┘
```

This lifecycle is documented in each feature's:
- `docs/workstreams/[feature]/WORKSTREAM.md` — Worktree Lifecycle section
- `docs/workstreams/[feature]/BATCH_EXECUTION_PLAN.md` — Worktree Setup section
- `docs/workstreams/[feature]/MERGE_POINTS.md` — Post-merge cleanup section
