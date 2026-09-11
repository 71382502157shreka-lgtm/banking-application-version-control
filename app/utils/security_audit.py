"""
Security Audit & Validation Utilities for BankVCS 2.0.

Provides pure Python validators for password strength, input sanitization,
IP address range validation, and transaction security threshold audits.
"""

import re
import ipaddress
import logging
from typing import Dict, List, Any, Tuple, Optional

logger = logging.getLogger(__name__)


class PasswordPolicyValidator:
    """
    Validates user passwords against enterprise banking strength policies.
    """

    MIN_LENGTH = 8
    MAX_LENGTH = 128

    @classmethod
    def validate(cls, password: str) -> Tuple[bool, List[str]]:
        """
        Validates password against complexity requirements:
        - At least 8 characters long
        - At least one uppercase letter (A-Z)
        - At least one lowercase letter (a-z)
        - At least one digit (0-9)
        - At least one special character (!@#$%^&*()_+-=[]{})
        """
        errors = []
        if not password:
            return False, ["Password cannot be empty."]

        if len(password) < cls.MIN_LENGTH:
            errors.append(f"Password must be at least {cls.MIN_LENGTH} characters long.")
        if len(password) > cls.MAX_LENGTH:
            errors.append(f"Password must not exceed {cls.MAX_LENGTH} characters.")
        if not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one uppercase letter (A-Z).")
        if not re.search(r"[a-z]", password):
            errors.append("Password must contain at least one lowercase letter (a-z).")
        if not re.search(r"[0-9]", password):
            errors.append("Password must contain at least one numerical digit (0-9).")
        if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", password):
            errors.append("Password must contain at least one special character.")

        # Common forbidden passwords check
        forbidden_words = ["password", "123456", "admin", "bankvcs", "welcome", "qwerty"]
        for fw in forbidden_words:
            if fw in password.lower():
                errors.append(f"Password contains common unsafe word '{fw}'.")

        return len(errors) == 0, errors


class InputSecuritySanitizer:
    """
    Sanitizes user input strings for malicious script tags or SQL injection patterns.
    """

    DANGEROUS_PATTERNS = [
        r"<script.*?>.*?</script>",
        r"javascript:",
        r"onload\s*=",
        r"onerror\s*=",
        r"onclick\s*=",
        r"UNION\s+SELECT",
        r"DROP\s+TABLE",
        r"DELETE\s+FROM",
        r"--\s*$",
    ]

    @classmethod
    def contains_malicious_pattern(cls, text_input: str) -> Tuple[bool, Optional[str]]:
        """
        Checks string for common XSS and SQL injection payloads.
        Returns (is_suspicious, matching_pattern_description).
        """
        if not text_input or not isinstance(text_input, str):
            return False, None

        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, text_input, re.IGNORECASE):
                return True, pattern

        return False, None

    @classmethod
    def sanitize(cls, text_input: str) -> str:
        """Strips HTML tags and trailing whitespace."""
        if not text_input:
            return ""
        # Remove basic HTML tags
        clean = re.sub(r"<[^>]*>", "", text_input)
        return clean.strip()


class IPAddressAuditUtility:
    """
    Validates and checks IP addresses against private, public, and whitelist ranges.
    """

    INTERNAL_SUBNETS = [
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
        ipaddress.ip_network("127.0.0.0/8"),
    ]

    @classmethod
    def is_internal_ip(cls, ip_str: str) -> bool:
        """Determines if IP address belongs to internal private subnets or loopback."""
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            return any(ip_obj in subnet for subnet in cls.INTERNAL_SUBNETS)
        except ValueError:
            return False

    @classmethod
    def is_valid_ip(cls, ip_str: str) -> bool:
        """Verifies if input string is a valid IPv4 or IPv6 address."""
        try:
            ipaddress.ip_address(ip_str)
            return True
        except ValueError:
            return False


class TransactionSecurityAudit:
    """
    Evaluates transaction risk based on amount thresholds and transfer frequency.
    """

    HIGH_VALUE_THRESHOLD = 10000.0
    CRITICAL_VALUE_THRESHOLD = 50000.0

    @classmethod
    def evaluate_risk(cls, amount: float, user_role: str) -> Dict[str, Any]:
        """
        Calculates risk rating and required approval tier for a financial transaction.
        """
        if amount <= 0:
            return {"risk_level": "INVALID", "requires_approval": False, "requires_otp": False}

        if amount >= cls.CRITICAL_VALUE_THRESHOLD:
            return {
                "risk_level": "CRITICAL",
                "requires_approval": True,
                "approval_role": "ADMIN",
                "requires_otp": True,
                "reason": f"Transaction amount ${amount:,.2f} exceeds critical limit ${cls.CRITICAL_VALUE_THRESHOLD:,.2f}.",
            }
        elif amount >= cls.HIGH_VALUE_THRESHOLD:
            return {
                "risk_level": "HIGH",
                "requires_approval": True,
                "approval_role": "EMPLOYEE",
                "requires_otp": True,
                "reason": f"Transaction amount ${amount:,.2f} exceeds high value threshold ${cls.HIGH_VALUE_THRESHOLD:,.2f}.",
            }
        else:
            return {
                "risk_level": "LOW",
                "requires_approval": False,
                "requires_otp": False,
                "reason": "Standard transaction within normal limits.",
            }
