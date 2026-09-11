"""
Unit tests for Security Audit & Validation Utilities in BankVCS 2.0.
"""

import pytest
from app.utils.security_audit import (
    PasswordPolicyValidator,
    InputSecuritySanitizer,
    IPAddressAuditUtility,
    TransactionSecurityAudit,
)


def test_password_policy_validator():
    """Test password policy complexity requirements."""
    # Valid strong password
    valid, errors = PasswordPolicyValidator.validate("SecurePass123!")
    assert valid is True
    assert len(errors) == 0

    # Short password
    valid, errors = PasswordPolicyValidator.validate("Pass1!")
    assert valid is False
    assert any("at least 8" in err for err in errors)

    # Missing special character
    valid, errors = PasswordPolicyValidator.validate("Password123")
    assert valid is False
    assert any("special character" in err for err in errors)

    # Common word
    valid, errors = PasswordPolicyValidator.validate("Admin1234!")
    assert valid is False
    assert any("common unsafe word" in err for err in errors)


def test_input_security_sanitizer():
    """Test XSS detection and HTML tag sanitization."""
    suspicious, pattern = InputSecuritySanitizer.contains_malicious_pattern("<script>alert('xss')</script>")
    assert suspicious is True

    suspicious, pattern = InputSecuritySanitizer.contains_malicious_pattern("UNION SELECT * FROM users")
    assert suspicious is True

    suspicious, pattern = InputSecuritySanitizer.contains_malicious_pattern("Normal input string")
    assert suspicious is False

    cleaned = InputSecuritySanitizer.sanitize("<h1>Header</h1> Content ")
    assert cleaned == "Header Content"


def test_ip_address_audit_utility():
    """Test IP range checks for internal subnets and loopback."""
    assert IPAddressAuditUtility.is_valid_ip("192.168.1.1") is True
    assert IPAddressAuditUtility.is_valid_ip("invalid.ip") is False

    assert IPAddressAuditUtility.is_internal_ip("127.0.0.1") is True
    assert IPAddressAuditUtility.is_internal_ip("10.0.0.5") is True
    assert IPAddressAuditUtility.is_internal_ip("8.8.8.8") is False


def test_transaction_security_audit():
    """Test transaction risk threshold classification."""
    low = TransactionSecurityAudit.evaluate_risk(500.0, "CUSTOMER")
    assert low["risk_level"] == "LOW"
    assert low["requires_approval"] is False

    high = TransactionSecurityAudit.evaluate_risk(15000.0, "CUSTOMER")
    assert high["risk_level"] == "HIGH"
    assert high["requires_approval"] is True
    assert high["approval_role"] == "EMPLOYEE"

    critical = TransactionSecurityAudit.evaluate_risk(75000.0, "CUSTOMER")
    assert critical["risk_level"] == "CRITICAL"
    assert critical["requires_approval"] is True
    assert critical["approval_role"] == "ADMIN"
