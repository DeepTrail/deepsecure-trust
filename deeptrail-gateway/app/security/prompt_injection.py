"""
Prompt Injection Detection for MCP tool call arguments.

Inspects tool call arguments for LLM-specific attack patterns
(instruction overrides, data exfiltration, privilege escalation,
encoding evasion, delimiter injection, role manipulation) and
blocks requests exceeding a configurable threat threshold.

Operates within the tools/call handler pipeline:
  Agent args → PromptInjectionDetector → Backend API (or block)

Complements existing security layers:
- security_filters.py — traditional web attacks (XSS, SQLi)
- result_filter.py (WS-J4) — output-side PII masking
- This module — input-side LLM prompt injection

Industry reference: OWASP Top 10 for LLM Applications — LLM01

Usage:
    from app.security.prompt_injection import (
        get_prompt_injection_detector, configure_prompt_injection_detector,
    )

    configure_prompt_injection_detector()

    det = get_prompt_injection_detector()
    scan = det.scan_arguments({"query": user_input}, tool_name="notion.search_pages")
    if scan.is_blocked:
        raise MCPError(...)
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Minimum string length to consider for scanning.
_MIN_SCAN_LENGTH = 8

# Maximum string length for full scanning (ReDoS guard).
_MAX_SCAN_LENGTH = 100_000


# =============================================================================
# Data Models
# =============================================================================


class ThreatLevel(str, Enum):
    """Severity of detected prompt injection attempt."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Ordered for comparison (higher index = more severe)
_THREAT_SEVERITY = {
    ThreatLevel.NONE: 0,
    ThreatLevel.LOW: 1,
    ThreatLevel.MEDIUM: 2,
    ThreatLevel.HIGH: 3,
    ThreatLevel.CRITICAL: 4,
}


class DetectionCategory(str, Enum):
    """Categories of prompt injection patterns."""
    INSTRUCTION_OVERRIDE = "instruction_override"
    DATA_EXFILTRATION = "data_exfiltration"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    ENCODING_EVASION = "encoding_evasion"
    DELIMITER_INJECTION = "delimiter_injection"
    ROLE_MANIPULATION = "role_manipulation"


@dataclass
class DetectionResult:
    """Result of prompt injection analysis on a single value."""
    is_threat: bool
    threat_level: ThreatLevel
    category: Optional[DetectionCategory] = None
    pattern_matched: Optional[str] = None
    matched_text: Optional[str] = None


@dataclass
class ScanResult:
    """Aggregate result of scanning all tool arguments."""
    is_blocked: bool
    threat_level: ThreatLevel
    detections: List[DetectionResult] = field(default_factory=list)
    scanned_fields: int = 0
    tool_name: Optional[str] = None

    @property
    def detection_count(self) -> int:
        return len([d for d in self.detections if d.is_threat])


@dataclass
class PromptInjectionConfig:
    """Configuration for the prompt injection detector."""
    enabled: bool = True
    block_threshold: ThreatLevel = ThreatLevel.MEDIUM
    max_argument_length: int = 10_000
    tool_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    custom_deny_patterns: List[str] = field(default_factory=list)
    log_all_scans: bool = False


# =============================================================================
# Pattern Definitions
# =============================================================================

# Each entry: (compiled_pattern, threat_level, description)
PatternEntry = tuple[re.Pattern, ThreatLevel, str]


def _compile_instruction_override_patterns() -> List[PatternEntry]:
    return [
        (re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.IGNORECASE),
         ThreatLevel.HIGH, "ignore_previous_instructions"),
        (re.compile(r"disregard\s+(?:all\s+)?(?:prior|previous|above)\s+(?:instructions|rules|guidelines)", re.IGNORECASE),
         ThreatLevel.HIGH, "disregard_prior_rules"),
        (re.compile(r"forget\s+(?:everything|all)\s+(?:you|that)", re.IGNORECASE),
         ThreatLevel.HIGH, "forget_everything"),
        (re.compile(r"override\s+(?:system|safety|security)\s+(?:prompt|rules|policy)", re.IGNORECASE),
         ThreatLevel.CRITICAL, "override_system_prompt"),
        (re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
         ThreatLevel.MEDIUM, "new_instructions"),
        (re.compile(r"do\s+not\s+follow\s+(?:the\s+)?(?:previous|original|above)", re.IGNORECASE),
         ThreatLevel.HIGH, "do_not_follow"),
    ]


