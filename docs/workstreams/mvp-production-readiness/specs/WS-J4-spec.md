# Task Specification: WS-J4 Implement Result Filtering (PII Masking)

> **IMMUTABLE AFTER DESIGN APPROVAL**
>
> This specification defines what implementation MUST match exactly.
> Do not modify without updating the design doc first.
>
> **Source:** `deepsecure-comprehensive-architecture-consolidated.md` Section 11 (Gateway Components),
> MCP Governance Layer ("Apply output content filters — PII masking")
>
> **Coverage Matrix:** Result Filtering → PII masking → ❌ Not Implemented (0%)

---

## Overview

| Field | Value |
|-------|-------|
| **Task ID** | WS-J4 |
| **Task Name** | Implement Result Filtering (PII Masking) |
| **Type** | Middleware (Response Filter) |
| **Service** | deeptrail-gateway |
| **Complexity** | M (1-3 hours) |
| **Dependencies** | MP3.5 (P1.5 complete) |
| **Validates** | MCP Governance: sensitive data removal from tool call responses |
| **Unblocks** | WS-J6 (Keycloak token exchange — governance layer complete) |

---

## Problem Statement

### Current State

Tool call responses from backend APIs (Notion, Slack, HubSpot) are returned verbatim to agents. If a backend response contains PII (email addresses, phone numbers, SSNs, API keys), it flows through to the agent unfiltered.

```
Agent ──► Gateway ──► Backend API
                          │
                    Response with PII
                          │
                   ┌──────▼──────┐
                   │ NO FILTER   │  ← Current: raw pass-through
                   └──────┬──────┘
                          │
                   Agent sees PII
```

### Target State

Responses pass through a configurable result filter that masks PII patterns before returning to the agent.

```
Agent ──► Gateway ──► Backend API
                          │
                    Response with PII
                          │
                   ┌──────▼──────┐
                   │ ResultFilter │  ← New: PII masking
                   │ • emails     │
                   │ • phones     │
                   │ • SSNs       │
                   │ • API keys   │
                   └──────┬──────┘
                          │
                   Agent sees [REDACTED]
```

---

## Component Specification

### Module: `ResultFilter`

| Field | Value |
|-------|-------|
| **Module** | `deeptrail-gateway.app.middleware.result_filter` |
| **File** | `deeptrail-gateway/app/middleware/result_filter.py` |
| **Type** | Class |
| **Pattern** | Configurable filter with per-backend rules |

### Core Data Models

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class PIIType(str, Enum):
    """Types of PII that can be detected and masked."""
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    API_KEY = "api_key"
    IP_ADDRESS = "ip_address"


@dataclass
class MaskingRule:
    """Defines how a specific PII type should be masked."""
    pii_type: PIIType
    enabled: bool = True
    replacement: str = "[REDACTED]"
    # Partial masking: show last N chars (e.g., "***@example.com" → show domain)
    partial_mask: bool = False
    visible_chars: int = 0


@dataclass
class BackendFilterConfig:
    """Per-backend filtering configuration."""
    backend_id: str
    enabled: bool = True
    masking_rules: List[MaskingRule] = field(default_factory=list)
    # Fields to always exclude from responses (e.g., internal IDs)
    excluded_fields: Set[str] = field(default_factory=set)
    # Fields to never mask (e.g., the agent's own email in context)
    allowlisted_fields: Set[str] = field(default_factory=set)


@dataclass
class FilterResult:
    """Result of applying filters to a response."""
    filtered_content: Any
    masks_applied: int
    pii_types_found: List[PIIType]
    fields_excluded: int
