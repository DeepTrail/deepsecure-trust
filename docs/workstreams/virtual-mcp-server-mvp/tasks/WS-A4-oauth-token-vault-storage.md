# Task: WS-A4 Implement OAuth Token Vault Storage

---

## Metadata

| Field | Value |
|-------|-------|
| **Status** | `ready` |
| **Design Doc** | [deepsecure-virtual-mcp-server-mvp.md](../../../design/internal/markdowns/deepsecure-virtual-mcp-server-mvp.md) |
| **Workstream** | WS-A: Control Plane Foundation |
| **Dependencies** | A3 (Connected Services model) |
| **Blocked By** | None (A3 is complete ✅) |
| **Assigned** | - |
| **Created** | January 30, 2026 |
| **Estimated Complexity** | `M` (2-4 hours) |
| **Batch** | 3 |

---

## Validation Mapping

| Mapping | Value |
|---------|-------|
| **Validates Demo** | Demo 1: Unified Connection (credential injection path) |
| **Validates User Journey Step** | Step 3: Sarah Connects Notion & Slack (token storage) |

---

## Pre-Conditions

Before starting this task, ensure:

- [x] A3 (Connected Services model) is complete
- [ ] `deeptrail-control/` service structure exists
- [ ] ConnectedService model can be imported from `deeptrail-control.models`

---

## Task Description

Implement secure OAuth token vault storage that:
1. Stores user OAuth tokens (access_token, refresh_token) securely
2. Returns opaque references (`vault://user-service-id`) for storage in ConnectedService
3. Retrieves tokens by reference when needed (e.g., for credential injection)
4. Implements a ConnectedServiceService that orchestrates token storage with service connections

### Context

From the MVP design (Section 2.4 - Step 3 and Section 4.2):

```
Sarah clicks "Connect Notion":
1. Browser redirects to Notion OAuth
2. Sarah logs into Notion
3. Notion consent screen shown
4. Sarah clicks "Allow"
5. Notion returns OAuth tokens to DeepTrail

DeepTrail stores connection:
{
  "user_id": "sarah@acme.com",
  "service_id": "notion",
  "oauth_token_ref": "vault://sarah-notion-oauth-xyz",  // Encrypted
  "scopes_granted": ["read_content", "search", "create_pages"]
}
```

Later, during tools/call:
```
Gateway needs Sarah's OAuth token:
├── Get oauth_token_ref from ConnectedService
├── Fetch actual token from vault
└── Inject into backend request
```

### Technical Notes

- **Vault Reference Format**: `vault://{user_id}-{service_id}-{unique_suffix}`
- **For MVP**: Use encrypted in-memory or simple file-based storage
- **Post-MVP**: Integrate with HashiCorp Vault, AWS Secrets Manager, etc.
- **Security**: Tokens must be encrypted at rest
- **Separation**: VaultClient handles encryption/storage, ConnectedServiceService handles business logic

---

## Acceptance Criteria

### Protocol
- [ ] N/A (internal service)

### Security
- [ ] OAuth tokens are encrypted before storage (use Fernet or similar)
- [ ] Encryption key is loaded from environment, not hardcoded
- [ ] Token references are opaque (no token data in reference string)
- [ ] Tokens can be revoked/deleted by reference
- [ ] No token data appears in logs

### Integration
- [ ] VaultClient can be imported from `deeptrail-control.services`
- [ ] ConnectedServiceService can be imported from `deeptrail-control.services`
- [ ] Works with ConnectedService model from A3
- [ ] Gateway can call vault to retrieve tokens (for C7: credential injection)

### Functional
- [ ] `VaultClient.store_token(user_id, service_id, token_data)` → returns `vault://...` reference
- [ ] `VaultClient.retrieve_token(token_ref)` → returns decrypted token data
- [ ] `VaultClient.delete_token(token_ref)` → removes token from storage
- [ ] `VaultClient.token_exists(token_ref)` → boolean check
- [ ] `ConnectedServiceService.connect_service(user_id, service_id, oauth_response)` → stores token and creates ConnectedService record
- [ ] `ConnectedServiceService.disconnect_service(user_id, service_id)` → deletes token and marks ConnectedService as disconnected
- [ ] `ConnectedServiceService.get_token_for_service(user_id, service_id)` → retrieves decrypted token

### General
- [ ] Unit tests for VaultClient with mocked encryption
- [ ] Unit tests for ConnectedServiceService with mocked VaultClient
- [ ] Integration test for full connect/disconnect flow
- [ ] No new linting errors introduced

---

## Files to Create

| File | Purpose |
|------|---------|
| `deeptrail-control/services/vault_client.py` | Secure token storage with encryption |
| `deeptrail-control/services/connected_service_service.py` | Business logic for service connections |
| `deeptrail-control/tests/services/test_vault_client.py` | Unit tests for VaultClient |
| `deeptrail-control/tests/services/test_connected_service_service.py` | Unit tests for service |