def _compile_data_exfiltration_patterns() -> List[PatternEntry]:
    return [
        (re.compile(r"(?:include|embed|insert)\s+.*(?:password|secret|key|token|credential)", re.IGNORECASE),
         ThreatLevel.HIGH, "embed_secrets"),
        (re.compile(r"(?:send|transmit|post|write)\s+.*\s+to\s+https?://", re.IGNORECASE),
         ThreatLevel.HIGH, "send_to_url"),
        (re.compile(r"(?:read|access|get|fetch)\s+.*(?:env|environment|config|\.env)", re.IGNORECASE),
         ThreatLevel.MEDIUM, "read_env"),
        (re.compile(r"https?://[^\s]{10,}\?[^\s]*(?:data|exfil|leak|steal)=", re.IGNORECASE),
         ThreatLevel.MEDIUM, "exfil_url_param"),
    ]


def _compile_privilege_escalation_patterns() -> List[PatternEntry]:
    return [
        (re.compile(r"(?:act|behave)\s+as\s+(?:an?\s+)?(?:admin|root|superuser|system)", re.IGNORECASE),
         ThreatLevel.HIGH, "act_as_admin"),
        (re.compile(r"(?:grant|give|assign)\s+(?:me|yourself)\s+(?:admin|elevated|full)\s+(?:access|permissions|privileges)", re.IGNORECASE),
         ThreatLevel.HIGH, "grant_admin"),
        (re.compile(r"(?:sudo\b|root\s+access|privilege\s+escalat)", re.IGNORECASE),
         ThreatLevel.MEDIUM, "sudo_root"),
        (re.compile(r"(?:bypass|skip|disable)\s+(?:auth|security|permission|validation)", re.IGNORECASE),
         ThreatLevel.CRITICAL, "bypass_security"),
    ]


def _compile_encoding_evasion_patterns() -> List[PatternEntry]:
    return [
        (re.compile(r"[A-Za-z0-9+/]{100,}={0,2}"),
         ThreatLevel.MEDIUM, "large_base64_block"),
        (re.compile(r"(?:\\x[0-9a-fA-F]{2}){4,}"),
         ThreatLevel.MEDIUM, "hex_encoded_sequence"),
        (re.compile(r"(?:\\u[0-9a-fA-F]{4}){4,}"),
         ThreatLevel.MEDIUM, "unicode_escape_sequence"),
        (re.compile(r"(.)\1{15,}"),
         ThreatLevel.LOW, "excessive_repeated_chars"),
    ]


def _compile_delimiter_injection_patterns() -> List[PatternEntry]:
    return [
        (re.compile(r"<\|?(?:system|user|assistant)\|?>", re.IGNORECASE),
         ThreatLevel.CRITICAL, "llm_delimiter_tag"),
        (re.compile(r"\[INST\].*?\[/INST\]", re.IGNORECASE | re.DOTALL),
         ThreatLevel.CRITICAL, "inst_tags"),
        (re.compile(r"###\s*(?:system|instruction|human|assistant)", re.IGNORECASE),
         ThreatLevel.HIGH, "markdown_delimiter"),
        (re.compile(r"<\s*(?:system|instruction)_prompt\s*>", re.IGNORECASE),
         ThreatLevel.CRITICAL, "system_prompt_tag"),
    ]


def _compile_role_manipulation_patterns() -> List[PatternEntry]:
    return [
        (re.compile(r"you\s+are\s+(?:now\s+)?(?:an?\s+)?(?:admin|different|new|unrestricted)", re.IGNORECASE),
         ThreatLevel.HIGH, "you_are_now"),
        (re.compile(r"(?:switch|change)\s+(?:to|into)\s+(?:admin|developer|debug)\s+mode", re.IGNORECASE),
         ThreatLevel.MEDIUM, "switch_mode"),
        (re.compile(r"(?:enter|activate)\s+(?:god|admin|root|developer)\s+mode", re.IGNORECASE),
         ThreatLevel.HIGH, "activate_god_mode"),
    ]


