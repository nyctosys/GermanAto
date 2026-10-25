"""Normalized field validators (PK phone E.164, reg no, CNIC, non-negative money/qty)."""

from __future__ import annotations

import re
from typing import Any

# Pakistan mobile: +92XXXXXXXXXX (12 digits after +) or local 03XXXXXXXXX
_PHONE_DIGITS = re.compile(r"\D+")
_CNIC = re.compile(r"^\d{5}-\d{7}-\d{1}$|^\d{13}$")
_REG_NO = re.compile(r"^[A-Za-z0-9\-\s]{2,20}$")


def normalize_pk_phone(value: str | None, *, required: bool = False) -> str | None:
    if value is None or str(value).strip() in ("", "N/A"):
        if required:
            raise ValueError("phone is required")
        return None
    raw = str(value).strip()
    digits = _PHONE_DIGITS.sub("", raw)
    if digits.startswith("0092"):
        digits = digits[4:]
    elif digits.startswith("92") and len(digits) >= 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) != 10 or not digits.startswith("3"):
        raise ValueError("phone must be a valid Pakistan mobile (e.g. 03XX XXXXXXX or +923XXXXXXXXX)")
    return f"+92{digits}"


def normalize_reg_no(value: str | None, *, required: bool = False) -> str | None:
    if value is None or str(value).strip() in ("", "N/A"):
        if required:
            raise ValueError("registration number is required")
        return None
    cleaned = re.sub(r"\s+", " ", str(value).strip().upper())
    if not _REG_NO.match(cleaned):
        raise ValueError("registration number format is invalid")
    return cleaned


def normalize_cnic(value: str | None, *, required: bool = False) -> str | None:
    if value is None or str(value).strip() in ("", "N/A"):
        if required:
            raise ValueError("CNIC is required")
        return None
    raw = str(value).strip()
    digits = _PHONE_DIGITS.sub("", raw)
    if len(digits) != 13:
        raise ValueError("CNIC must be 13 digits (XXXXX-XXXXXXX-X)")
    return f"{digits[:5]}-{digits[5:12]}-{digits[12]}"


def require_non_negative(name: str, value: Any) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc
    if num < 0:
        raise ValueError(f"{name} must not be negative")
    return num


def require_positive_int(name: str, value: Any) -> int:
    try:
        num = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if num < 0:
        raise ValueError(f"{name} must not be negative")
    return num


def validate_money_fields(data: dict, fields: tuple[str, ...] = ("amount", "price", "rate")) -> list[str]:
    errors: list[str] = []
    for field in fields:
        if field not in data or data[field] in (None, ""):
            continue
        try:
            require_non_negative(field, data[field])
        except ValueError as exc:
            errors.append(str(exc))
    if "quantity" in data and data["quantity"] not in (None, ""):
        try:
            require_positive_int("quantity", data["quantity"])
        except ValueError as exc:
            errors.append(str(exc))
    return errors
