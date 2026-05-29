"""
Tests for request sanitization in the DeepTrail Gateway.

Tests the current implementation of RequestSanitizer which provides
basic header sanitization for core PEP functionality.

Advanced content sanitization, parameter validation, and malicious
pattern detection are marked "For Future - Enterprise Grade" in the
implementation.
"""

import pytest
from unittest.mock import Mock
from fastapi import Request

from app.core.request_sanitizer import (
    RequestSanitizer,
    SanitizationConfig,
    SanitizationLevel,
    SanitizationResult,
    ContentType,
    JSONSanitizer,
    FormSanitizer,
    XMLSanitizer,
    sanitizer,
)


class TestSanitizationConfig:
    """Test sanitization configuration."""

    def test_default_config(self):
        config = SanitizationConfig()
        assert config.level == SanitizationLevel.MODERATE

    def test_custom_level(self):
        config = SanitizationConfig(level=SanitizationLevel.STRICT)
        assert config.level == SanitizationLevel.STRICT


class TestSanitizationLevel:
    """Test sanitization level enum."""

    def test_levels_exist(self):
        assert SanitizationLevel.STRICT == "strict"
        assert SanitizationLevel.MODERATE == "moderate"
        assert SanitizationLevel.LENIENT == "lenient"


class TestContentType:
    """Test content type enum."""

    def test_json_type(self):
        assert ContentType.JSON == "application/json"

    def test_form_type(self):
        assert ContentType.FORM_URLENCODED == "application/x-www-form-urlencoded"

    def test_xml_type(self):
        assert ContentType.XML == "application/xml"


class TestRequestSanitizer:
    """Test RequestSanitizer basic header sanitization."""

    def test_init_with_default_config(self):
        sanitizer = RequestSanitizer()
        assert sanitizer.config.level == SanitizationLevel.MODERATE

    def test_init_with_custom_config(self):
        config = SanitizationConfig(level=SanitizationLevel.STRICT)
        sanitizer = RequestSanitizer(config)
        assert sanitizer.config.level == SanitizationLevel.STRICT

    def test_sanitize_request_returns_result(self):
        request = Mock(spec=Request)
        request.headers = {"content-type": "application/json", "authorization": "Bearer token123"}

        sanitizer = RequestSanitizer()
        result = sanitizer.sanitize_request(request)

        assert isinstance(result, SanitizationResult)
        assert result.is_safe is True
        assert isinstance(result.sanitized_headers, dict)

    def test_strips_dangerous_headers(self):
        request = Mock(spec=Request)
        request.headers = {
            "host": "evil.example.com",
            "x-forwarded-for": "1.2.3.4",
            "x-real-ip": "5.6.7.8",
            "content-type": "application/json",
            "authorization": "Bearer token",
        }

        sanitizer = RequestSanitizer()
        result = sanitizer.sanitize_request(request)

        assert "host" not in result.sanitized_headers
        assert "x-forwarded-for" not in result.sanitized_headers
        assert "x-real-ip" not in result.sanitized_headers
        assert "content-type" in result.sanitized_headers
        assert "authorization" in result.sanitized_headers

    def test_rejects_oversized_header_values(self):
        request = Mock(spec=Request)
        request.headers = {
            "x-custom": "x" * 9000,
            "content-type": "application/json",
        }

        sanitizer = RequestSanitizer()
        result = sanitizer.sanitize_request(request)

        assert "x-custom" not in result.sanitized_headers
        assert "content-type" in result.sanitized_headers

    def test_preserves_normal_headers(self):
        request = Mock(spec=Request)
        request.headers = {
            "content-type": "application/json",
            "accept": "application/json",
            "user-agent": "test-agent/1.0",
        }

        sanitizer = RequestSanitizer()
        result = sanitizer.sanitize_request(request)

        assert result.sanitized_headers["content-type"] == "application/json"
        assert result.sanitized_headers["accept"] == "application/json"
        assert result.sanitized_headers["user-agent"] == "test-agent/1.0"


class TestSanitizationResult:
    """Test SanitizationResult dataclass."""

    def test_to_dict(self):
        result = SanitizationResult(
            sanitized_headers={"content-type": "application/json"},
            sanitized_params={},
            sanitized_body=None,
            warnings=["test warning"],
            violations=[],
            is_safe=True,
        )

        d = result.to_dict()
        assert d["is_safe"] is True
        assert d["warnings"] == ["test warning"]
        assert d["violations"] == []
        assert d["sanitized_headers"]["content-type"] == "application/json"


class TestModuleLevelSanitizer:
    """Test module-level sanitizer instance."""

    def test_module_sanitizer_exists(self):
        assert sanitizer is not None
        assert isinstance(sanitizer, RequestSanitizer)

    def test_module_sanitizer_uses_default_config(self):
        assert sanitizer.config.level == SanitizationLevel.MODERATE


class TestFutureEnterprisePlaceholders:
    """Verify placeholder classes exist for future enterprise features."""

    def test_json_sanitizer_exists(self):
        assert JSONSanitizer is not None

    def test_form_sanitizer_exists(self):
        assert FormSanitizer is not None

    def test_xml_sanitizer_exists(self):
        assert XMLSanitizer is not None
