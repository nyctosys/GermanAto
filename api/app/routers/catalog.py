"""Labour codes and inventory items (spec R4, R6)."""

import uuid
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import Actor, require
from app.db import get_db
from app.models import Item, ItemCode, LabourCode, StockMovement, User
from app.numbering import next_number
from app.stock import StockError, move, on_hand, on_hand_map
from app.validators import Name, Text, normalize_code

router = APIRouter(prefix="/api", tags=["catalog"])
can_stock = require("inventory")

Money = Field(ge=0, max_digits=14, decimal_places=2)
Qty = Field(max_digits=12, decimal_places=3)


# --- labour codes ----------------------------------------------------------

class LabourCodeIn(BaseModel):
    code: str = Field(default="", pattern=r"^([A-Za-z0-9][A-Za-z0-9-]{1,23})?$")  # blank: the system picks LAB-0001, LAB-0002, ...
    name: Name
    category: Name
    description: Text = Field(default="", max_length=1000)
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def upper(cls, v: str) -> str:
        return v.upper()


def labour_out(l: LabourCode) -> dict:
    return {k: getattr(l, k) for k in ("id", "code", "name", "category", "description", "is_active", "version")}


@router.get("/labour-codes")
def list_labour_codes(q: str = "", include_inactive: bool = False, actor: Actor = Depends(require("dashboard")),
                      db: Session = Depends(get_db)):
    stmt = select(LabourCode).where(LabourCode.branch_id == actor.branch.id).order_by(LabourCode.category, LabourCode.code)
    if not include_inactive:
        stmt = stmt.where(LabourCode.is_active)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(LabourCode.code.ilike(like), LabourCode.name.ilike(like), LabourCode.category.ilike(like)))
    return [labour_out(l) for l in db.scalars(stmt)]


@router.post("/labour-codes", status_code=201)
def create_labour_code(body: LabourCodeIn, actor: Actor = Depends(require("labour-codes")), db: Session = Depends(get_db)):
    if not body.code:
        n = db.scalar(select(func.count()).select_from(LabourCode).where(LabourCode.branch_id == actor.branch.id)) + 1
        while db.scalar(select(LabourCode.id).where(LabourCode.branch_id == actor.branch.id, LabourCode.code == f"LAB-{n:04d}")):
            n += 1
        body.code = f"LAB-{n:04d}"
    if db.scalar(select(LabourCode.id).where(LabourCode.branch_id == actor.branch.id, LabourCode.code == body.code)):
        raise HTTPException(409, f"The code {body.code} is already used")
    code = LabourCode(**body.model_dump())
    db.add(code)
    db.commit()
    return labour_out(code)


@router.put("/labour-codes/{code_id}")
def update_labour_code(code_id: uuid.UUID, body: LabourCodeIn, actor: Actor = Depends(require("labour-codes")),
                       db: Session = Depends(get_db)):
    code = db.get(LabourCode, code_id)
    if not code or code.branch_id != actor.branch.id:
        raise HTTPException(404, "Labour code not found")
    if body.code and body.code != code.code:
        raise HTTPException(422, "A code can't be renamed once created (old documents use it). Add a new code instead.")
    for key, value in body.model_dump(exclude={"code"}).items():
        setattr(code, key, value)
    db.commit()
    return labour_out(code)


# --- items -----------------------------------------------------------------

class CodeIn(BaseModel):
    kind: Literal["barcode", "mpn"]
    code: str = Field(min_length=3, max_length=60)

    @field_validator("code")
    @classmethod
    def usable(cls, v: str) -> str:
        v = " ".join(v.split()).upper()
        if not 3 <= len(normalize_code(v)) <= 40:
            raise ValueError("A code needs 3 to 40 letters or digits")
        return v


