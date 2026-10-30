"""The accounts and expense categories every branch starts with. Created the
first time they are needed, so existing branches pick them up without a data migration."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, Branch, ExpenseCategory
from app.config import local_today

DEFAULT_ACCOUNTS = (("cash", "Cash in hand"), ("bank", "Bank account"), ("wallet", "Mobile wallet"))
DEFAULT_CATEGORIES = (
    "Tea and refreshments", "Fuel and transport", "Electricity, gas and water", "Rent", "Repairs and maintenance",
    "Equipment and tools", "Cleaning and supplies", "Stationery and printing", "Internet and phone", "Marketing",
    "Bank charges", "Taxes and fees", "Other",
)


def ensure_money_setup(db: Session, branch: Branch) -> None:
    have = set(db.scalars(select(Account.kind).where(Account.branch_id == branch.id)))
    for kind, name in DEFAULT_ACCOUNTS:
        if kind not in have:
            db.add(Account(kind=kind, name=name, opening_date=local_today(), branch_id=branch.id))
    if not db.scalar(select(func.count()).select_from(ExpenseCategory).where(ExpenseCategory.branch_id == branch.id)):
        db.add_all(ExpenseCategory(name=n, branch_id=branch.id) for n in DEFAULT_CATEGORIES)
    db.flush()
