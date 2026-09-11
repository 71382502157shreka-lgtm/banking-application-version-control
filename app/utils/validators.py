import re
from decimal import Decimal, InvalidOperation

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.]{3,32}$")
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
ACCOUNT_NUM_RE = re.compile(r"^\d{9,18}$")


class ValidationError(Exception):
    def __init__(self, message: str, field: str = None):
        super().__init__(message)
        self.message = message
        self.field = field


def require_fields(data: dict, fields: list):
    missing = [f for f in fields if data.get(f) in (None, "")]
    if missing:
        raise ValidationError(f"Missing required field(s): {', '.join(missing)}")


def validate_email(email: str):
    if not email or not EMAIL_RE.match(email):
        raise ValidationError("Invalid email address", field="email")


def validate_username(username: str):
    if not username or not USERNAME_RE.match(username):
        raise ValidationError(
            "Username must be 3-32 characters: letters, numbers, underscore, or dot",
            field="username",
        )


def validate_password_strength(password: str):
    if not password or len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long", field="password")
    if not re.search(r"[A-Z]", password):
        raise ValidationError("Password must contain an uppercase letter", field="password")
    if not re.search(r"[a-z]", password):
        raise ValidationError("Password must contain a lowercase letter", field="password")
    if not re.search(r"\d", password):
        raise ValidationError("Password must contain a digit", field="password")


def validate_amount(raw_amount) -> Decimal:
    try:
        amount = Decimal(str(raw_amount))
    except (InvalidOperation, TypeError):
        raise ValidationError("Amount must be a valid number", field="amount")
    if amount <= 0:
        raise ValidationError("Amount must be greater than zero", field="amount")
    if amount.as_tuple().exponent < -2:
        raise ValidationError("Amount cannot have more than 2 decimal places", field="amount")
    return amount


def validate_ifsc(ifsc: str):
    if not ifsc or not IFSC_RE.match(ifsc.upper()):
        raise ValidationError("Invalid IFSC code format", field="ifsc")


def validate_account_number(account_number: str):
    if not account_number or not ACCOUNT_NUM_RE.match(str(account_number).strip()):
        raise ValidationError("Account number must be 9-18 digits", field="account_number")

