"""
Conversion helpers between integer paise (storage) and rupee display values.
See Plan_v3 Core Architectural Principles 7.
"""

from decimal import ROUND_HALF_UP, Decimal


def rupees_to_paise(rupees) -> int:
    """Converts a rupee amount (int, float or str) to integer paise, rounding half-up."""
    amount = Decimal(str(rupees)) * 100
    return int(amount.to_integral_value(rounding=ROUND_HALF_UP))


def paise_to_rupees(paise: int) -> Decimal:
    """Converts integer paise to a Decimal rupee amount with 2 decimal places."""
    if not isinstance(paise, int):
        raise TypeError("paise_to_rupees requires an int; money is stored as integer paise only")
    return (Decimal(paise) / 100).quantize(Decimal("0.01"))


def format_rupees(paise: int) -> str:
    """Formats integer paise as a '₹' rupee string, e.g. 94050 -> '₹940.50'."""
    return f"₹{paise_to_rupees(paise)}"