```

### Interface Contract

```python
import re
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ResultFilter:
    """
    Filters tool call responses to mask PII and remove sensitive fields.
    
    Operates on the MCP tools/call response content before it reaches the agent.
    Configurable per-backend with default rules for common PII patterns.
    """

    def __init__(
        self,
        default_rules: Optional[List[MaskingRule]] = None,
        backend_configs: Optional[Dict[str, BackendFilterConfig]] = None,
        enabled: bool = True,
    ):
        ...

    def filter_response(
        self,
        content: Any,
        backend_id: str,
        tool_name: Optional[str] = None,
    ) -> FilterResult:
        """
        Filter a tool call response, masking PII and excluding fields.

        Args:
            content: The raw response content (dict, list, or str).
            backend_id: Backend identifier (e.g., "notion", "hubspot").
            tool_name: Optional tool name for tool-specific rules.

        Returns:
            FilterResult with masked content and audit metadata.
        """
        ...

    def mask_string(self, value: str, rules: List[MaskingRule]) -> tuple[str, List[PIIType]]:
        """
        Apply PII masking rules to a string value.

        Returns:
            Tuple of (masked_string, list of PII types found).
        """
        ...

    def _filter_dict(
        self,
        data: Dict[str, Any],
        config: BackendFilterConfig,
    ) -> tuple[Dict[str, Any], int, List[PIIType]]:
        """Recursively filter a dictionary, masking PII in string values."""
        ...

    def _filter_list(
        self,
        data: List[Any],
        config: BackendFilterConfig,
    ) -> tuple[List[Any], int, List[PIIType]]:
        """Recursively filter a list."""
        ...

    def get_config_for_backend(self, backend_id: str) -> BackendFilterConfig:
        """Get filter config, falling back to defaults if no backend-specific config."""
        ...
```

### PII Detection Patterns

These regex patterns MUST be implemented:

| PII Type | Pattern | Example Match | Replacement |
|----------|---------|---------------|-------------|
| `EMAIL` | `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}` | `sarah@acme.com` | `[EMAIL REDACTED]` |
| `PHONE` | US: `(\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}` | `+1 (555) 123-4567` | `[PHONE REDACTED]` |
| `SSN` | `\b\d{3}-\d{2}-\d{4}\b` | `123-45-6789` | `[SSN REDACTED]` |
| `CREDIT_CARD` | `\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b` | `4111-1111-1111-1111` | `[CC REDACTED]` |
| `API_KEY` | `\b(sk-[a-zA-Z0-9]{32,})\b`, `\b(xoxb-[a-zA-Z0-9-]+)\b`, `\b(Bearer\s+[a-zA-Z0-9._-]{20,})\b` | `sk-abc123...` | `[API_KEY REDACTED]` |
| `IP_ADDRESS` | `\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b` | `192.168.1.100` | `[IP REDACTED]` |

### Default Configuration

```python
DEFAULT_MASKING_RULES = [
    MaskingRule(pii_type=PIIType.EMAIL, replacement="[EMAIL REDACTED]"),
    MaskingRule(pii_type=PIIType.PHONE, replacement="[PHONE REDACTED]"),
    MaskingRule(pii_type=PIIType.SSN, replacement="[SSN REDACTED]"),
    MaskingRule(pii_type=PIIType.CREDIT_CARD, replacement="[CC REDACTED]"),
    MaskingRule(pii_type=PIIType.API_KEY, replacement="[API_KEY REDACTED]"),
    MaskingRule(pii_type=PIIType.IP_ADDRESS, enabled=False),  # Off by default
]
```

### Integration Point: MCP Tools/Call Handler

The `ResultFilter` is invoked in the `tools/call` handler **after** receiving the backend response and **before** returning the MCP result to the agent.

```python
# In deeptrail-gateway/app/mcp/handlers/tools_call.py
# After backend call returns result:

result_filter = get_result_filter()
if result_filter and result_filter.enabled:
    filter_result = result_filter.filter_response(
        content=backend_response,
        backend_id=backend_id,
        tool_name=tool_name,
    )
    backend_response = filter_result.filtered_content

    if filter_result.masks_applied > 0:
        logger.info(
            "PII masked in response",
            extra={
                "tool": tool_name,
                "backend": backend_id,
                "masks_applied": filter_result.masks_applied,
                "pii_types": [t.value for t in filter_result.pii_types_found],
            },
        )
