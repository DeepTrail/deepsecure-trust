"""
Tests for ResultFilter (WS-J4: PII Masking).

Covers:
- Individual PII type masking (email, phone, SSN, credit card, API key, IP)
- False positive avoidance
- Recursive dict/list traversal
- Excluded and allowlisted fields
- Per-backend configuration
- Disabled filter and disabled individual rules
- FilterResult audit metadata
- Module accessor lifecycle (configure / get / reset)
- Edge cases (empty, null, non-string values, binary content)
"""

import pytest

from app.middleware.result_filter import (
    BackendFilterConfig,
    MaskingRule,
    PIIType,
    ResultFilter,
    configure_result_filter,
    get_result_filter,
    reset_result_filter,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def _reset_global_filter():
    """Reset the global result filter singleton before and after each test."""
    reset_result_filter()
    yield
    reset_result_filter()


@pytest.fixture
def rf() -> ResultFilter:
    """Standard result filter with default rules."""
    return ResultFilter()


# =============================================================================
# PII Masking — Individual Types
# =============================================================================


class TestMaskEmail:
    def test_mask_email_basic(self, rf: ResultFilter):
        result, pii = rf.mask_string("Contact sarah@acme.com for details", rf._default_rules)
        assert "sarah@acme.com" not in result
        assert "[EMAIL REDACTED]" in result
        assert PIIType.EMAIL in pii

    def test_mask_email_with_plus(self, rf: ResultFilter):
        result, pii = rf.mask_string("Send to user+tag@example.org", rf._default_rules)
        assert "[EMAIL REDACTED]" in result
        assert PIIType.EMAIL in pii

    def test_mask_multiple_emails(self, rf: ResultFilter):
        text = "cc: alice@foo.com and bob@bar.io"
        result, pii = rf.mask_string(text, rf._default_rules)
        assert "alice@foo.com" not in result
        assert "bob@bar.io" not in result
        assert result.count("[EMAIL REDACTED]") == 2


class TestMaskPhone:
    def test_mask_phone_us_format(self, rf: ResultFilter):
        result, pii = rf.mask_string("Call +1 (555) 123-4567", rf._default_rules)
        assert "(555) 123-4567" not in result
        assert "[PHONE REDACTED]" in result
        assert PIIType.PHONE in pii

    def test_mask_phone_plain(self, rf: ResultFilter):
        result, pii = rf.mask_string("Phone: 555-123-4567", rf._default_rules)
        assert "555-123-4567" not in result
        assert "[PHONE REDACTED]" in result

    def test_mask_phone_dots(self, rf: ResultFilter):
        result, pii = rf.mask_string("Phone: 555.123.4567", rf._default_rules)
        assert "555.123.4567" not in result
        assert "[PHONE REDACTED]" in result


class TestMaskSSN:
    def test_mask_ssn(self, rf: ResultFilter):
        result, pii = rf.mask_string("SSN: 123-45-6789", rf._default_rules)
        assert "123-45-6789" not in result
        assert "[SSN REDACTED]" in result
        assert PIIType.SSN in pii

    def test_ssn_not_confused_with_phone(self, rf: ResultFilter):
        """SSN should be detected as SSN, not phone."""
        result, pii = rf.mask_string("SSN: 123-45-6789", rf._default_rules)
        assert PIIType.SSN in pii


class TestMaskCreditCard:
    def test_mask_cc_with_dashes(self, rf: ResultFilter):
        result, pii = rf.mask_string("CC: 4111-1111-1111-1111", rf._default_rules)
        assert "4111-1111-1111-1111" not in result
        assert "[CC REDACTED]" in result
        assert PIIType.CREDIT_CARD in pii

    def test_mask_cc_with_spaces(self, rf: ResultFilter):
        result, pii = rf.mask_string("CC: 4111 1111 1111 1111", rf._default_rules)
        assert "4111 1111 1111 1111" not in result
        assert "[CC REDACTED]" in result

    def test_mask_cc_no_separator(self, rf: ResultFilter):
        result, pii = rf.mask_string("CC: 4111111111111111", rf._default_rules)
        assert "4111111111111111" not in result
        assert "[CC REDACTED]" in result


class TestMaskAPIKey:
    def test_mask_openai_key(self, rf: ResultFilter):
        key = "sk-abc123def456ghi789jkl012mno345pqr678"
        result, pii = rf.mask_string(f"Use key {key}", rf._default_rules)
        assert key not in result
        assert "[API_KEY REDACTED]" in result
        assert PIIType.API_KEY in pii

    def test_mask_slack_bot_token(self, rf: ResultFilter):
        result, pii = rf.mask_string(
            "Token: xoxb-123456-789012-abcdef", rf._default_rules
        )
        assert "xoxb-" not in result
        assert "[API_KEY REDACTED]" in result
        assert PIIType.API_KEY in pii

    def test_mask_bearer_token(self, rf: ResultFilter):
        result, pii = rf.mask_string(
            "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature",
            rf._default_rules,
        )
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "[API_KEY REDACTED]" in result


class TestMaskIPAddress:
    def test_ip_disabled_by_default(self, rf: ResultFilter):
        result, pii = rf.mask_string("Server at 192.168.1.100", rf._default_rules)
        assert "192.168.1.100" in result
        assert PIIType.IP_ADDRESS not in pii

    def test_ip_enabled_when_configured(self):
        rules = [
            MaskingRule(pii_type=PIIType.IP_ADDRESS, enabled=True, replacement="[IP REDACTED]"),
        ]
        rf = ResultFilter(default_rules=rules)
        result, pii = rf.mask_string("Server at 192.168.1.100", rules)
        assert "192.168.1.100" not in result
        assert "[IP REDACTED]" in result
        assert PIIType.IP_ADDRESS in pii


# =============================================================================
# False Positive Avoidance
# =============================================================================


class TestFalsePositives:
    def test_short_string_unchanged(self, rf: ResultFilter):
        result, pii = rf.mask_string("test", rf._default_rules)
        assert result == "test"
        assert pii == []

    def test_normal_string_unchanged(self, rf: ResultFilter):
        result, pii = rf.mask_string("Hello, world!", rf._default_rules)
        assert result == "Hello, world!"
        assert pii == []

    def test_numbers_not_masked(self, rf: ResultFilter):
        result, pii = rf.mask_string("Order #12345 confirmed", rf._default_rules)
        assert result == "Order #12345 confirmed"
        assert pii == []

    def test_empty_string(self, rf: ResultFilter):
        result, pii = rf.mask_string("", rf._default_rules)
        assert result == ""
        assert pii == []

    def test_version_string_not_masked(self, rf: ResultFilter):
        result, pii = rf.mask_string("Version 2.1.0", rf._default_rules)
        assert result == "Version 2.1.0"
        assert pii == []


# =============================================================================
# Multiple PII in One String
# =============================================================================


class TestMultiplePII:
    def test_email_and_phone(self, rf: ResultFilter):
        text = "Email: sarah@acme.com, Phone: 555-123-4567"
        result, pii = rf.mask_string(text, rf._default_rules)
        assert "sarah@acme.com" not in result
        assert "555-123-4567" not in result
        assert PIIType.EMAIL in pii
        assert PIIType.PHONE in pii

    def test_three_pii_types(self, rf: ResultFilter):
        text = "Email: a@b.com SSN: 123-45-6789 CC: 4111-1111-1111-1111"
        result, pii = rf.mask_string(text, rf._default_rules)
        assert PIIType.EMAIL in pii
        assert PIIType.SSN in pii
        assert PIIType.CREDIT_CARD in pii


# =============================================================================
# filter_response — Dict Traversal
# =============================================================================


class TestFilterResponseDict:
    def test_nested_dict(self, rf: ResultFilter):
        data = {
            "contact": {
                "name": "Sarah Chen",
                "email": "sarah@acme.com",
                "details": {
                    "phone": "+1 555-123-4567",
                    "notes": "SSN is 123-45-6789",
                },
            }
        }
        result = rf.filter_response(data, backend_id="notion")
        content = result.filtered_content
        assert "sarah@acme.com" not in str(content)
        assert "555-123-4567" not in str(content)
        assert "123-45-6789" not in str(content)
        assert result.masks_applied >= 3
        assert "Sarah Chen" in content["contact"]["name"]

    def test_only_string_values_masked(self, rf: ResultFilter):
        data = {
            "email": "user@example.com",
            "count": 42,
            "active": True,
            "score": 3.14,
        }
        result = rf.filter_response(data, backend_id="test")
        c = result.filtered_content
        assert c["count"] == 42
        assert c["active"] is True
        assert c["score"] == 3.14
        assert "[EMAIL REDACTED]" in c["email"]

    def test_dict_keys_not_masked(self, rf: ResultFilter):
        data = {"email_address": "user@example.com"}
        result = rf.filter_response(data, backend_id="test")
        assert "email_address" in result.filtered_content


class TestFilterResponseList:
    def test_list_of_strings(self, rf: ResultFilter):
        data = ["alice@foo.com", "hello", "bob@bar.io"]
        result = rf.filter_response(data, backend_id="test")
        assert result.filtered_content[0] == "[EMAIL REDACTED]"
        assert result.filtered_content[1] == "hello"
        assert result.filtered_content[2] == "[EMAIL REDACTED]"

    def test_list_of_dicts(self, rf: ResultFilter):
        data = [
            {"name": "Alice", "email": "alice@acme.com"},
            {"name": "Bob", "email": "bob@acme.com"},
        ]
        result = rf.filter_response(data, backend_id="test")
        for item in result.filtered_content:
            assert "[EMAIL REDACTED]" in item["email"]
        assert result.masks_applied == 2


# =============================================================================
# Excluded and Allowlisted Fields
# =============================================================================


class TestExcludedFields:
    def test_excluded_fields_removed(self):
        config = BackendFilterConfig(
            backend_id="notion",
            excluded_fields={"internal_id", "raw_token"},
        )
        rf = ResultFilter(backend_configs={"notion": config})
        data = {
            "title": "My Page",
            "internal_id": "secret-123",
            "raw_token": "sk-xxx",
        }
        result = rf.filter_response(data, backend_id="notion")
        assert "internal_id" not in result.filtered_content
        assert "raw_token" not in result.filtered_content
        assert "title" in result.filtered_content
        assert result.fields_excluded == 2


class TestAllowlistedFields:
    def test_allowlisted_fields_preserved(self):
        config = BackendFilterConfig(
            backend_id="notion",
            allowlisted_fields={"owner_email"},
        )
        rf = ResultFilter(backend_configs={"notion": config})
        data = {
            "owner_email": "sarah@acme.com",
            "contact_email": "user@example.com",
        }
        result = rf.filter_response(data, backend_id="notion")
        assert result.filtered_content["owner_email"] == "sarah@acme.com"
        assert "[EMAIL REDACTED]" in result.filtered_content["contact_email"]


# =============================================================================
# Disabled Filter / Disabled Rules
# =============================================================================


class TestDisabledFilter:
    def test_disabled_filter_passthrough(self):
        rf = ResultFilter(enabled=False)
        data = {"email": "secret@example.com"}
        result = rf.filter_response(data, backend_id="test")
        assert result.filtered_content == data
        assert result.masks_applied == 0
        assert result.pii_types_found == []

    def test_disabled_individual_rule(self):
        rules = [
            MaskingRule(pii_type=PIIType.EMAIL, enabled=False),
            MaskingRule(pii_type=PIIType.PHONE, replacement="[PHONE REDACTED]"),
        ]
        rf = ResultFilter(default_rules=rules)
        data = {"info": "Email: user@test.com Phone: 555-123-4567"}
        result = rf.filter_response(data, backend_id="test")
        assert "user@test.com" in result.filtered_content["info"]
        assert "[PHONE REDACTED]" in result.filtered_content["info"]


# =============================================================================
# Backend-Specific Config
# =============================================================================


class TestBackendConfig:
    def test_backend_specific_rules(self):
        notion_config = BackendFilterConfig(
            backend_id="notion",
            masking_rules=[
                MaskingRule(pii_type=PIIType.EMAIL, replacement="[NOTION EMAIL]"),
            ],
        )
        rf = ResultFilter(backend_configs={"notion": notion_config})
        result = rf.filter_response(
            {"email": "user@test.com"}, backend_id="notion"
        )
        assert "[NOTION EMAIL]" in result.filtered_content["email"]

    def test_default_config_fallback(self, rf: ResultFilter):
        config = rf.get_config_for_backend("unknown_backend")
        assert config.backend_id == "unknown_backend"
        assert config.enabled is True
        assert config.masking_rules == []
        assert config.excluded_fields == set()


# =============================================================================
# FilterResult Metadata
# =============================================================================


class TestFilterResultMetadata:
    def test_masks_applied_count(self, rf: ResultFilter):
        data = {
            "a": "user@test.com",
            "b": "555-123-4567",
        }
        result = rf.filter_response(data, backend_id="test")
        assert result.masks_applied == 2

    def test_pii_types_found_populated(self, rf: ResultFilter):
        data = {"info": "Email: u@t.com SSN: 123-45-6789"}
        result = rf.filter_response(data, backend_id="test")
        assert PIIType.EMAIL in result.pii_types_found
        assert PIIType.SSN in result.pii_types_found

    def test_no_duplicates_in_pii_types(self, rf: ResultFilter):
        data = {
            "a": "alice@foo.com",
            "b": "bob@bar.com",
        }
        result = rf.filter_response(data, backend_id="test")
        email_count = result.pii_types_found.count(PIIType.EMAIL)
        assert email_count == 1


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    def test_none_content(self, rf: ResultFilter):
        result = rf.filter_response(None, backend_id="test")
        assert result.filtered_content is None
        assert result.masks_applied == 0

    def test_string_content(self, rf: ResultFilter):
        result = rf.filter_response("user@test.com", backend_id="test")
        assert "[EMAIL REDACTED]" in result.filtered_content
        assert result.masks_applied == 1

    def test_integer_content(self, rf: ResultFilter):
        result = rf.filter_response(42, backend_id="test")
        assert result.filtered_content == 42
        assert result.masks_applied == 0

    def test_boolean_content(self, rf: ResultFilter):
        result = rf.filter_response(True, backend_id="test")
        assert result.filtered_content is True
        assert result.masks_applied == 0

    def test_deeply_nested(self, rf: ResultFilter):
        data = {"l1": {"l2": {"l3": {"l4": {"email": "deep@nested.com"}}}}}
        result = rf.filter_response(data, backend_id="test")
        deep_val = result.filtered_content["l1"]["l2"]["l3"]["l4"]["email"]
        assert "[EMAIL REDACTED]" in deep_val

    def test_mixed_list(self, rf: ResultFilter):
        data = [42, "user@test.com", True, None, {"phone": "555-123-4567"}]
        result = rf.filter_response(data, backend_id="test")
        c = result.filtered_content
        assert c[0] == 42
        assert "[EMAIL REDACTED]" in c[1]
        assert c[2] is True
        assert c[3] is None
        assert "[PHONE REDACTED]" in c[4]["phone"]


# =============================================================================
# Module Accessor Pattern
# =============================================================================


class TestModuleAccessors:
    def test_lifecycle(self):
        assert get_result_filter() is None

        rf = configure_result_filter(enabled=True)
        assert get_result_filter() is rf
        assert rf.enabled is True

        reset_result_filter()
        assert get_result_filter() is None

    def test_configure_with_custom_rules(self):
        rules = [MaskingRule(pii_type=PIIType.EMAIL, replacement="***")]
        rf = configure_result_filter(default_rules=rules)
        assert rf._default_rules == rules

    def test_configure_with_backend_configs(self):
        configs = {
            "notion": BackendFilterConfig(
                backend_id="notion",
                excluded_fields={"internal_id"},
            )
        }
        rf = configure_result_filter(backend_configs=configs)
        assert "notion" in rf._backend_configs

    def test_configure_disabled(self):
        rf = configure_result_filter(enabled=False)
        assert rf.enabled is False
        result = rf.filter_response({"email": "a@b.com"}, backend_id="test")
        assert result.masks_applied == 0


# =============================================================================
# ReDoS Safety
# =============================================================================


class TestReDoSSafety:
    def test_pathological_email_input(self, rf: ResultFilter):
        """Ensure email regex doesn't hang on crafted input."""
        evil = "a" * 1000 + "@" + "b" * 1000 + ".com"
        result, pii = rf.mask_string(evil, rf._default_rules)
        assert isinstance(result, str)

    def test_very_long_string_skipped(self, rf: ResultFilter):
        """Strings beyond max scan length are returned as-is."""
        huge = "user@test.com " * 10000
        result, pii = rf.mask_string(huge, rf._default_rules)
        assert result == huge
        assert pii == []