---

## Files to Modify

| File | Changes |
|------|---------|
| `deeptrail-control/services/__init__.py` | Export VaultClient and ConnectedServiceService |

---

## Implementation Hints

```python
# deeptrail-control/services/vault_client.py

import os
import uuid
import json
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet

class VaultClient:
    """
    Secure storage for OAuth tokens.
    
    MVP Implementation: In-memory encrypted storage.
    Production: Integrate with HashiCorp Vault or AWS Secrets Manager.
    """
    
    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize vault with encryption key.
        
        Args:
            encryption_key: Fernet-compatible key. If None, loads from
                           VAULT_ENCRYPTION_KEY environment variable.
        """
        key = encryption_key or os.environ.get("VAULT_ENCRYPTION_KEY")
        if not key:
            # For development only - generate ephemeral key
            key = Fernet.generate_key().decode()
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
        self._storage: Dict[str, bytes] = {}  # token_ref -> encrypted_data
    
    def _generate_ref(self, user_id: str, service_id: str) -> str:
        """Generate opaque token reference."""
        suffix = uuid.uuid4().hex[:8]
        return f"vault://{user_id}-{service_id}-{suffix}"
    
    def store_token(
        self, 
        user_id: str, 
        service_id: str, 
        token_data: Dict[str, Any]
    ) -> str:
        """
        Store OAuth token securely.
        
        Args:
            user_id: User identifier (e.g., "sarah@acme.com")
            service_id: Service identifier (e.g., "notion")
            token_data: OAuth token response (access_token, refresh_token, etc.)
        
        Returns:
            Opaque token reference (e.g., "vault://sarah@acme.com-notion-abc123")
        """
        token_ref = self._generate_ref(user_id, service_id)
        
        # Encrypt token data
        plaintext = json.dumps(token_data).encode()
        encrypted = self._fernet.encrypt(plaintext)
        
        # Store encrypted data
        self._storage[token_ref] = encrypted
        
        return token_ref
    
    def retrieve_token(self, token_ref: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve decrypted OAuth token.
        
        Args:
            token_ref: Token reference from store_token()
        
        Returns:
            Decrypted token data or None if not found
        """
        encrypted = self._storage.get(token_ref)
        if not encrypted:
            return None
        
        # Decrypt token data
        plaintext = self._fernet.decrypt(encrypted)
        return json.loads(plaintext.decode())
    
    def delete_token(self, token_ref: str) -> bool:
        """
        Delete token from storage.
        
        Args:
            token_ref: Token reference
        
        Returns:
            True if deleted, False if not found
        """
        if token_ref in self._storage:
            del self._storage[token_ref]
            return True
        return False
    
    def token_exists(self, token_ref: str) -> bool:
        """Check if token exists in storage."""
        return token_ref in self._storage


# deeptrail-control/services/connected_service_service.py

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from ..models.connected_service import ConnectedService
from .vault_client import VaultClient

class ConnectedServiceService:
    """
    Service for managing user's connected backend services.
    
    Orchestrates between ConnectedService model and VaultClient.
    """
    
    def __init__(self, vault_client: VaultClient, db_session):
        self._vault = vault_client
        self._db = db_session
    
    def connect_service(
        self,
        user_id: str,
        service_id: str,
        oauth_response: Dict[str, Any],
        scopes_granted: List[str]
    ) -> ConnectedService:
        """
        Connect a user to a backend service.
        
        Args:
            user_id: User identifier
            service_id: Service identifier (e.g., "notion")
            oauth_response: OAuth token response from provider
            scopes_granted: List of scopes user consented to
        
        Returns:
            ConnectedService record
        """
        # Store token securely
        token_ref = self._vault.store_token(user_id, service_id, oauth_response)
        
        # Check for existing connection
        existing = self._db.query(ConnectedService).filter(
            ConnectedService.user_id == user_id,
            ConnectedService.service_id == service_id
        ).first()
        
        if existing:
            # Re-connect: delete old token, update record
            if existing.oauth_token_ref:
                self._vault.delete_token(existing.oauth_token_ref)
            existing.oauth_token_ref = token_ref
            existing.scopes_granted = scopes_granted
            existing.connected_at = datetime.now(timezone.utc)
            existing.disconnected_at = None
            return existing
        
        # Create new connection
        connection = ConnectedService(
            user_id=user_id,
            service_id=service_id,
            oauth_token_ref=token_ref,
            scopes_granted=scopes_granted,
            connected_at=datetime.now(timezone.utc)
        )
        self._db.add(connection)
        return connection
    
    def disconnect_service(self, user_id: str, service_id: str) -> bool:
        """
        Disconnect a user from a backend service.
        
        Args:
            user_id: User identifier
            service_id: Service identifier
        
        Returns:
            True if disconnected, False if not found
        """
        connection = self._db.query(ConnectedService).filter(
            ConnectedService.user_id == user_id,
            ConnectedService.service_id == service_id
        ).first()
        
        if not connection:
            return False
        
        # Delete token from vault
        if connection.oauth_token_ref:
            self._vault.delete_token(connection.oauth_token_ref)
        
        # Mark as disconnected (soft delete)
        connection.disconnected_at = datetime.now(timezone.utc)
        connection.oauth_token_ref = None
        
        return True
    
    def get_token_for_service(
        self, 
        user_id: str, 
        service_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get OAuth token for a user's connected service.
        
        Used by gateway for credential injection.
        
        Args:
            user_id: User identifier
            service_id: Service identifier
        
        Returns:
            Decrypted OAuth token data or None
        """
        connection = self._db.query(ConnectedService).filter(
            ConnectedService.user_id == user_id,
            ConnectedService.service_id == service_id,
            ConnectedService.disconnected_at.is_(None)
        ).first()
        
        if not connection or not connection.oauth_token_ref:
            return None
        
        return self._vault.retrieve_token(connection.oauth_token_ref)
    
    def get_user_connections(self, user_id: str) -> List[ConnectedService]:
        """Get all active connections for a user."""
        return self._db.query(ConnectedService).filter(
            ConnectedService.user_id == user_id,
            ConnectedService.disconnected_at.is_(None)
        ).all()
```