```

### Module-Level Accessor Pattern

Follow the existing gateway pattern (see `audit.py`, `credential_injection.py`):

```python
_result_filter: Optional[ResultFilter] = None


def get_result_filter() -> Optional[ResultFilter]:
    """Get the configured ResultFilter instance."""
    return _result_filter


def configure_result_filter(
    default_rules: Optional[List[MaskingRule]] = None,
    backend_configs: Optional[Dict[str, BackendFilterConfig]] = None,
    enabled: bool = True,
) -> ResultFilter:
    """Configure and store the global ResultFilter."""
    global _result_filter
    _result_filter = ResultFilter(
        default_rules=default_rules,
        backend_configs=backend_configs,
        enabled=enabled,
    )
    return _result_filter


def reset_result_filter() -> None:
    """Reset result filter (for testing)."""
    global _result_filter
    _result_filter = None
```

---

## API Contracts

> **Note:** This task implements an internal middleware module, not API endpoints.
> The result filter operates within the `tools/call` MCP handler pipeline.
> No new HTTP endpoints are created.

---

## File Location Rules

| Artifact | Correct Location |
|----------|------------------|
| Implementation | `deeptrail-gateway/app/middleware/result_filter.py` |
| Unit tests | `deeptrail-gateway/tests/middleware/test_result_filter.py` |
| Integration point | `deeptrail-gateway/app/mcp/handlers/tools_call.py` (modify) |
| Configuration | `deeptrail-gateway/app/main.py` (add `configure_result_filter()`) |

---

## Technical Requirements

### Framework-Specific

| Requirement | Pattern | Why |
|-------------|---------|-----|
| Module accessor | `get_*`, `configure_*`, `reset_*` | Gateway module pattern (see `audit.py`) |
| Regex compilation | Compile at `__init__` time | Performance: avoid recompilation per request |
| Recursive traversal | Handle nested dicts/lists | Backend responses can be deeply nested JSON |
| Thread safety | No shared mutable state per-request | Middleware may handle concurrent requests |

### Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `re` | stdlib | PII pattern matching |
| `logging` | stdlib | Audit logging of masked content |
| `dataclasses` | stdlib | Configuration models |

### Existing Code Relationship

| Existing Module | Relationship | Notes |
|-----------------|-------------|-------|
| `security_filters.py` | Complementary | SQL/XSS injection on **input**; result filter on **output** |
| `sanitization.py` | Complementary | Request sanitization; result filter is response sanitization |
| `permission_filter.py` | Complementary | Filters which **tools** agent sees; result filter masks **data** in responses |

---

## Test Cases

### Unit Tests

| Test Case | Method | Expected | Notes |
|-----------|--------|----------|-------|
| Mask email in string | `mask_string()` | `"Contact [EMAIL REDACTED] for info"` | Basic pattern |
| Mask phone in string | `mask_string()` | `"Call [PHONE REDACTED]"` | US format variants |
| Mask SSN in string | `mask_string()` | `"SSN: [SSN REDACTED]"` | Exact format |
| Mask credit card | `mask_string()` | `"CC: [CC REDACTED]"` | With/without dashes |
| Mask API key (sk-*) | `mask_string()` | `"Key: [API_KEY REDACTED]"` | OpenAI format |
| Mask Slack token (xoxb-*) | `mask_string()` | `"Token: [API_KEY REDACTED]"` | Slack bot token |
| No false positive on short strings | `mask_string()` | `"test"` unchanged | No masking when no PII |
| Nested dict filtering | `filter_response()` | PII masked at all depths | Recursive traversal |
| List filtering | `filter_response()` | PII masked in list items | Array of objects |
| Excluded fields removed | `filter_response()` | Field absent from result | `excluded_fields` config |
| Allowlisted fields preserved | `filter_response()` | Field NOT masked | `allowlisted_fields` config |
| Disabled filter passthrough | `filter_response()` | Content unchanged | `enabled=False` |
| Disabled rule skipped | `filter_response()` | Only enabled rules apply | `rule.enabled=False` |
| Backend-specific config | `filter_response()` | Per-backend rules used | Different backends, different rules |
| Default config fallback | `get_config_for_backend()` | Default rules used | Unknown backend ID |
| FilterResult audit metadata | `filter_response()` | `masks_applied > 0`, `pii_types_found` populated | Audit trail |
| Multiple PII in one string | `mask_string()` | All instances masked | `"Email: a@b.com, Phone: 555-1234"` |
| PII in JSON string values | `filter_response()` | Only string values masked | Don't touch keys or numbers |
| Empty/null content | `filter_response()` | Handled gracefully | No exception |

### Integration Tests

| Test Case | Setup | Expected | Notes |
|-----------|-------|----------|-------|
| MCP tools/call with PII in response | Mock backend returns email | Agent response has `[EMAIL REDACTED]` | Full pipeline |
| Filter disabled via config | `enabled=False` | Raw response returned | Feature toggle |

### Test Code Example

```python
import pytest
from deeptrail_gateway.app.middleware.result_filter import (
    ResultFilter,
    MaskingRule,
    PIIType,
    BackendFilterConfig,
    FilterResult,
    configure_result_filter,
    get_result_filter,
    reset_result_filter,
)


