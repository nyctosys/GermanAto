"""Input normalisers shared by every schema, so the same value is always
stored the same way (spec §3 R8)."""

import re
from typing import Annotated

from pydantic import AfterValidator, StringConstraints


def normalize_pk_phone(value: str) -> str:
    """Pakistani numbers to +92XXXXXXXXXX. Empty stays empty."""
    digits = re.sub(r"[^\d+]", "", value.strip())
    if not digits:
        return ""
    if digits.startswith("+92"):
        digits = digits[3:]
    elif digits.startswith("0092"):
        digits = digits[4:]
    elif digits.startswith("92") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = digits[1:]
    if not re.fullmatch(r"\d{9,10}", digits):
        raise ValueError("Enter a Pakistani phone number, e.g. 0300 1234567")
    return "+92" + digits


def _strip(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


Text = Annotated[str, AfterValidator(_strip)]
Name = Annotated[str, AfterValidator(_strip), StringConstraints(min_length=1, max_length=120)]
Phone = Annotated[str, AfterValidator(normalize_pk_phone)]
Username = Annotated[str, AfterValidator(lambda v: v.strip().lower()),
                     StringConstraints(pattern=r"^[a-z0-9._-]{3,32}$")]
Email = Annotated[str, AfterValidator(lambda v: v.strip().lower()),
                  StringConstraints(pattern=r"^(|[^@\s]+@[^@\s]+\.[^@\s]+)$", max_length=120)]  # "" = no email
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]


if __name__ == "__main__":
    for raw in ("0300 1234567", "+92 300 1234567", "923001234567", "0092-300-1234567", "042 35761234"):
        print(raw, "->", normalize_pk_phone(raw))
    assert normalize_pk_phone("0300-1234567") == "+923001234567"
    assert normalize_pk_phone("") == ""
    for bad in ("12345", "0300 12345678901"):
        try:
            normalize_pk_phone(bad)
            raise AssertionError(bad)
        except ValueError:
            pass
    print("ok")
