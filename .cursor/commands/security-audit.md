# Security Audit: OWASP-Based Security Review

Conduct a dedicated security audit using STRIDE threat modeling and OWASP Top 10. Deeper and more systematic than `/review` Axis 4 — use this for security-sensitive changes, new API endpoints, auth flow changes, or before production deployment.

## Workflow Position

```
... → /execute-task → /run-checks → /review → /security-audit → /commit-push-pr
                                                     ↑
                                                (YOU ARE HERE)
```

Can also be invoked standalone at any point when security assessment is needed.

## When to Use

- New or modified authentication/authorization flows
- New API endpoints that accept user input
- Changes to JWT, token, or cryptographic operations
- Gateway middleware changes (request routing, credential injection)
- New external dependencies added
- Before production deployment of any feature
- After a security incident or vulnerability report
- When the change touches Tier 1 (external boundary) or Tier 2 (service boundary)

**When NOT to use:**
- Documentation-only changes
- Test-only changes with no production code impact
- Internal refactoring that doesn't change API surface or auth logic
- For general code quality — use `/review` instead

---

## Instructions

### Phase 1: SCOPE — Define the Audit Boundary

Identify what's being audited:

```bash
# What changed?
git diff --name-only HEAD~1

# Focus on security-relevant files
git diff --name-only HEAD~1 | grep -E '(auth|security|middleware|token|crypto|key|secret|jwt|session)'
```

**Classify the scope:**

| Scope Level | Triggers | Depth |
|-------------|----------|-------|
| **Targeted** | Single endpoint or module changed | OWASP check on changed code only |
| **Service** | Multiple files in one service changed | Full service threat model |
| **Cross-service** | Changes span Control + Gateway | End-to-end auth flow review |
| **Full** | Pre-deployment or incident response | All seven review sections below |

### Phase 2: THREAT MODEL — STRIDE Analysis

For every changed component, apply STRIDE:

```markdown
## STRIDE Threat Model: [Component Name]

| Threat | Question | Risk | Mitigation |
|--------|----------|------|------------|
| **S**poofing | Can an attacker impersonate a user/agent/service? | | |
| **T**ampering | Can request/response data be modified in transit? | | |
| **R**epudiation | Can actions be performed without audit trail? | | |
| **I**nformation Disclosure | Can sensitive data leak via errors/logs/responses? | | |
| **D**enial of Service | Can the service be overwhelmed or crashed? | | |
| **E**levation of Privilege | Can a low-privilege user gain higher access? | | |
```

**For DeepSecure, map threats to boundaries:**

```
Tier 1: Internet → Gateway
├── Spoofing: Forged Agent JWT? Invalid MCP session?
├── Tampering: Modified tool call parameters?
├── DoS: Unbounded tool calls? Large payloads?
└── EoP: Agent accessing another agent's services?

Tier 2: Gateway → Control Plane
├── Spoofing: Forged internal token?
├── Information Disclosure: Vault secrets in logs?
└── EoP: Gateway calling admin-only endpoints?

Tier 3: Service → Database/Redis
├── Injection: Raw SQL in queries?
├── Information Disclosure: Credentials in connection strings?
└── Tampering: Unsigned data in Redis?
```

### Phase 3: OWASP TOP 10 — Systematic Check

Walk through each OWASP category against the changed code.

**Use the Read tool** to examine each security-relevant file, then check:

| # | Category | What to Check | Commands |
|---|----------|---------------|----------|
| A01 | **Broken Access Control** | AuthZ on every endpoint, agent isolation, delegation scoping | `grep -r "Depends(" [file]` to find dependency injection |
| A02 | **Cryptographic Failures** | Ed25519 not RSA, challenge entropy ≥32 bytes, no MD5/SHA1 | `grep -r "hashlib\|md5\|sha1" [files]` |
| A03 | **Injection** | Parameterized queries, no f-string SQL, no eval() | `grep -r "execute(\|raw(\|eval(" [files]` |
| A04 | **Insecure Design** | Threat model exists, fail-closed defaults | Review architecture |
| A05 | **Security Misconfiguration** | No debug mode in prod, no default credentials | `grep -r "DEBUG\|debug=True" [files]` |
| A06 | **Vulnerable Components** | Dependency audit | `pip audit && safety check` |
| A07 | **Auth Failures** | Correct token types, JWT validation, rate limiting | See Token Verification below |
| A08 | **Data Integrity Failures** | Signed JWTs, no unsigned cookies, pipeline integrity | Check JWT verification code |
| A09 | **Logging Failures** | Auth failures logged, no secrets in logs | `grep -r "logger\.\|logging\." [files]` |
| A10 | **SSRF** | User-controlled URLs not fetched server-side | `grep -r "requests\.\|httpx\.\|aiohttp\." [files]` |