class TestResultFilter:
    def setup_method(self):
        self.filter = ResultFilter()

    def test_mask_email_in_string(self):
        result, pii_types = self.filter.mask_string(
            "Contact sarah@acme.com for details",
            self.filter._default_rules,
        )
        assert "sarah@acme.com" not in result
        assert "[EMAIL REDACTED]" in result
        assert PIIType.EMAIL in pii_types

    def test_mask_phone_us_format(self):
        result, pii_types = self.filter.mask_string(
            "Call +1 (555) 123-4567",
            self.filter._default_rules,
        )
        assert "(555) 123-4567" not in result
        assert "[PHONE REDACTED]" in result
        assert PIIType.PHONE in pii_types

    def test_mask_ssn(self):
        result, pii_types = self.filter.mask_string(
            "SSN: 123-45-6789",
            self.filter._default_rules,
        )
        assert "123-45-6789" not in result
        assert "[SSN REDACTED]" in result

    def test_nested_dict_filtering(self):
        data = {
            "contact": {
                "name": "Sarah Chen",
                "email": "sarah@acme.com",
                "details": {
                    "phone": "+1 555-123-4567",
                    "notes": "SSN is 123-45-6789"
                }
            }
        }
        result = self.filter.filter_response(data, backend_id="hubspot")
        content = result.filtered_content
        assert "sarah@acme.com" not in str(content)
        assert "555-123-4567" not in str(content)
        assert "123-45-6789" not in str(content)
        assert result.masks_applied >= 3

    def test_excluded_fields_removed(self):
        config = BackendFilterConfig(
            backend_id="notion",
            excluded_fields={"internal_id", "raw_token"},
        )
        data = {
            "title": "My Page",
            "internal_id": "secret-123",
            "raw_token": "sk-xxx",
        }
        self.filter = ResultFilter(backend_configs={"notion": config})
        result = self.filter.filter_response(data, backend_id="notion")
        assert "internal_id" not in result.filtered_content
        assert "raw_token" not in result.filtered_content
        assert "title" in result.filtered_content

    def test_disabled_filter_passthrough(self):
        self.filter = ResultFilter(enabled=False)
        data = {"email": "secret@example.com"}
        result = self.filter.filter_response(data, backend_id="test")
        assert result.filtered_content == data
        assert result.masks_applied == 0

    def test_empty_content_handled(self):
        result = self.filter.filter_response(None, backend_id="test")
        assert result.filtered_content is None
        assert result.masks_applied == 0

    def test_api_key_masking(self):
        result, pii_types = self.filter.mask_string(
            "Use key sk-abc123def456ghi789jkl012mno345pqr678",
            self.filter._default_rules,
        )
        assert "sk-abc123" not in result
        assert "[API_KEY REDACTED]" in result

    def test_module_accessor_pattern(self):
        reset_result_filter()
        assert get_result_filter() is None

        rf = configure_result_filter(enabled=True)
        assert get_result_filter() is rf
        assert rf.enabled is True

        reset_result_filter()
        assert get_result_filter() is None
