"""Every change to stock goes through move(): one place that locks the item,
refuses to go below zero, values outgoing stock at average cost and keeps
the weighted average cost up to date (spec D2, D4)."""

import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Item, StockMovement

ZERO = Decimal("0")


class StockError(ValueError):
    pass


def weighted_average(on_hand: Decimal, avg_cost: Decimal, qty_in: Decimal, unit_cost: Decimal) -> Decimal:
    """Average cost after receiving qty_in at unit_cost. Stock that was at or
    below zero carries no cost of its own, so the new cost simply wins."""
    if on_hand <= 0:
        return unit_cost
    total = on_hand + qty_in
    return ((on_hand * avg_cost + qty_in * unit_cost) / total).quantize(Decimal("0.0001"), ROUND_HALF_UP)


def on_hand(db: Session, item_id: uuid.UUID) -> Decimal:
    return db.scalar(select(func.coalesce(func.sum(StockMovement.qty), 0)).where(StockMovement.item_id == item_id))


def on_hand_map(db: Session, item_ids: list[uuid.UUID]) -> dict[uuid.UUID, Decimal]:
    if not item_ids:
        return {}
    rows = db.execute(select(StockMovement.item_id, func.sum(StockMovement.qty))
                      .where(StockMovement.item_id.in_(item_ids)).group_by(StockMovement.item_id))
    return {item_id: qty for item_id, qty in rows}


def move(db: Session, item_id: uuid.UUID, kind: str, qty: Decimal, *, unit_cost: Decimal | None = None,
         reason: str = "", source_type: str | None = None, source_id: uuid.UUID | None = None,
         allow_negative: bool = False) -> StockMovement:
    if qty == 0:
        raise StockError("Quantity can't be zero")
    # Row lock: two people issuing the last unit at once can't both succeed.
    item = db.scalar(select(Item).where(Item.id == item_id).with_for_update())
    if item is None:
        raise StockError("Item not found")
    current = on_hand(db, item.id)

    if qty < 0:
        if current + qty < 0 and not allow_negative:
            raise StockError(f"Only {current.normalize():f} {item.unit} of {item.name} in stock")
        cost = item.avg_cost
    else:
        cost = item.avg_cost if unit_cost is None else unit_cost
        if cost < 0:
            raise StockError("Cost can't be negative")
        item.avg_cost = weighted_average(current, item.avg_cost, qty, cost)

    movement = StockMovement(item_id=item.id, branch_id=item.branch_id, kind=kind, qty=qty, unit_cost=cost,
                             reason=reason, source_type=source_type, source_id=source_id)
    db.add(movement)
    db.flush()
    # Every unit in or out is also an inventory entry in the books, so stock value and the journal can't disagree.
    from app import posting  # late: posting builds on the models, which stock already imports
    from app.models import Branch
    posting.stock_movement(db, db.get(Branch, item.branch_id), movement, reason or f"Stock {kind}: {item.name}")
    return movement


if __name__ == "__main__":
    D = Decimal
    assert weighted_average(D(10), D(100), D(10), D(200)) == D(150)
    assert weighted_average(D(0), D(100), D(5), D(80)) == D(80)
    assert weighted_average(D(-2), D(100), D(5), D(80)) == D(80)
    assert weighted_average(D(3), D("33.3333"), D(1), D(40)) == D("35.0000")
    print("ok")
