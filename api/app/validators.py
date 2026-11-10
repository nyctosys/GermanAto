"""Input normalisers shared by every schema, so the same value is always
stored the same way (spec §3 R8)."""

import re
from typing import Annotated

from pydantic import AfterValidator, StringConstraints


def normalize_pk_phone(value: str) -> str:
    """Phone numbers in international format. Pakistani numbers (0300..., 92300..., +92300...) become +92XXXXXXXXXX;
    a number with another country code (+971..., 00971...) is kept as +<code><number>. Empty stays empty."""
    if re.search(r"[^\d\s+\-()./]", value):
        raise ValueError("A phone number has digits only, e.g. +92 300 1234567")
    digits = re.sub(r"[^\d+]", "", value.strip())
    if not digits:
        return ""
    if digits.startswith("00") and not digits.startswith("0092"):
        digits = "+" + digits[2:]
    if digits.startswith("+") and not digits.startswith("+92"):
        if not re.fullmatch(r"\+[1-9]\d{7,14}", digits):
            raise ValueError("That number is too short or too long for its country code, e.g. +971 50 123 4567")
        return digits
    if digits.startswith("+92"):
        digits = digits[3:]
    elif digits.startswith("0092"):
        digits = digits[4:]
    elif digits.startswith("92") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = digits[1:]
    if not re.fullmatch(r"\d{9,10}", digits):
        raise ValueError(f"A Pakistani number has 10 digits after +92 (you typed {len(digits)}), e.g. +92 300 1234567")
    return "+92" + digits


def normalize_plate(value: str) -> str:
    """'lea 21-1234' -> 'LEA211234'. The plate as written is kept separately."""
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def normalize_code(value: str) -> str:
    """Barcodes and part numbers match without spaces, dashes or dots."""
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def normalize_vin(value: str) -> str:
    """One identity number: a 17-character VIN or a local chassis number
    (Japanese imports carry ones like NZE141-6012345)."""
    vin = re.sub(r"\s", "", value.upper())
    if vin and not re.fullmatch(r"[A-Z0-9-]{5,30}", vin):
        raise ValueError("Use the VIN or chassis number: 5 to 30 letters, digits or dashes")
    if len(vin) == 17 and "-" not in vin and re.search(r"[IOQ]", vin):
        raise ValueError("A 17-character VIN never contains I, O or Q")
    return vin


def normalize_cnic(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if not digits:
        return ""
    if len(digits) != 13:
        raise ValueError("A CNIC has 13 digits, e.g. 35202-1234567-1")
    return f"{digits[:5]}-{digits[5:12]}-{digits[12]}"


def normalize_ntn(value: str) -> str:
    """Company National Tax Number: 7 digits, optionally with a check digit (1234567-8). Empty stays empty."""
    digits = re.sub(r"\D", "", value)
    if not digits:
        return ""
    if len(digits) == 7:
        return digits
    if len(digits) == 8:
        return f"{digits[:7]}-{digits[7]}"
    raise ValueError("A company NTN has 7 digits, e.g. 1234567-8")


def normalize_ntn_options(value: str) -> str:
    """Up to three workshop NTNs, one per line (commas also accepted)."""
    out: list[str] = []
    for part in re.split(r"[\n,;]+", value or ""):
        part = part.strip()
        if not part:
            continue
        n = normalize_ntn(part)
        if n and n not in out:
            out.append(n)
        if len(out) >= 3:
            break
    return "\n".join(out)


def _strip(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


Text = Annotated[str, AfterValidator(_strip)]
def _person(v: str) -> str:
    v = re.sub(r"\s+", " ", v).strip()
    if re.search(r"\d", v):
        raise ValueError("A person's name has no numbers. Put a phone number in the Phone box.")
    return v


PersonOrEmpty = Annotated[str, AfterValidator(_person), StringConstraints(max_length=120)]
Name = Annotated[str, AfterValidator(_strip), StringConstraints(min_length=1, max_length=120)]
Phone = Annotated[str, AfterValidator(normalize_pk_phone)]
Username = Annotated[str, AfterValidator(lambda v: v.strip().lower()),
                     StringConstraints(pattern=r"^[a-z0-9._-]{3,32}$")]
Email = Annotated[str, AfterValidator(lambda v: v.strip().lower()),
                  StringConstraints(pattern=r"^(|[^@\s]+@[^@\s]+\.[^@\s]+)$", max_length=120)]  # "" = no email
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]
Vin = Annotated[str, AfterValidator(normalize_vin)]
Cnic = Annotated[str, AfterValidator(normalize_cnic)]
Ntn = Annotated[str, AfterValidator(normalize_ntn)]
NtnOptions = Annotated[str, AfterValidator(normalize_ntn_options)]
Upper = Annotated[str, AfterValidator(lambda v: re.sub(r"\s+", " ", v).strip().upper())]


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
    assert normalize_plate("lea 21-1234") == "LEA211234"
    assert normalize_code(" 11-42 7.583 ") == "11427583"
    assert normalize_vin("wba 3a5c5 xdf123456") == "WBA3A5C5XDF123456"
    assert normalize_cnic("3520212345671") == "35202-1234567-1"
    for bad, fn in (("WBAO3A5C5XDF12345", normalize_vin), ("123", normalize_cnic)):
        try:
            fn(bad)
            raise AssertionError(bad)
        except ValueError:
            pass
    print("ok")
