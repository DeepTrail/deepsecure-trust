# Security Scan: Pre-Commit Security Audit

Run security scanning tools (bandit, safety) against the codebase, generate a structured report, and gate commits on severity thresholds.

## Invocation

```
/security-scan [--report-only] [--block-on-medium] [path]
```

**Parameters:**
- `--report-only` — Generate report without blocking (default: block on HIGH)
- `--block-on-medium` — Also block on MEDIUM severity findings
- `path` — Specific directory to scan (default: `deepsecure/`)

---

## Instructions

### Step 1: Run Security Scanners

Execute both scanners and capture output:

```bash
# Bandit — Python AST security analysis
bandit -r deepsecure/ -f json -o /tmp/bandit-report.json 2>/dev/null || true

# Safety — dependency vulnerability check
pip audit --format json --output /tmp/safety-report.json 2>/dev/null || \
  safety check --json > /tmp/safety-report.json 2>/dev/null || true
```

If neither `bandit` nor `safety`/`pip audit` are installed:

```bash
echo "Installing security tools..."
pip install bandit pip-audit 2>/dev/null
```

### Step 2: Parse Results

Parse both reports and classify findings:

| Severity | Bandit Level | Action |
|----------|-------------|--------|
| **HIGH** | High confidence + High severity | Block commit |
| **MEDIUM** | Medium confidence or Medium severity | Warn (block if `--block-on-medium`) |
| **LOW** | Low confidence or Low severity | Informational |

For dependency vulnerabilities:
- Known CVE with fix available → HIGH
- Known CVE, no fix yet → MEDIUM
- Deprecated package → LOW

### Step 3: Generate Report

Create `reports/security-scan-[YYYY-MM-DD-HHMMSS].md`:

```markdown
## Security Scan Report — [timestamp]

### Summary
| Severity | Count | Action |
|----------|-------|--------|
| HIGH | [N] | [BLOCKED / —] |
| MEDIUM | [N] | [WARNED / BLOCKED / —] |
| LOW | [N] | Informational |

### Findings

#### HIGH Severity
| # | File | Line | Issue | CWE | Fix |
|---|------|------|-------|-----|-----|
| 1 | [file] | [line] | [description] | [CWE-XXX] | [recommended fix] |

#### MEDIUM Severity
[same format]

#### Dependency Vulnerabilities
| Package | Version | CVE | Fix Version |
|---------|---------|-----|-------------|

### Recommendation
[SAFE TO COMMIT / REQUIRES FIXES BEFORE COMMIT]
```

### Step 4: Report Verdict

Output summary to stdout:

```
Security scan complete:
  HIGH:   [N] findings
  MEDIUM: [N] findings
  LOW:    [N] findings

  Verdict: [SAFE TO COMMIT | BLOCKED — fix HIGH issues first]
  Report:  reports/security-scan-[timestamp].md
```

**Exit behavior:**
- If HIGH findings exist (and not `--report-only`): clearly state commit is blocked
- If only MEDIUM/LOW: warn but allow

---

## When to Use

- Before committing security-sensitive changes (auth, crypto, secrets)
- As part of the `/go` pipeline (automatic)
- Periodically on the full codebase
- After adding new dependencies

**When NOT to use:**
- Documentation-only changes
- Test-only changes (unless testing auth/crypto)

## Related Skills

- `/go` — Invokes this as part of the ship pipeline
- `/review` — Complements with manual code review