```

---

## Contract Verification Checklist

Before marking implementation complete, verify:

- [ ] `ResultFilter` class exists in `deeptrail-gateway/app/middleware/result_filter.py`
- [ ] All 6 PII types have compiled regex patterns
- [ ] `filter_response()` recursively traverses nested dicts and lists
- [ ] `filter_response()` returns `FilterResult` with audit metadata
- [ ] Per-backend configuration works (`BackendFilterConfig`)
- [ ] Excluded fields are removed from responses
- [ ] Allowlisted fields are preserved (not masked)
- [ ] Disabled filter passes content through unchanged
- [ ] Module accessor pattern: `get_result_filter()`, `configure_result_filter()`, `reset_result_filter()`
- [ ] Integration point: `tools_call.py` calls filter after backend response
- [ ] `main.py` calls `configure_result_filter()` during startup
- [ ] PII masking logged for audit (tool, backend, count, types)
- [ ] No false positives on short/normal strings
- [ ] Empty/null content handled gracefully
- [ ] All unit tests pass

---

## Security Considerations

| Aspect | Status | Notes |
|--------|--------|-------|
| PII in logs | Safe | Only log counts and types, never the actual PII values |
| Regex DoS (ReDoS) | Mitigated | Use non-backtracking patterns; test with pathological inputs |
| False negatives | Accepted | Regex-based detection is best-effort; not a compliance guarantee |
| Filter bypass | Fail-open | If filter errors, log and return unfiltered (availability > masking) |
| Binary content | Skip | Only filter string values; binary/base64 content is skipped |

---

## Validation Commands

### Unit Tests

```bash
cd deeptrail-gateway
pytest tests/middleware/test_result_filter.py -v
```

### Manual Verification

```bash
# Ensure services are running
docker compose up -d

# 1. Initialize MCP session
curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "method": "initialize", "id": 1,
    "params": {"protocolVersion": "2024-11-05", "capabilities": {},
               "clientInfo": {"name": "test", "version": "1.0.0"}}
  }'

# 2. Call a tool that returns PII-containing data
RESULT=$(curl -s -X POST http://localhost:8002/mcp \
  -H "Authorization: Bearer $AGENT_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "method": "tools/call", "id": 2,
    "params": {"name": "hubspot.search_contacts",
               "arguments": {"query": "sarah"}}
  }')

# 3. Verify PII is masked in response
echo "$RESULT" | jq '.'
# Expected: email addresses show as "[EMAIL REDACTED]"
# Expected: phone numbers show as "[PHONE REDACTED]"
```

---

## References

- **Architecture:** `deepsecure-comprehensive-architecture-consolidated.md` — MCP Governance Layer: "Result Filtering: Mask PII, remove sensitive fields"
- **Coverage Matrix:** `MVP_COVERAGE_MATRIX.md` — Result Filtering: 0% → target 80%+
- **Existing Patterns:** `deeptrail-gateway/app/middleware/audit.py` (module accessor), `deeptrail-gateway/app/core/security_filters.py` (regex pattern detection)
- **Upstream Dependencies:** MP3.5 (integration bugs fixed)
- **Downstream Dependents:** WS-J6 (governance layer must be in place before token exchange)
