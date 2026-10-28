"""Human document numbers: <PREFIX>-<branch code>-<000001>, one series per
branch and kind, gap-free under concurrency (the upsert takes a row lock)."""

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Branch, NumberSequence

PREFIXES = {"customer": "CUS", "item": "ITM", "visit": "VIS", "inspection": "INS", "job_card": "JC",
            "quotation": "QT", "repair_order": "RO", "invoice": "INV", "counter_sale": "CS", "payment": "PAY",
            "credit_note": "CN", "vendor": "VEN", "purchase_order": "PO", "goods_receipt": "GRN",
            "vendor_bill": "BILL", "vendor_payment": "VPAY", "journal": "JE",
            "other_income": "INC", "owner_capital": "CAP", "transfer": "TRF", "expense": "EXP", "drawings": "DRW", "refund": "RFD", "cash_close": "CC", "employee": "EMP", "payroll_run": "PR", "salary_advance": "ADV", "salary": "SAL"}


def next_number(db: Session, branch: Branch, kind: str) -> str:
    stmt = (
        insert(NumberSequence)
        .values(branch_id=branch.id, kind=kind, last_value=1)
        .on_conflict_do_update(index_elements=["branch_id", "kind"],
                               set_={"last_value": NumberSequence.last_value + 1})
        .returning(NumberSequence.last_value)
    )
    n = db.execute(stmt).scalar_one()
    return f"{PREFIXES[kind]}-{branch.code}-{n:06d}"
