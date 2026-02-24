"""
Tests for PII Redaction Module.
"""
import pytest
from src.security.pii_redactor import (
    redact_pii,
    redact_partial_card,
    sanitize_for_logging,
    detect_pii_types,
)


class TestRedactPII:
    """Tests for the redact_pii function."""

    def test_redact_ssn_dashed(self):
        text = "My SSN is 123-45-6789."
        redacted, detected = redact_pii(text)
        assert "123-45-6789" not in redacted
        assert "[SSN_REDACTED]" in redacted
        assert "SSN" in detected

    def test_redact_credit_card_with_spaces(self):
        text = "Card number is 4532 1234 5678 9010."
        redacted, detected = redact_pii(text)
        assert "4532 1234 5678 9010" not in redacted
        assert "[CREDIT_CARD_REDACTED]" in redacted
        assert "CREDIT_CARD" in detected

    def test_redact_credit_card_with_dashes(self):
        text = "Card: 4532-1234-5678-9010"
        redacted, detected = redact_pii(text)
        assert "4532-1234-5678-9010" not in redacted
        assert "CREDIT_CARD" in detected

    def test_redact_pin(self):
        text = "My PIN: 4321 is set."
        redacted, detected = redact_pii(text)
        assert "PIN: 4321" not in redacted
        assert "[PIN_REDACTED]" in redacted
        assert "PIN" in detected

    def test_redact_password(self):
        text = "password: MyS3cr3t!"
        redacted, detected = redact_pii(text)
        assert "MyS3cr3t!" not in redacted
        assert "PASSWORD" in detected

    def test_no_pii_detected(self):
        text = "I want to check my balance."
        redacted, detected = redact_pii(text)
        assert redacted == text
        assert detected == []

    def test_strict_mode_redacts_email(self):
        text = "Email me at john@example.com."
        redacted_normal, detected_normal = redact_pii(text, strict_mode=False)
        redacted_strict, detected_strict = redact_pii(text, strict_mode=True)
        # Normal mode should NOT redact email (not critical)
        assert "john@example.com" in redacted_normal
        # Strict mode should redact email
        assert "john@example.com" not in redacted_strict
        assert "EMAIL" in detected_strict

    def test_strict_mode_redacts_phone(self):
        text = "Call me at 555-123-4567."
        _, detected_normal = redact_pii(text, strict_mode=False)
        _, detected_strict = redact_pii(text, strict_mode=True)
        assert "PHONE" not in detected_normal
        assert "PHONE" in detected_strict

    def test_multiple_pii_types(self):
        text = "SSN: 123-45-6789, Card: 4532 1234 5678 9010, PIN: 1234"
        redacted, detected = redact_pii(text)
        assert "SSN" in detected
        assert "CREDIT_CARD" in detected
        assert "PIN" in detected
        assert len(detected) >= 3


class TestRedactPartialCard:
    """Tests for partial card redaction (keeps last 4 digits)."""

    def test_keeps_last_4(self):
        text = "Card: 4532 1234 5678 9010"
        result = redact_partial_card(text)
        assert "XXXX XXXX XXXX 9010" in result
        assert "4532" not in result

    def test_multiple_cards(self):
        text = "Cards: 1111 2222 3333 4444 and 5555 6666 7777 8888"
        result = redact_partial_card(text)
        assert "4444" in result
        assert "8888" in result
        assert "1111" not in result


class TestSanitizeForLogging:
    """Tests for sanitize_for_logging."""

    def test_removes_ssn(self):
        text = "Customer SSN 123-45-6789 requested balance."
        result = sanitize_for_logging(text)
        assert "123-45-6789" not in result

    def test_safe_text_unchanged(self):
        text = "User asked about branch hours."
        result = sanitize_for_logging(text)
        assert result == text


class TestDetectPIITypes:
    """Tests for detect_pii_types."""

    def test_detects_multiple_types(self):
        text = "SSN 123-45-6789, email test@mail.com, PIN: 1234"
        types = detect_pii_types(text)
        assert "SSN" in types
        assert "EMAIL" in types
        assert "PIN" in types

    def test_no_pii(self):
        text = "Hello, I need help."
        types = detect_pii_types(text)
        assert types == []