### Phase 4: TOKEN & AUTH VERIFICATION — DeepSecure-Specific

**Use the Shell tool** to extract and verify token usage:

```bash
# Find all auth-related code
grep -rn "Authorization\|Bearer\|token\|jwt\|JWT" [changed_files]

# Find all endpoint decorators
grep -rn "@router\.\(get\|post\|put\|delete\)" [changed_files]

# Check each endpoint has auth dependency
grep -A5 "@router\." [changed_files] | grep -E "Depends|current_user|verify_token"
```

**Token type verification table:**

| Endpoint Pattern | Required Token | Verification |
|-----------------|---------------|--------------|
| `/api/v1/auth/*` (public) | None or User Token | Check login returns `.token` not `.access_token` |
| `/api/v1/agents/*` | User Token | `Authorization: Bearer $USER_TOKEN` |
| `/api/v1/vault/*` | Agent JWT | Must have `owner` claim |
| `/api/v1/auth/agent/*` | None (challenge) or Agent JWT (verify) | Ed25519 challenge-response flow |
| Internal (`/internal/*`) | Internal API Token | `gateway-internal-secret-token` + `X-User-ID` |
| Gateway MCP (`/mcp`) | Agent JWT | Must call `initialize` before `tools/call` |

### Phase 5: SECRETS SCAN — Verify No Leaks

```bash
# Check for hardcoded secrets
grep -rn "password\s*=\|secret\s*=\|api_key\s*=\|token\s*=" [changed_files] --include="*.py"

# Check for secrets in logs
grep -rn "logger.*token\|logger.*secret\|logger.*password\|logger.*key" [changed_files]

# Check for secrets in error responses
grep -rn "HTTPException.*detail.*token\|HTTPException.*detail.*key" [changed_files]

# Check git history for accidentally committed secrets
git log --diff-filter=A --name-only -- "*.env" "*.pem" "*.key" "*credentials*"
```

**DeepSecure secret checklist:**
- [ ] Agent private keys use OS keyring, not plaintext files
- [ ] Split-key values never appear in same log entry
- [ ] JWT signing keys not in API responses
- [ ] Redis connection strings from environment, not code
- [ ] Docker compose secrets not hardcoded (use env vars)
- [ ] No production credentials in test fixtures

### Phase 6: DEPENDENCY AUDIT

```bash
# Run pip audit for known vulnerabilities
pip audit

# Run safety check
safety check

# Check for outdated packages with known CVEs
pip list --outdated --format=columns
```