class ItemIn(BaseModel):
    name: Name = Field(max_length=160)
    brand: Text = Field(default="", max_length=60)
    category: Text = Field(default="", max_length=60)
    unit: Literal["pcs", "set", "litre", "kg", "metre", "pair", "box"] = "pcs"
    fitment: Text = Field(default="", max_length=200)
    location: Text = Field(default="", max_length=60)
    sale_price: Decimal = Money
    reorder_level: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=3)
    reorder_qty: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=3)
    is_active: bool = True
    codes: list[CodeIn] = Field(min_length=1, max_length=10)


class ItemCreate(ItemIn):
    opening_qty: Decimal = Field(default=Decimal("0"), ge=0, max_digits=12, decimal_places=3)
    opening_cost: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=4)


class ItemUpdate(ItemIn):
    version: int


class AdjustIn(BaseModel):
    qty: Decimal = Field(max_digits=12, decimal_places=3)  # + found / opening, - damaged / lost
    reason: Text = Field(min_length=3, max_length=300)
    unit_cost: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=4)


def item_out(item: Item, qty: Decimal) -> dict:
    data = {k: getattr(item, k) for k in ("id", "number", "name", "brand", "category", "unit", "fitment", "location",
                                          "sale_price", "avg_cost", "reorder_level", "reorder_qty", "is_active", "version")}
    data["codes"] = [{"id": c.id, "kind": c.kind, "code": c.code} for c in item.codes]
    data["on_hand"] = qty
    data["low_stock"] = item.reorder_level > 0 and qty <= item.reorder_level
    data["margin_pct"] = (float((item.sale_price - item.avg_cost) / item.sale_price * 100)
                          if item.sale_price > 0 and item.avg_cost > 0 else None)
    return data


def _set_codes(db: Session, actor: Actor, item: Item, codes: list[CodeIn]) -> None:
    norms = [normalize_code(c.code) for c in codes]
    if len(set(norms)) != len(norms):
        raise HTTPException(422, "The same code is listed twice")
    clash = db.execute(select(ItemCode.code, Item.name).join(Item, Item.id == ItemCode.item_id)
                       .where(ItemCode.branch_id == actor.branch.id, ItemCode.code_norm.in_(norms),
                              ItemCode.item_id != item.id)).first()
    if clash:
        raise HTTPException(409, f"The code {clash.code} already belongs to {clash.name}")
    existing = {c.code_norm: c for c in item.codes}  # keep rows whose code is unchanged
    kept = []
    for c, n in zip(codes, norms):
        row = existing.get(n) or ItemCode(code_norm=n, branch_id=actor.branch.id)
        row.kind, row.code = c.kind, c.code
        kept.append(row)
    item.codes = kept


def _get_item(db: Session, actor: Actor, item_id: uuid.UUID) -> Item:
    item = db.get(Item, item_id)
    if not item or item.branch_id != actor.branch.id:
        raise HTTPException(404, "Item not found")
    return item


@router.get("/items")
def list_items(q: str = "", stock: Literal["all", "low", "out"] = "all", limit: int = Query(100, ge=1, le=500),
               actor: Actor = Depends(can_stock), db: Session = Depends(get_db)):
    qty = (select(StockMovement.item_id, func.sum(StockMovement.qty).label("qty"))
           .where(StockMovement.branch_id == actor.branch.id).group_by(StockMovement.item_id).subquery())
    on_hand_col = func.coalesce(qty.c.qty, 0)
    stmt = (select(Item, on_hand_col).outerjoin(qty, qty.c.item_id == Item.id)
            .where(Item.branch_id == actor.branch.id, Item.is_active).order_by(Item.name).limit(limit))
    if q.strip():
        like, norm = f"%{q.strip()}%", normalize_code(q)
        conds = [Item.name.ilike(like), Item.brand.ilike(like), Item.category.ilike(like), Item.fitment.ilike(like),
                 Item.number.ilike(like)]
        if len(norm) >= 3:
            conds.append(Item.id.in_(select(ItemCode.item_id).where(ItemCode.branch_id == actor.branch.id,
                                                                    ItemCode.code_norm.contains(norm))))
        stmt = stmt.where(or_(*conds))
    if stock == "low":
        stmt = stmt.where(Item.reorder_level > 0, on_hand_col <= Item.reorder_level)
    elif stock == "out":
        stmt = stmt.where(on_hand_col <= 0)
    return [item_out(item, q_) for item, q_ in db.execute(stmt)]


