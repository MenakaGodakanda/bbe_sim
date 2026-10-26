"""Exact integer money arithmetic. 1 unit = 1 micro-USD (10^-6 USD)."""
from decimal import Decimal, ROUND_HALF_EVEN

MICRO = 10 ** 6


def to_u(x) -> int:
    """Convert a decimal amount (str/float/int) to integer micro-USD."""
    return int((Decimal(str(x)) * MICRO).to_integral_value(ROUND_HALF_EVEN))


def ceil_div(a: int, b: int) -> int:
    return -(-a // b)
