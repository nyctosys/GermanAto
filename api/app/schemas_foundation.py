"""Pydantic models for foundation field validation (shared with routers)."""

from __future__ import annotations

from pydantic import Field, field_validator

from app.foundation.validation import normalize_cnic, normalize_pk_phone, normalize_reg_no
from app.schemas import APIModel


class PhoneIn(APIModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalize_pk_phone(v, required=True)  # type: ignore[return-value]


class RegNoIn(APIModel):
    reg_no: str

    @field_validator("reg_no")
    @classmethod
    def _reg(cls, v: str) -> str:
        return normalize_reg_no(v, required=True)  # type: ignore[return-value]


class CnicIn(APIModel):
    cnic: str

    @field_validator("cnic")
    @classmethod
    def _cnic(cls, v: str) -> str:
        return normalize_cnic(v, required=True)  # type: ignore[return-value]


class MoneyAmountIn(APIModel):
    amount: float = Field(ge=0)


class QuantityIn(APIModel):
    quantity: int = Field(ge=0)
