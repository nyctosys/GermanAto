"""Unit tests for foundation helpers (no live DB required)."""

from decimal import Decimal

import pytest

from app.foundation.branch import DEFAULT_BRANCH_ID, new_branch_id
from app.foundation.money import format_pkr, from_paisa, to_paisa, validate_paisa
from app.foundation.roles import VALID_ROLES, expand_allowed_roles


def test_to_paisa_rounds_half_up():
    assert to_paisa(1) == 100
    assert to_paisa("10.50") == 1050
    assert to_paisa(Decimal("0.01")) == 1
    assert to_paisa(1.005) == 101


def test_from_paisa():
    assert from_paisa(100) == Decimal("1.00")
    assert from_paisa(1050) == Decimal("10.50")


def test_validate_paisa_rejects_negative():
    with pytest.raises(ValueError):
        validate_paisa(-1)


def test_format_pkr():
    assert "1,050.00" in format_pkr(105000) or "1050.00" in format_pkr(105000)


def test_branch_id_shape():
    assert len(DEFAULT_BRANCH_ID) == 8
    assert all(c in "0123456789abcdef" for c in DEFAULT_BRANCH_ID)
    bid = new_branch_id()
    assert len(bid) == 8


def test_expand_roles_owner_covers_admin_routes():
    allowed = expand_allowed_roles(["admin", "accountant"])
    assert "owner" in allowed
    assert "manager" in allowed
    assert "admin" in allowed


def test_valid_roles_include_workshop_map():
    for role in (
        "owner",
        "manager",
        "accountant",
        "service_advisor",
        "technician",
        "store_keeper",
    ):
        assert role in VALID_ROLES
