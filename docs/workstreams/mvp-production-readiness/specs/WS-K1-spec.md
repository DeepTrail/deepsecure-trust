# Task Specification: WS-K1 Persistent Vault - Store OAuth Tokens in PostgreSQL

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** MVP_ARCHITECTURE_DEEP_DIVE.md, Issue #1 (In-Memory Vault is Ephemeral)

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-K1 |
| **Task Name** | Persistent Vault - Store OAuth Tokens in PostgreSQL |
| **Type** | Data Model + Service Refactor |
| **Service** | deeptrail-control |
| **Complexity** | L (3+ hrs) |
| **Dependencies** | None (standalone) |
| **Validates** | Token persistence across container restarts |

---

## Problem Statement

### Current Architecture

```
ConnectedService (PostgreSQL)           VaultClient (In-Memory)
┌────────────────────────────┐         ┌────────────────────────┐
│ id: conn-xxx               │         │ _storage: Dict         │
│ user_id: sarah@acme.com    │         │   ├── vault://ref-123  │
│ service_id: notion         │   ──►   │   │   └── encrypted_  │
│ oauth_token_ref: vault://  │         │   │       token_data   │
│   sarah-notion-abc123      │         │   └── vault://ref-456  │
└────────────────────────────┘         │       └── ...          │
        ✅ PERSISTENT                  └────────────────────────┘
                                              ⚠️ EPHEMERAL
```

**Issue:** When `deeptrail-control` container restarts:
1. `VaultClient._storage` dict is reset to `{}`
2. `ConnectedService` records still exist with `oauth_token_ref`
3. Token retrieval fails: "Service not connected"
4. User must re-connect all services

### Target Architecture

```
ConnectedService (PostgreSQL)           VaultToken (PostgreSQL)
┌────────────────────────────┐         ┌────────────────────────┐
│ id: conn-xxx               │         │ token_ref: vault://    │
│ user_id: sarah@acme.com    │         │   sarah-notion-abc123  │
│ service_id: notion         │   ──►   │ encrypted_data: binary │
│ oauth_token_ref: vault://  │         │ user_id: sarah@...     │
│   sarah-notion-abc123      │         │ service_id: notion     │
└────────────────────────────┘         │ created_at, expires_at │
        ✅ PERSISTENT                  └────────────────────────┘
                                              ✅ PERSISTENT
```

---

## Data Model Specification

### Model: `VaultToken`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `token_ref` | `String(512)` | Yes | - | Primary key, vault reference (e.g., `vault://sarah-notion-abc123`) |
| `user_id` | `String(255)` | Yes | - | User identifier for ownership |
| `service_id` | `String(64)` | Yes | - | Service identifier (notion, slack, etc.) |
| `encrypted_data` | `LargeBinary` | Yes | - | Fernet-encrypted token JSON |
| `created_at` | `DateTime(tz=True)` | Yes | `func.now()` | When token was stored |
| `expires_at` | `DateTime(tz=True)` | No | `None` | Token expiration (NULL = no expiry) |
| `last_used_at` | `DateTime(tz=True)` | No | `None` | Last retrieval timestamp |
| `refresh_count` | `Integer` | Yes | `0` | Number of times refreshed |

### Table Definition

```python
class VaultToken(Base):
    """Encrypted OAuth token storage.
    
    Stores OAuth tokens with Fernet encryption. The actual token data
    (access_token, refresh_token, etc.) is encrypted; only metadata
    is stored in plaintext for queries.
    
    Security:
    - Token data encrypted using VAULT_ENCRYPTION_KEY
    - Encryption key never stored in database
    - Token ref is opaque (no sensitive data in ref string)
    """
    
    __tablename__ = "vault_tokens"
    
    # Primary key - the vault reference
    token_ref = Column(
        String(512),
        primary_key=True,
        comment="Vault reference (e.g., vault://sarah-notion-abc123)"
    )
    
    # Ownership
    user_id = Column(
        String(255),
        nullable=False,
        index=True,
        comment="User identifier (e.g., sarah@acme.com)"
    )
    
    service_id = Column(
        String(64),
        nullable=False,
        index=True,
        comment="Service identifier (e.g., notion, slack)"
    )
    
    # Encrypted token data
    encrypted_data = Column(
        LargeBinary,
        nullable=False,
        comment="Fernet-encrypted OAuth token JSON"
    )
    
    # Metadata (for queries, not encrypted)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="When token was stored"
    )
    
    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Token expiration (NULL = no expiry)"
    )
    
    last_used_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Last retrieval timestamp"
    )
    
    refresh_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times token was refreshed"
    )
    
    # Indexes for common queries
    __table_args__ = (
        Index("ix_vault_token_user", "user_id"),
        Index("ix_vault_token_service", "service_id"),
        Index("ix_vault_token_user_service", "user_id", "service_id"),
        Index("ix_vault_token_expires", "expires_at"),
    )
```

### Relationships

| Relationship | Target | Type | Description |
|--------------|--------|------|-------------|
| N/A | `ConnectedService` | Implicit (via `token_ref`) | `ConnectedService.oauth_token_ref` references `VaultToken.token_ref` |

