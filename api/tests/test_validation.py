import pytest

from app.foundation.validation import (
    normalize_cnic,
    normalize_pk_phone,
    normalize_reg_no,
    require_non_negative,
    require_positive_int,
)


def test_normalize_pk_phone_local():
    assert normalize_pk_phone("03001234567") == "+923001234567"


def test_normalize_pk_phone_e164():
    assert normalize_pk_phone("+92 300 1234567") == "+923001234567"


def test_normalize_pk_phone_rejects_landline():
    with pytest.raises(ValueError):
        normalize_pk_phone("0421234567")


def test_normalize_reg_no():
    assert normalize_reg_no("abc-123") == "ABC-123"


def test_normalize_cnic():
    assert normalize_cnic("3520212345671") == "35202-1234567-1"
    assert normalize_cnic("35202-1234567-1") == "35202-1234567-1"


def test_non_negative():
    assert require_non_negative("amount", 0) == 0.0
    with pytest.raises(ValueError):
        require_non_negative("amount", -1)


def test_quantity():
    assert require_positive_int("quantity", 3) == 3
    with pytest.raises(ValueError):
        require_positive_int("quantity", -2)