---

## Post-Conditions

After completing this task:

- [ ] All acceptance criteria met
- [ ] Tests pass locally: `pytest deeptrail-control/tests/services/`
- [ ] Linting passes: `ruff check deeptrail-control/services/`
- [ ] Type checking passes: `mypy deeptrail-control/services/`
- [ ] Task C7 can use VaultClient for credential injection
- [ ] OAuth callback endpoint (future) can use ConnectedServiceService

---

## References

- Design Doc Section 2.4: Step 3 - Sarah Connects Notion & Slack
- Design Doc Section 4.2: Token Flow in MVP
- A3 Task: ConnectedService model for token reference storage
- C7 Task: Credential injection (will consume this service)

---

## Notes

- **MVP simplification**: In-memory storage is acceptable for MVP; production needs persistent vault
- **Encryption key management**: For MVP, generate ephemeral key if not set; production needs proper key management
- **Token refresh**: Not implemented in MVP; post-MVP should add refresh token rotation
- **Consider**: Adding token expiration tracking for proactive refresh
- **Gateway integration**: Gateway will need API endpoint or gRPC to fetch tokens for C7

---

## Test Cases to Cover

```python
# test_vault_client.py

def test_store_and_retrieve_token():
    vault = VaultClient()
    token_data = {"access_token": "abc123", "refresh_token": "xyz789"}
    ref = vault.store_token("sarah@acme.com", "notion", token_data)
    
    assert ref.startswith("vault://")
    assert "sarah@acme.com" in ref
    assert "notion" in ref
    
    retrieved = vault.retrieve_token(ref)
    assert retrieved == token_data

def test_delete_token():
    vault = VaultClient()
    ref = vault.store_token("user", "service", {"token": "secret"})
    
    assert vault.token_exists(ref) is True
    vault.delete_token(ref)
    assert vault.token_exists(ref) is False
    assert vault.retrieve_token(ref) is None

def test_token_data_is_encrypted():
    vault = VaultClient()
    ref = vault.store_token("user", "service", {"secret": "sensitive"})
    
    # Raw storage should be encrypted (not readable JSON)
    raw = vault._storage[ref]
    assert b"sensitive" not in raw

# test_connected_service_service.py

def test_connect_service_stores_token():
    vault = MagicMock(spec=VaultClient)
    vault.store_token.return_value = "vault://ref"
    
    service = ConnectedServiceService(vault, mock_db)
    result = service.connect_service(
        "sarah@acme.com", 
        "notion",
        {"access_token": "abc"},
        ["read_content"]
    )
    
    vault.store_token.assert_called_once()
    assert result.oauth_token_ref == "vault://ref"

def test_disconnect_deletes_token():
    vault = MagicMock(spec=VaultClient)
    service = ConnectedServiceService(vault, mock_db_with_connection)
    
    service.disconnect_service("sarah@acme.com", "notion")
    
    vault.delete_token.assert_called_once()
```

---

## Execution Log

### Progress Updates

| Date | Update |
|------|--------|
| - | Task created, ready to start |

### Blockers Encountered

| Date | Blocker | Resolution |
|------|---------|------------|
| - | - | - |