---

## Component Specification

### Class: `VaultClient` (Refactored)

| Field | Value |
|-------|-------|
| **Module** | `deeptrail-control/app/services/vault_client.py` |
| **Type** | Class (singleton pattern retained) |
| **Purpose** | Store and retrieve encrypted OAuth tokens using PostgreSQL |

### Constructor Change

```python
# Current (in-memory)
def __init__(self, encryption_key: Optional[str] = None):
    # ...
    self._storage: Dict[str, bytes] = {}  # IN-MEMORY

# New (database-backed)
def __init__(
    self,
    encryption_key: Optional[str] = None,
    db_session_factory: Optional[Callable[[], Session]] = None,
):
    # ...
    self._db_session_factory = db_session_factory  # DATABASE
```

### Method Signature Changes

```python
# store_token - change from dict storage to DB
def store_token(
    self,
    user_id: str,
    service_id: str,
    token_data: Dict[str, Any],
    expires_in: Optional[int] = None,
    db: Session | None = None,  # NEW - optional explicit session
) -> str:
    """Store token in database instead of memory."""
    ...

# retrieve_token - change from dict lookup to DB query
def retrieve_token(
    self,
    token_ref: str,
    update_usage: bool = True,
    db: Session | None = None,  # NEW
) -> Optional[Dict[str, Any]]:
    """Retrieve token from database."""
    ...

# delete_token - change from dict del to DB delete
def delete_token(
    self,
    token_ref: str,
    db: Session | None = None,  # NEW
) -> bool:
    """Delete token from database."""
    ...

# update_token - change from dict update to DB update
def update_token(
    self,
    token_ref: str,
    token_data: Dict[str, Any],
    db: Session | None = None,  # NEW
) -> bool:
    """Update token in database."""
    ...
```

### New Methods

```python
def get_expiring_tokens(
    self,
    within_seconds: int = 300,
    db: Session | None = None,
) -> List[Tuple[str, Dict[str, Any]]]:
    """Get tokens expiring within timeframe (for proactive refresh)."""
    ...

def delete_user_tokens(
    self,
    user_id: str,
    service_id: Optional[str] = None,
    db: Session | None = None,
) -> int:
    """Delete all tokens for a user (or user+service). Returns count."""
    ...
```

### Database Session Management

```python
from app.db.session import get_db

class VaultClient:
    def __init__(self, ...):
        self._db_session_factory = db_session_factory or get_db
    
    def _get_db(self, db: Session | None = None) -> Session:
        """Get database session from provided or factory."""
        if db is not None:
            return db
        return next(self._db_session_factory())
```

---

## Migration Specification

### Alembic Migration

**File:** `deeptrail-control/alembic/versions/xxx_add_vault_tokens_table.py`

```python
"""Add vault_tokens table for persistent OAuth token storage.

Revision ID: [auto-generated]
Revises: [latest revision]
Create Date: 2026-02-22
"""

from alembic import op
import sqlalchemy as sa

revision = '[auto-generated]'
down_revision = '[current head]'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'vault_tokens',
        sa.Column('token_ref', sa.String(512), primary_key=True),
        sa.Column('user_id', sa.String(255), nullable=False, index=True),
        sa.Column('service_id', sa.String(64), nullable=False, index=True),
        sa.Column('encrypted_data', sa.LargeBinary(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), 
                  server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('refresh_count', sa.Integer(), nullable=False, default=0),
    )
    
    # Additional indexes
    op.create_index(
        'ix_vault_token_user_service',
        'vault_tokens',
        ['user_id', 'service_id']
    )
    op.create_index(
        'ix_vault_token_expires',
        'vault_tokens',
        ['expires_at']
    )


def downgrade() -> None:
    op.drop_index('ix_vault_token_expires', table_name='vault_tokens')
    op.drop_index('ix_vault_token_user_service', table_name='vault_tokens')
    op.drop_table('vault_tokens')
```

---

## Implementation Details

### Encryption Flow (Unchanged)

```
Token Data (JSON)
       │
       ▼
┌──────────────┐
│ json.dumps() │
└──────────────┘
       │
       ▼
┌──────────────┐
│ Fernet.      │
│ encrypt()    │
└──────────────┘
       │
       ▼
encrypted_data (bytes)
       │
       ▼
┌──────────────┐
│ Database     │
│ (LargeBinary)│
└──────────────┘
```

### Token Storage Flow

```python
def store_token(self, user_id, service_id, token_data, expires_in, db=None):
    db = self._get_db(db)
    
    # 1. Generate reference
    token_ref = self._generate_ref(user_id, service_id)
    
    # 2. Calculate expiration
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=expires_in) if expires_in else None
    
    # 3. Wrap with metadata and encrypt
    stored = StoredTokenData(
        token_data=token_data,
        metadata=TokenMetadata(
            created_at=now,
            expires_at=expires_at,
        )
    )
    encrypted = self._fernet.encrypt(
        json.dumps(stored.to_dict()).encode()
    )
    
    # 4. Upsert to database
    existing = db.query(VaultToken).filter(
        VaultToken.token_ref == token_ref
    ).first()
    
    if existing:
        existing.encrypted_data = encrypted
        existing.expires_at = expires_at
        existing.refresh_count = 0
    else:
        db.add(VaultToken(
            token_ref=token_ref,
            user_id=user_id,
            service_id=service_id,
            encrypted_data=encrypted,
            expires_at=expires_at,
        ))
    
    db.commit()
    return token_ref
```

