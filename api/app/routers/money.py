"""Accounts, expense categories and (later stories) the Money In and Money Out pages."""

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import Actor, current_actor, require
from app.db import get_db
from app.models import Account, ExpenseCategory
from app.money_setup import ensure_money_setup
from app.validators import Name, Text

router = APIRouter(prefix="/api", tags=["money"])
can_settings = require("settings")


def can_read_money(actor: Actor = Depends(current_actor)) -> Actor:
    if not any(actor.can(p) for p in ("settings", "payments-in", "payments-out", "expenses", "dashboard")):
        raise HTTPException(403, "You don't have permission to do this")
    return actor


def account_out(a: Account) -> dict:
    return {k: getattr(a, k) for k in ("id", "kind", "name", "opening_balance", "opening_date", "is_active", "version")}


@router.get("/accounts")
def list_accounts(actor: Actor = Depends(can_read_money), db: Session = Depends(get_db)):
    ensure_money_setup(db, actor.branch)
    db.commit()
    return [account_out(a) for a in db.scalars(select(Account).where(Account.branch_id == actor.branch.id).order_by(Account.kind))]


class AccountUpdate(BaseModel):
    name: Name
    opening_balance: Decimal = Field(ge=0, le=10_000_000_000, decimal_places=2)
    opening_date: date
    is_active: bool = True
    version: int


@router.put("/accounts/{account_id}")
def update_account(account_id: uuid.UUID, body: AccountUpdate, actor: Actor = Depends(can_settings), db: Session = Depends(get_db)):
    a = db.get(Account, account_id)
    if not a or a.branch_id != actor.branch.id:
        raise HTTPException(404, "Account not found")
    if body.version != a.version:
        raise HTTPException(409, "Someone else changed this account. Reload and try again.")
    if body.opening_date > date.today():
        raise HTTPException(422, "The opening date is in the future")
    for k, v in body.model_dump(exclude={"version"}).items():
        setattr(a, k, v)
    db.commit()
    return account_out(a)


# --- expense categories --------------------------------------------------------------------------------

def category_out(c: ExpenseCategory) -> dict:
    return {k: getattr(c, k) for k in ("id", "name", "is_active", "version")}


@router.get("/expense-categories")
def list_categories(include_inactive: bool = False, actor: Actor = Depends(can_read_money), db: Session = Depends(get_db)):
    ensure_money_setup(db, actor.branch)
    db.commit()
    stmt = select(ExpenseCategory).where(ExpenseCategory.branch_id == actor.branch.id).order_by(ExpenseCategory.name)
    if not include_inactive:
        stmt = stmt.where(ExpenseCategory.is_active)
    return [category_out(c) for c in db.scalars(stmt)]


class CategoryIn(BaseModel):
    name: Name = Field(max_length=80)


class CategoryUpdate(CategoryIn):
    is_active: bool = True
    version: int


def _name_taken(db: Session, actor: Actor, name: str, except_id: uuid.UUID | None = None) -> bool:
    stmt = select(ExpenseCategory.id).where(ExpenseCategory.branch_id == actor.branch.id, func.lower(ExpenseCategory.name) == name.lower())
    if except_id:
        stmt = stmt.where(ExpenseCategory.id != except_id)
    return db.scalar(stmt) is not None


@router.post("/expense-categories", status_code=201)
def create_category(body: CategoryIn, actor: Actor = Depends(can_settings), db: Session = Depends(get_db)):
    ensure_money_setup(db, actor.branch)
    if _name_taken(db, actor, body.name):
        raise HTTPException(409, "This category already exists")
    c = ExpenseCategory(name=body.name)
    db.add(c)
    db.commit()
    return category_out(c)


@router.put("/expense-categories/{category_id}")
def update_category(category_id: uuid.UUID, body: CategoryUpdate, actor: Actor = Depends(can_settings), db: Session = Depends(get_db)):
    c = db.get(ExpenseCategory, category_id)
    if not c or c.branch_id != actor.branch.id:
        raise HTTPException(404, "Category not found")
    if body.version != c.version:
        raise HTTPException(409, "Someone else changed this category. Reload and try again.")
    if _name_taken(db, actor, body.name, c.id):
        raise HTTPException(409, "This category already exists")
    c.name, c.is_active = body.name, body.is_active
    db.commit()
    return category_out(c)
