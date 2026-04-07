"""
Result Filter for MCP tool call responses.

Inspects tool call responses from backend APIs and masks PII
(emails, phone numbers, SSNs, credit cards, API keys) before
returning results to agents.

Operates within the tools/call handler pipeline:
  Backend API → ResultFilter → Agent

Design principles:
- Per-backend configurability (different backends may have different PII rules)
- Recursive traversal (backend responses can be deeply nested JSON)
- Fail-open on errors (availability > masking — log and return unfiltered)
- Audit logging (log mask counts and PII types, never actual PII values)
- Module accessor pattern matching existing gateway middleware

Usage:
    from app.middleware.result_filter import get_result_filter, configure_result_filter

    configure_result_filter(enabled=True)

    rf = get_result_filter()
    result = rf.filter_response(backend_data, backend_id="hubspot")
    # result.filtered_content has PII masked
    # result.masks_applied shows how many masks were applied
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models
# =============================================================================


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
    partial_mask: bool = False
    visible_chars: int = 0


@dataclass
class BackendFilterConfig:
    """Per-backend filtering configuration."""
    backend_id: str
    enabled: bool = True
    masking_rules: List[MaskingRule] = field(default_factory=list)
    excluded_fields: Set[str] = field(default_factory=set)
    allowlisted_fields: Set[str] = field(default_factory=set)


@dataclass
class FilterResult:
    """Result of applying filters to a response."""
    filtered_content: Any
    masks_applied: int
    pii_types_found: List[PIIType]
    fields_excluded: int


# =============================================================================
# Default Configuration
# =============================================================================


DEFAULT_MASKING_RULES = [
    MaskingRule(pii_type=PIIType.EMAIL, replacement="[EMAIL REDACTED]"),
    MaskingRule(pii_type=PIIType.PHONE, replacement="[PHONE REDACTED]"),
    MaskingRule(pii_type=PIIType.SSN, replacement="[SSN REDACTED]"),
    MaskingRule(pii_type=PIIType.CREDIT_CARD, replacement="[CC REDACTED]"),
    MaskingRule(pii_type=PIIType.API_KEY, replacement="[API_KEY REDACTED]"),
    MaskingRule(pii_type=PIIType.IP_ADDRESS, enabled=False, replacement="[IP REDACTED]"),
]

# Minimum string length to consider for PII scanning.
# Strings shorter than this cannot contain any PII pattern.
_MIN_PII_LENGTH = 5

# Maximum string length for PII scanning to avoid ReDoS on huge blobs.
_MAX_PII_SCAN_LENGTH = 100_000


# =============================================================================
# PII Detection Patterns
# =============================================================================


def _compile_patterns() -> Dict[PIIType, List[re.Pattern]]:
    """Compile PII detection regex patterns.

    SSN is checked before PHONE to avoid the SSN pattern being partially
    consumed by a greedy phone regex. Order within each type doesn't matter
    because they are applied per-type based on MaskingRule ordering.
    """
    return {
        PIIType.EMAIL: [
            re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
        ],
        PIIType.SSN: [
            re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        ],
        PIIType.CREDIT_CARD: [
            re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
        ],
        PIIType.PHONE: [
            re.compile(
                r"(?<!\d)"
                r"(?:\+?1[-.\s]?)?"
                r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
                r"(?!\d)"
            ),
        ],
        PIIType.API_KEY: [
            re.compile(r"\bsk-[a-zA-Z0-9]{32,}\b"),
            re.compile(r"\bxoxb-[a-zA-Z0-9\-]+\b"),
            re.compile(r"\bBearer\s+[a-zA-Z0-9._\-]{20,}\b"),
        ],
        PIIType.IP_ADDRESS: [
            re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
        ],
    }


# =============================================================================
# ResultFilter
# =============================================================================


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
        self.enabled = enabled
        self._default_rules = default_rules or list(DEFAULT_MASKING_RULES)
        self._backend_configs = backend_configs or {}
        self._patterns = _compile_patterns()

        # Build a lookup for rule ordering so SSN is applied before PHONE
        self._rule_order = [
            PIIType.SSN,
            PIIType.CREDIT_CARD,
            PIIType.EMAIL,
            PIIType.API_KEY,
            PIIType.PHONE,
            PIIType.IP_ADDRESS,
        ]

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def filter_response(
        self,
        content: Any,
        backend_id: str,
        tool_name: Optional[str] = None,
    ) -> FilterResult:
        """Filter a tool call response, masking PII and excluding fields."""
        if not self.enabled:
            return FilterResult(
                filtered_content=content,
                masks_applied=0,
                pii_types_found=[],
                fields_excluded=0,
            )

        if content is None:
            return FilterResult(
                filtered_content=None,
                masks_applied=0,
                pii_types_found=[],
                fields_excluded=0,
            )

        try:
            config = self.get_config_for_backend(backend_id)
            rules = config.masking_rules if config.masking_rules else self._default_rules

            if isinstance(content, dict):
                filtered, masks, pii_types, excluded = self._filter_dict(content, config, rules)
            elif isinstance(content, list):
                filtered, masks, pii_types = self._filter_list(content, config, rules)
                excluded = 0
            elif isinstance(content, str):
                filtered, pii_types = self.mask_string(content, rules)
                masks = 1 if pii_types else 0
                excluded = 0
            else:
                return FilterResult(
                    filtered_content=content,
                    masks_applied=0,
                    pii_types_found=[],
                    fields_excluded=0,
                )

            unique_types = list(dict.fromkeys(pii_types))

            return FilterResult(
                filtered_content=filtered,
                masks_applied=masks,
                pii_types_found=unique_types,
                fields_excluded=excluded,
            )
        except Exception:
            logger.error(
                "Result filter error — returning unfiltered content",
                exc_info=True,
            )
            return FilterResult(
                filtered_content=content,
                masks_applied=0,
                pii_types_found=[],
                fields_excluded=0,
            )

    def mask_string(
        self, value: str, rules: List[MaskingRule]
    ) -> Tuple[str, List[PIIType]]:
        """Apply PII masking rules to a string value.

        Returns (masked_string, list_of_pii_types_found).
        """
        if len(value) < _MIN_PII_LENGTH:
            return value, []

        if len(value) > _MAX_PII_SCAN_LENGTH:
            return value, []

        # Skip likely binary / base64 content (high ratio of non-printable chars)
        if _looks_like_binary(value):
            return value, []

        pii_found: List[PIIType] = []
        result = value

        rules_by_type = {r.pii_type: r for r in rules}

        for pii_type in self._rule_order:
            rule = rules_by_type.get(pii_type)
            if rule is None or not rule.enabled:
                continue

            patterns = self._patterns.get(pii_type, [])
            for pattern in patterns:
                if pattern.search(result):
                    result = pattern.sub(rule.replacement, result)
                    if pii_type not in pii_found:
                        pii_found.append(pii_type)

        return result, pii_found

    def get_config_for_backend(self, backend_id: str) -> BackendFilterConfig:
        """Get filter config, falling back to defaults if no backend-specific config."""
        if backend_id in self._backend_configs:
            return self._backend_configs[backend_id]
        return BackendFilterConfig(backend_id=backend_id)

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _filter_dict(
        self,
        data: Dict[str, Any],
        config: BackendFilterConfig,
        rules: List[MaskingRule],
    ) -> Tuple[Dict[str, Any], int, List[PIIType], int]:
        """Recursively filter a dictionary, masking PII in string values.

        Returns (filtered_dict, masks_applied, pii_types_found, fields_excluded).
        """
        filtered: Dict[str, Any] = {}
        total_masks = 0
        all_pii: List[PIIType] = []
        excluded_count = 0

        for key, val in data.items():
            if key in config.excluded_fields:
                excluded_count += 1
                continue

            if key in config.allowlisted_fields:
                filtered[key] = val
                continue

            if isinstance(val, dict):
                sub, masks, pii, exc = self._filter_dict(val, config, rules)
                filtered[key] = sub
                total_masks += masks
                all_pii.extend(pii)
                excluded_count += exc
            elif isinstance(val, list):
                sub, masks, pii = self._filter_list(val, config, rules)
                filtered[key] = sub
                total_masks += masks
                all_pii.extend(pii)
            elif isinstance(val, str):
                masked, pii = self.mask_string(val, rules)
                filtered[key] = masked
                if pii:
                    total_masks += 1
                    all_pii.extend(pii)
            else:
                filtered[key] = val

        return filtered, total_masks, all_pii, excluded_count

    def _filter_list(
        self,
        data: List[Any],
        config: BackendFilterConfig,
        rules: List[MaskingRule],
    ) -> Tuple[List[Any], int, List[PIIType]]:
        """Recursively filter a list."""
        filtered: List[Any] = []
        total_masks = 0
        all_pii: List[PIIType] = []

        for item in data:
            if isinstance(item, dict):
                sub, masks, pii, _ = self._filter_dict(item, config, rules)
                filtered.append(sub)
                total_masks += masks
                all_pii.extend(pii)
            elif isinstance(item, list):
                sub, masks, pii = self._filter_list(item, config, rules)
                filtered.append(sub)
                total_masks += masks
                all_pii.extend(pii)
            elif isinstance(item, str):
                masked, pii = self.mask_string(item, rules)
                filtered.append(masked)
                if pii:
                    total_masks += 1
                    all_pii.extend(pii)
            else:
                filtered.append(item)

        return filtered, total_masks, all_pii


# =============================================================================
# Utility
# =============================================================================


def _looks_like_binary(value: str) -> bool:
    """Heuristic: skip strings that look like binary/base64 encoded data."""
    if len(value) < 64:
        return False
    sample = value[:256]
    non_ascii = sum(1 for c in sample if ord(c) > 127 or ord(c) < 9)
    return (non_ascii / len(sample)) > 0.3


# =============================================================================
# Module-Level Accessor Pattern
# =============================================================================


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
    logger.info("Result filter configured: enabled=%s", enabled)
    return _result_filter


def reset_result_filter() -> None:
    """Reset result filter (for testing)."""
    global _result_filter
    _result_filter = None
