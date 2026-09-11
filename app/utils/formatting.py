"""
Server-side Python formatting utilities for financial figures, dates, and account masking.
"""

from decimal import Decimal
from datetime import datetime


def format_currency(amount: Decimal | float | int | str, currency_symbol: str = "Rs. ") -> str:
    """Format numeric amount into standardized Indian currency string."""
    try:
        val = Decimal(str(amount))
        return f"{currency_symbol}{val:,.2f}"
    except Exception:
        return f"{currency_symbol}0.00"


def format_datetime(dt: datetime | str | None, fmt: str = "%d %b %Y, %H:%M") -> str:
    """Format datetime object or ISO string into readable string."""
    if not dt:
        return "N/A"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return dt
    return dt.strftime(fmt)


def mask_account_number(account_number: str) -> str:
    """Mask account number showing only last 4 digits."""
    if not account_number or len(account_number) < 4:
        return "XXXX"
    return "X" * (len(account_number) - 4) + account_number[-4:]
