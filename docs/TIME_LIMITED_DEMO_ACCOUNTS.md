# Time-Limited Demo Accounts

How to give users temporary access to DeepSecure (1 hour, 6 hours, 24 hours) via either Keycloak or Google SSO.

**Current deployment:** `https://app.deepsecure.one`
**Keycloak Admin Console:** `https://app.deepsecure.one/admin/` (realm: `deepsecure`)

---

## Option A: Keycloak Session Limits (Zero Code Changes)

Use Keycloak's built-in session and token lifetime controls. Available immediately.

### Step 1: Set Realm Session Timeouts

In the Keycloak Admin Console:

1. Select the **DeepSecure** realm (top-left dropdown)
2. Go to **Realm settings** → **Sessions** tab
3. Configure:

| Setting | Purpose | Recommended Value |
|---------|---------|-------------------|
| **SSO Session Idle** | Auto-logout after inactivity | 30 min – 1 hour |
| **SSO Session Max** | Absolute max session length | Set to demo duration (1h / 6h / 24h) |
| **SSO Session Idle Remember Me** | Idle timeout when "remember me" is checked | Same as SSO Session Idle |
| **SSO Session Max Remember Me** | Max session when "remember me" is checked | Same as SSO Session Max |

4. Go to **Realm settings** → **Tokens** tab
5. Configure:

| Setting | Purpose | Recommended Value |
|---------|---------|-------------------|
| **Access Token Lifespan** | How long each JWT is valid before refresh | 5 minutes |
| **Client Session Idle** | Per-client idle timeout | Same as realm |
| **Client Session Max** | Per-client max session | Same as realm |

### Step 2: Create the Demo User

1. Go to **Users** → **Add user**
2. Fill in:
   - **Username**: `demo-user@company.com`
   - **Email**: `demo-user@company.com`
   - **Email verified**: ON
   - **First name / Last name**: as needed
   - **Required user actions**: None (remove any defaults)
   - **Groups**: Add to relevant groups (e.g., `/engineering`, `/sales`)
3. Click **Create**
4. Go to the **Credentials** tab → **Set password**
   - Enter the password
   - Toggle **Temporary** to OFF (unless you want them to change it on first login)

### Step 3: After the Demo — Disable the User

1. Go to **Users** → find the user
2. Toggle **Enabled** to OFF
3. Or delete the user entirely

### Limitations

- Session timeouts apply to ALL users in the realm, not per-user
- No automatic account expiry — you must manually disable users
- Cannot give different demo durations to different users simultaneously

---

## Option B: Google SSO with Workspace Controls

For users who sign in with Google. Access is controlled via Google Workspace Admin Console.

### Prerequisites

- Demo user must have a `@deeptrail.com` Google Workspace account (OAuth is configured as `internal` with `hd=deeptrail.com`)
- External emails (e.g., `prospect@acme.com`) cannot use Google SSO with the current config

### Steps

1. **Create or use an existing** `@deeptrail.com` Google Workspace account
2. Share the credentials with the demo user
3. They sign in via "Sign in with Google" on `app.deepsecure.one`
4. After the demo:
   - **Suspend the account**: Google Workspace Admin → Users → select user → Suspend
   - **Or revoke app access**: Google Workspace Admin → Security → API controls → find "DeepTrail Google App" → Revoke

### Limitations

- Only works for `@deeptrail.com` accounts
- No automatic time-based expiry
- Requires Google Workspace admin access to disable

---

## Option C: App-Level Account Expiry (Future — Requires Code Changes)

Add an `expires_at` field to the user record in the DeepSecure Control Plane. Works for both Keycloak and Google SSO.

### How It Works

```
User logs in (Keycloak or Google)
    → Control Plane checks user.expires_at
    → If expired → reject login, redirect with "Account expired" message
    → If valid → issue JWT, proceed to dashboard
    → Middleware checks on every request, not just login
```

### Implementation Plan

#### 1. Database: Add `expires_at` column to `users` table

```python
# New Alembic migration
# deeptrail-control/alembic/versions/xxxx_add_user_expires_at.py
op.add_column('users', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))
```

`NULL` means no expiry (permanent account). A timestamp means the account expires at that time.

#### 2. Auth Middleware: Check expiry on every request

```python
# In deeptrail-control/app/core/security.py or auth middleware
def check_user_expiry(user):
    if user.expires_at and user.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=403, detail="Account expired")
```

#### 3. SSO Callback: Check expiry at login time

In the SSO callback (`deeptrail-control/app/api/v1/endpoints/sso.py`), after resolving the user, check `expires_at` before issuing a JWT.

#### 4. Admin API: Set expiry when creating users

```python
# New endpoint or extend existing user management
POST /api/v1/admin/users
{
    "email": "demo@company.com",
    "expires_at": "2026-05-15T00:00:00Z"  // or
    "expires_in_hours": 6
}
```

#### 5. Frontend: Show expiry status

- Show remaining time in the dashboard header
- Show "Account expired" message on the login page when redirected

#### 6. (Optional) Management Script

```bash
# Create a 6-hour demo account via CLI
python scripts/create_demo_account.py \
  --email demo@company.com \
  --hours 6 \
  --idp keycloak  # or google
```

### Effort Estimate

| Component | Effort |
|-----------|--------|
| Database migration | 15 min |
| Auth middleware check | 30 min |
| SSO callback check | 30 min |
| Admin API endpoint | 1 hour |
| Frontend expiry display | 1 hour |
| Management script | 30 min |
| **Total** | **~3.5 hours** |

### Advantages

- Per-user time limits (different users can have different durations)
- Automatic — no manual disable needed
- Works for both Keycloak and Google SSO
- Audit trail of when accounts were created and expired

---

## Quick Reference: Which Option When?

| Scenario | Best Option |
|----------|-------------|
| One-off demo for a prospect today | **A** (Keycloak) — create user, demo, disable after |
| Internal team member needs temporary access | **A** (Keycloak) or **B** (Google SSO) |
| Recurring demos with automatic expiry | **C** (App-level) — build once, self-service after |
| External prospect without `@deeptrail.com` email | **A** (Keycloak) — only option that doesn't require Google Workspace |
| Scalable self-service demo portal | **C** (App-level) + sign-up flow |

---

## Current Keycloak Users

| Username | Email | Groups | Status |
|----------|-------|--------|--------|
| mahendra | mahendra@deeptrail.com | engineering, admin | Active |
| sarah | sarah@deeptrail.com | engineering | Active |
| Selina | selina@deeptrail.com | engineering, sales | Active (just created) |

To view/manage: `https://app.deepsecure.one/admin/` → DeepSecure realm → Users