For any new dependency, verify:
- [ ] Actively maintained (last release < 6 months)
- [ ] No known CVEs
- [ ] License compatible with project
- [ ] Justified (can't existing stack solve this?)

### Phase 7: REPORT — Generate Security Audit Report

---

## Output Format

```markdown
## Security Audit: [Feature/Change Name]

### Audit Scope
- **Level:** [Targeted / Service / Cross-service / Full]
- **Files audited:** [count]
- **Services:** [Control / Gateway / SDK / All]

### STRIDE Threat Model

| Threat | Applicable? | Risk | Mitigation Status |
|--------|------------|------|-------------------|
| Spoofing | ✅/❌ | H/M/L | [status] |
| Tampering | ✅/❌ | H/M/L | [status] |
| Repudiation | ✅/❌ | H/M/L | [status] |
| Information Disclosure | ✅/❌ | H/M/L | [status] |
| Denial of Service | ✅/❌ | H/M/L | [status] |
| Elevation of Privilege | ✅/❌ | H/M/L | [status] |

### OWASP Top 10 Assessment

| # | Category | Status | Notes |
|---|----------|--------|-------|
| A01 | Broken Access Control | ✅/⚠️/❌ | |
| A02 | Cryptographic Failures | ✅/⚠️/❌ | |
| A03 | Injection | ✅/⚠️/❌ | |
| A04 | Insecure Design | ✅/⚠️/❌ | |
| A05 | Security Misconfiguration | ✅/⚠️/❌ | |
| A06 | Vulnerable Components | ✅/⚠️/❌ | |
| A07 | Auth Failures | ✅/⚠️/❌ | |
| A08 | Data Integrity Failures | ✅/⚠️/❌ | |
| A09 | Logging Failures | ✅/⚠️/❌ | |
| A10 | SSRF | ✅/⚠️/❌ | |

### Token Type Verification

| Endpoint | Expected Token | Actual Token | Correct? |
|----------|---------------|-------------|----------|
| [endpoint] | [type] | [type] | ✅/❌ |

### Findings

#### Critical (blocks merge — security vulnerability)
- [ ] **CRITICAL [CWE-XXX]:** [file:line] [description]

#### High (should fix before merge)
- [ ] **HIGH:** [file:line] [description]

#### Medium (fix in follow-up, create ticket)
- [ ] **MEDIUM:** [file:line] [description]

#### Low / Informational
- **LOW:** [description]
- **INFO:** [recommendation]

### Secrets Scan
- [ ] No hardcoded secrets in source
- [ ] No secrets in log statements
- [ ] No secrets in error responses
- [ ] No secrets in git history
- [ ] Agent keys use keyring

### Dependency Audit
- [ ] `pip audit` clean
- [ ] `safety check` clean
- [ ] No new dependencies with known CVEs

### Verdict
- [ ] **Secure** — No findings, cleared for merge
- [ ] **Conditionally Secure** — Low/Medium findings, merge with follow-up tickets
- [ ] **Needs Fixes** — High/Critical findings must be addressed before merge
- [ ] **Security Design Review Required** — Architectural concerns need human review
```

---

## Multi-Agent Audit Pattern

For comprehensive audits, invoke the security-auditor subagent:

```
Use Task tool with subagent_type="generalPurpose" and include
the agent definition from .cursor/agents/security-auditor.md

Prompt: "Conduct a security audit of the following changes:
[git diff output or file list]
Focus on: [specific concerns]"
```

The subagent provides an attacker's perspective while this command provides the systematic OWASP/STRIDE framework.

---

## Common Rationalizations

| Rationalization | Reality |
|-----------------|---------|
| "This is an internal API, no one will attack it" | Internal APIs get compromised via SSRF, supply chain attacks, or lateral movement. Protect them. |
| "We'll add security later" | Security retrofitted after launch is 10x more expensive and 10x less effective. Design it in. |
| "The framework handles auth" | Frameworks provide tools. You still need to use them correctly. Missing a `Depends()` on one endpoint is a vulnerability. |
| "This is just MVP, we'll harden for production" | MVP code often becomes production code. Security vulnerabilities in MVP become security vulnerabilities in production. |
| "Nobody will send that input" | Attackers will send exactly that input. Validate everything at every boundary. |
| "We already did a security review last sprint" | Security is continuous. New code = new attack surface. Review every change that touches auth, tokens, or user input. |

## Red Flags

- Endpoints without authentication dependencies (`Depends()` missing)
- `eval()`, `exec()`, or `os.system()` with user-controlled input
- f-string SQL queries (`f"SELECT * FROM {table}"`)
- JWT validation that doesn't check expiry, issuer, or signature
- Secrets hardcoded as string literals or default parameter values
- `DEBUG=True` or verbose error messages in production config
- Agent private keys stored in plaintext files instead of keyring
- Missing rate limiting on authentication endpoints
- User Token used where Agent JWT is required (or vice versa)
- `try/except: pass` swallowing security-relevant errors
- Gateway MCP handler not requiring `initialize` before `tools/call`

## Verification

After completing the audit:

- [ ] STRIDE threat model completed for all changed components
- [ ] All 10 OWASP categories assessed
- [ ] Token type verification table filled for all endpoints
- [ ] Secrets scan completed (source, logs, errors, git history)
- [ ] Dependency audit completed (`pip audit`, `safety check`)
- [ ] All Critical findings addressed before merge
- [ ] All High findings addressed or explicitly deferred with justification
- [ ] Audit report generated and saved

---

## Reference

This command integrates with:
- `/review` → Axis 4 (Security) is a lighter version of this; use this for deeper dives
- `.cursor/agents/security-auditor.md` → Subagent for adversarial review perspective
- `/run-checks` → Includes `bandit` and `safety` checks
- `/ship` → Security audit should pass before production deployment

See also:
- `CLAUDE.md` → Token Types for API Validation
- `CLAUDE.md` → MCP Gateway Protocol Flow
- `CLAUDE.md` → Security Considerations
- OWASP Top 10 (2021): https://owasp.org/Top10/