@router.get("/items/lookup")
def lookup_item(code: str, actor: Actor = Depends(can_stock), db: Session = Depends(get_db)):
    """A scanner types the code and Enter; this finds the item it belongs to."""
    norm = normalize_code(code)
    item = db.scalar(select(Item).join(ItemCode, ItemCode.item_id == Item.id)
                     .where(ItemCode.branch_id == actor.branch.id, ItemCode.code_norm == norm))
    if not item:
        raise HTTPException(404, {"code": "unknown_code", "message": f"No item has the code {code.strip()}", "code_norm": norm})
    return item_out(item, on_hand(db, item.id))


@router.post("/items", status_code=201)
def create_item(body: ItemCreate, actor: Actor = Depends(can_stock), db: Session = Depends(get_db)):
    if body.opening_qty and not actor.can("stock-adjust"):
        raise HTTPException(403, "Setting opening stock needs the stock-adjust permission")
    item = Item(number=next_number(db, actor.branch, "item"),
                **body.model_dump(exclude={"codes", "opening_qty", "opening_cost"}))
    db.add(item)
    db.flush()
    _set_codes(db, actor, item, body.codes)
    if body.opening_qty:
        move(db, item.id, "opening", body.opening_qty, unit_cost=body.opening_cost, reason="Opening stock")
    db.commit()
    return item_out(item, on_hand(db, item.id))


@router.get("/items/{item_id}")
def get_item(item_id: uuid.UUID, actor: Actor = Depends(can_stock), db: Session = Depends(get_db)):
    item = _get_item(db, actor, item_id)
    movements = db.execute(select(StockMovement, User.username).outerjoin(User, User.id == StockMovement.created_by)
                           .where(StockMovement.item_id == item.id).order_by(StockMovement.created_at.desc()).limit(200)).all()
    return {**item_out(item, on_hand(db, item.id)),
            "movements": [{"id": m.id, "at": m.created_at, "kind": m.kind, "qty": m.qty, "unit_cost": m.unit_cost,
                           "reason": m.reason, "source_type": m.source_type, "source_id": m.source_id, "user": u}
                          for m, u in movements]}


@router.put("/items/{item_id}")
def update_item(item_id: uuid.UUID, body: ItemUpdate, actor: Actor = Depends(can_stock), db: Session = Depends(get_db)):
    item = _get_item(db, actor, item_id)
    if body.version != item.version:
        raise HTTPException(409, "Someone else changed this item. Reload and try again.")
    for key, value in body.model_dump(exclude={"version", "codes"}).items():
        setattr(item, key, value)
    _set_codes(db, actor, item, body.codes)
    db.commit()
    return item_out(item, on_hand(db, item.id))


@router.post("/items/{item_id}/adjust")
def adjust_stock(item_id: uuid.UUID, body: AdjustIn, actor: Actor = Depends(require("stock-adjust")),
                 db: Session = Depends(get_db)):
    item = _get_item(db, actor, item_id)
    try:
        move(db, item.id, "adjustment", body.qty, unit_cost=body.unit_cost, reason=body.reason)
    except StockError as e:
        raise HTTPException(422, str(e))
    db.commit()
    return get_item(item.id, actor, db)


@router.get("/stock/levels")
def stock_levels(ids: list[uuid.UUID] = Query(default_factory=list), actor: Actor = Depends(can_stock),
                 db: Session = Depends(get_db)):
    """On-hand quantities for a set of items (used by job cards in Phase 3)."""
    return {str(k): v for k, v in on_hand_map(db, ids).items()}