# =============================================================================
# PromptInjectionDetector
# =============================================================================


class PromptInjectionDetector:
    """
    Detects prompt injection attempts in MCP tool call arguments.

    Inspects string values in tool arguments for known injection patterns
    including instruction overrides, data exfiltration, privilege escalation,
    encoding evasion, and delimiter injection.
    """

    def __init__(self, config: Optional[PromptInjectionConfig] = None):
        self.config = config or PromptInjectionConfig()
        self._patterns: Dict[DetectionCategory, List[PatternEntry]] = {
            DetectionCategory.INSTRUCTION_OVERRIDE: _compile_instruction_override_patterns(),
            DetectionCategory.DATA_EXFILTRATION: _compile_data_exfiltration_patterns(),
            DetectionCategory.PRIVILEGE_ESCALATION: _compile_privilege_escalation_patterns(),
            DetectionCategory.ENCODING_EVASION: _compile_encoding_evasion_patterns(),
            DetectionCategory.DELIMITER_INJECTION: _compile_delimiter_injection_patterns(),
            DetectionCategory.ROLE_MANIPULATION: _compile_role_manipulation_patterns(),
        }
        self._custom_patterns: List[re.Pattern] = [
            re.compile(p, re.IGNORECASE) for p in self.config.custom_deny_patterns
        ]

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def scan_arguments(
        self,
        arguments: Dict[str, Any],
        tool_name: Optional[str] = None,
    ) -> ScanResult:
        """Scan all tool call arguments for prompt injection patterns."""
        effective_config = self._get_effective_config(tool_name)

        if not effective_config.enabled:
            return ScanResult(
                is_blocked=False,
                threat_level=ThreatLevel.NONE,
                tool_name=tool_name,
            )

        try:
            all_detections: List[DetectionResult] = []
            scanned = 0

            self._scan_value_recursive(arguments, all_detections, scanned_counter := [0], effective_config)
            scanned = scanned_counter[0]

            highest = ThreatLevel.NONE
            for d in all_detections:
                if _THREAT_SEVERITY[d.threat_level] > _THREAT_SEVERITY[highest]:
                    highest = d.threat_level

            is_blocked = _THREAT_SEVERITY[highest] >= _THREAT_SEVERITY[effective_config.block_threshold]

            result = ScanResult(
                is_blocked=is_blocked,
                threat_level=highest,
                detections=all_detections,
                scanned_fields=scanned,
                tool_name=tool_name,
            )

            if effective_config.log_all_scans or is_blocked:
                level = logging.WARNING if is_blocked else logging.DEBUG
                logger.log(
                    level,
                    "Prompt injection scan: tool=%s blocked=%s threat=%s detections=%d",
                    tool_name,
                    is_blocked,
                    highest.value,
                    result.detection_count,
                )

            return result

        except Exception:
            logger.error("Prompt injection detector error — allowing request", exc_info=True)
            return ScanResult(
                is_blocked=False,
                threat_level=ThreatLevel.NONE,
                tool_name=tool_name,
            )

    def scan_value(self, value: str) -> List[DetectionResult]:
        """Scan a single string value for injection patterns.

        Returns list of all detections found in the value.
        """
        detections: List[DetectionResult] = []

        if len(value) < _MIN_SCAN_LENGTH:
            return detections

        if len(value) > _MAX_SCAN_LENGTH:
            return detections

        detections.extend(self._check_delimiter_injection(value))
        detections.extend(self._check_instruction_override(value))
        detections.extend(self._check_privilege_escalation(value))
        detections.extend(self._check_role_manipulation(value))
        detections.extend(self._check_data_exfiltration(value))
        detections.extend(self._check_encoding_evasion(value))

        for cp in self._custom_patterns:
            if cp.search(value):
                detections.append(DetectionResult(
                    is_threat=True,
                    threat_level=ThreatLevel.HIGH,
                    category=None,
                    pattern_matched="custom_deny_pattern",
                ))

        return detections

    # -----------------------------------------------------------------
    # Category-specific checkers
    # -----------------------------------------------------------------

    def _check_instruction_override(self, value: str) -> List[DetectionResult]:
        return self._run_category(DetectionCategory.INSTRUCTION_OVERRIDE, value)

    def _check_data_exfiltration(self, value: str) -> List[DetectionResult]:
        return self._run_category(DetectionCategory.DATA_EXFILTRATION, value)

    def _check_privilege_escalation(self, value: str) -> List[DetectionResult]:
        return self._run_category(DetectionCategory.PRIVILEGE_ESCALATION, value)

    def _check_encoding_evasion(self, value: str) -> List[DetectionResult]:
        return self._run_category(DetectionCategory.ENCODING_EVASION, value)

    def _check_delimiter_injection(self, value: str) -> List[DetectionResult]:
        return self._run_category(DetectionCategory.DELIMITER_INJECTION, value)

    def _check_role_manipulation(self, value: str) -> List[DetectionResult]:
        return self._run_category(DetectionCategory.ROLE_MANIPULATION, value)

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _run_category(
        self, category: DetectionCategory, value: str
    ) -> List[DetectionResult]:
        results: List[DetectionResult] = []
        for pattern, threat_level, name in self._patterns[category]:
            if pattern.search(value):
                results.append(DetectionResult(
                    is_threat=True,
                    threat_level=threat_level,
                    category=category,
                    pattern_matched=name,
                ))
        return results

    def _scan_value_recursive(
        self,
        data: Any,
        detections: List[DetectionResult],
        counter: List[int],
        config: PromptInjectionConfig,
    ) -> None:
        """Recursively scan all string values in a dict/list/string."""
        if isinstance(data, dict):
            for val in data.values():
                self._scan_value_recursive(val, detections, counter, config)
        elif isinstance(data, list):
            for item in data:
                self._scan_value_recursive(item, detections, counter, config)
        elif isinstance(data, str):
            counter[0] += 1
            if len(data) > config.max_argument_length:
                detections.append(DetectionResult(
                    is_threat=True,
                    threat_level=ThreatLevel.LOW,
                    category=DetectionCategory.ENCODING_EVASION,
                    pattern_matched="excessive_argument_length",
                ))
            found = self.scan_value(data)
            detections.extend(found)

    def _get_effective_config(
        self, tool_name: Optional[str]
    ) -> PromptInjectionConfig:
        """Get config with tool-specific overrides applied."""
        if not tool_name or tool_name not in self.config.tool_overrides:
            return self.config

        overrides = self.config.tool_overrides[tool_name]
        return PromptInjectionConfig(
            enabled=overrides.get("enabled", self.config.enabled),
            block_threshold=ThreatLevel(overrides["block_threshold"])
            if "block_threshold" in overrides else self.config.block_threshold,
            max_argument_length=overrides.get(
                "max_argument_length", self.config.max_argument_length
            ),
            tool_overrides={},
            custom_deny_patterns=overrides.get(
                "custom_deny_patterns", self.config.custom_deny_patterns
            ),
            log_all_scans=overrides.get("log_all_scans", self.config.log_all_scans),
        )


# =============================================================================
# Module-Level Accessor Pattern
# =============================================================================


_detector: Optional[PromptInjectionDetector] = None


def get_prompt_injection_detector() -> Optional[PromptInjectionDetector]:
    """Get the configured PromptInjectionDetector instance."""
    return _detector


def configure_prompt_injection_detector(
    config: Optional[PromptInjectionConfig] = None,
) -> PromptInjectionDetector:
    """Configure and store the global PromptInjectionDetector."""
    global _detector
    _detector = PromptInjectionDetector(config=config)
    logger.info(
        "Prompt injection detector configured: enabled=%s, threshold=%s",
        _detector.config.enabled,
        _detector.config.block_threshold.value,
    )
    return _detector


def reset_prompt_injection_detector() -> None:
    """Reset detector (for testing)."""
    global _detector
    _detector = None