### Token Retrieval Flow

```python
def retrieve_token(self, token_ref, update_usage=True, db=None):
    db = self._get_db(db)
    
    # 1. Query database
    vault_token = db.query(VaultToken).filter(
        VaultToken.token_ref == token_ref
    ).first()
    
    if not vault_token:
        return None
    
    # 2. Decrypt
    try:
        plaintext = self._fernet.decrypt(vault_token.encrypted_data)
        stored = StoredTokenData.from_dict(json.loads(plaintext))
    except InvalidToken:
        raise DecryptionError(f"Failed to decrypt: {token_ref}")
    
    # 3. Update usage timestamp
    if update_usage:
        vault_token.last_used_at = datetime.now(timezone.utc)
        db.commit()
    
    # 4. Return with metadata
    result = dict(stored.token_data)
    result["metadata"] = stored.metadata.to_dict()
    return result
```

---

## Backward Compatibility

### Migration Strategy

1. **Add table:** Create `vault_tokens` table (migration)
2. **Update VaultClient:** Switch from `_storage` dict to database
3. **No API changes:** Endpoint signatures remain the same
4. **Existing data:** Lost (in-memory data doesn't persist anyway)

### Dual-Mode Support (Optional)

For gradual rollout, VaultClient can support both modes:

```python
class VaultClient:
    def __init__(self, ..., use_database: bool = True):
        self._use_database = use_database
        if not use_database:
            self._storage: Dict[str, bytes] = {}  # Legacy mode
```

---

## File Location Rules

| Artifact | Location |
|----------|----------|
| Model | `deeptrail-control/app/models/vault_token.py` |
| Migration | `deeptrail-control/alembic/versions/xxx_add_vault_tokens_table.py` |
| Service | `deeptrail-control/app/services/vault_client.py` (modify) |
| Tests | `deeptrail-control/tests/services/test_vault_client.py` (modify) |
| Model tests | `deeptrail-control/tests/models/test_vault_token.py` (create) |

---

## Test Cases

| Test Case | Input | Expected Outcome |
|-----------|-------|------------------|
| Store token | Valid token data | Token stored in DB, ref returned |
| Retrieve token | Valid ref | Token data returned with metadata |
| Retrieve missing | Invalid ref | Returns None |
| Delete token | Valid ref | Token removed from DB |
| Update token | Valid ref + new data | Token updated, metadata preserved |
| Token expiry | Expired token | Still retrievable (expiry check is caller's job) |
| Encryption roundtrip | Token data | Decrypt matches original |
| Container restart | Store → restart → retrieve | Token still available |
| Get expiring tokens | Tokens expiring in 5 min | Returns correct list |
| Delete user tokens | User ID | All user's tokens deleted |

---

## Security Considerations

| Concern | Mitigation |
|---------|------------|
| Encryption key in DB | Key loaded from env, never stored |
| Key rotation | Support multiple keys with key ID (future) |
| SQL injection | SQLAlchemy ORM prevents injection |
| Timing attacks | Constant-time comparison for refs (future) |
| Audit | Log operations without token values |

---

## Technical Requirements

### Framework-Specific

| Requirement | Pattern | Why |
|-------------|---------|-----|
| ORM | SQLAlchemy | Project standard |
| Migration | Alembic | Project standard |
| Encryption | Fernet (unchanged) | Already implemented |
| Testing | pytest with fixtures | Project standard |

### Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `sqlalchemy` | Existing | ORM |
| `cryptography` | Existing | Fernet encryption |
| `alembic` | Existing | Migrations |

---

## Contract Verification Checklist

Before marking implementation complete, verify:

- [ ] `VaultToken` model created with all fields
- [ ] Alembic migration runs without errors
- [ ] `VaultClient.store_token()` writes to database
- [ ] `VaultClient.retrieve_token()` reads from database
- [ ] Encryption/decryption works correctly
- [ ] Container restart test passes (store → restart → retrieve)
- [ ] No token values in logs
- [ ] Unit tests pass
- [ ] Integration tests pass with real PostgreSQL

---

## References

- **Architecture Doc:** [MVP_ARCHITECTURE_DEEP_DIVE.md](../../architecture/MVP_ARCHITECTURE_DEEP_DIVE.md)
- **Existing Model:** [connected_service.py](../../../deeptrail-control/app/models/connected_service.py)
- **Existing Service:** [vault_client.py](../../../deeptrail-control/app/services/vault_client.py)
- **Related:** `Secret` model in `credential.py` (similar pattern for split keys)
- **Upstream Dependencies:** None
- **Downstream Dependents:** WS-H1, WS-H2 (Credential Injection)
