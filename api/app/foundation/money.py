"""Money helpers: store as integer paisa (1 PKR = 100 paisa). Never use floats for new money fields."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Union

Number = Union[int, float, str, Decimal]

PAISA_PER_PKR = 100


def to_paisa(amount_pkr: Number) -> int:
    """Convert PKR (rupees) to integer paisa. Rejects non-finite input via Decimal."""
    value = Decimal(str(amount_pkr)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(value * PAISA_PER_PKR)


def from_paisa(paisa: int) -> Decimal:
    """Convert integer paisa to Decimal PKR with 2 places."""
    if not isinstance(paisa, int):
        raise TypeError("paisa must be int")
    return (Decimal(paisa) / PAISA_PER_PKR).quantize(Decimal("0.01"))


def validate_paisa(paisa: int, *, allow_zero: bool = True, allow_negative: bool = False) -> int:
    if not isinstance(paisa, int):
        raise TypeError("paisa must be int")
    if not allow_negative and paisa < 0:
        raise ValueError("amount must not be negative")
    if not allow_zero and paisa == 0:
        raise ValueError("amount must be greater than zero")
    return paisa


def format_pkr(paisa: int) -> str:
    return f"{from_paisa(paisa):,.2f} PKR"
