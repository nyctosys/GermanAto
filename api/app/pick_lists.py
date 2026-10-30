"""Team-managed pick-lists. DEFAULTS seed each list and fill in any new names that are still
missing; the team adds, renames and retires entries themselves (Settings, Pick-lists)."""
import re
from difflib import get_close_matches

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import Car, Item, LabourCode, PickListEntry

DEFAULTS: dict[str, list[str]] = {
    "fitment": [],  # grows as the team adds cars a part fits ("Audi e-tron", "BMW 5 Series F10")
    "car_make": [
        "Toyota", "Honda", "Suzuki", "Nissan", "Mitsubishi", "Daihatsu", "Mazda", "Subaru", "Lexus", "Hyundai", "Kia", "Changan", "MG",
        "Proton", "Haval", "DFSK", "FAW", "Isuzu", "BMW", "Mercedes-Benz", "Audi", "Volkswagen", "Porsche", "Land Rover", "Jaguar",
        "Volvo", "Peugeot", "Renault", "Ford", "Chevrolet", "Jeep", "Tesla", "BYD",
    ],
    # Permanent company brands for inventory (seeded on every branch; the team can still add more).
    # Aftermarket / genuine lines stay as extras for parts stock.
    "part_brand": [
        "Audi", "BMW", "BYD", "Changan", "Chevrolet", "Daihatsu", "Ford", "Haval", "Honda", "Hyundai",
        "Isuzu", "Jaguar", "Jeep", "Kia", "Land Rover", "Lexus", "Mazda", "Mercedes-Benz", "MG", "MINI",
        "Mitsubishi", "Nissan", "Peugeot", "Porsche", "Renault", "Subaru", "Suzuki", "Toyota", "Volkswagen", "Volvo",
        "Toyota Genuine", "Honda Genuine", "Suzuki Genuine", "BMW Genuine", "Mercedes Genuine", "Audi Genuine", "VW Genuine",
        "Bosch", "Mann", "Mahle", "Denso", "NGK", "Brembo", "ATE", "TRW", "Sachs", "ZF",
        "Bilstein", "KYB", "Monroe", "Gates", "Continental", "Valeo", "Hella", "Osram",
        "Castrol", "Shell", "Mobil", "Total", "Liqui Moly", "Febi", "Lemförder", "Meyle", "SKF",
        "Optimax", "Local",
    ],
    "part_category": [
        "Filters", "Oil and fluids", "Brakes", "Suspension", "Engine", "Transmission", "Electrical", "Lighting", "Cooling", "Belts and hoses",
        "Exhaust", "Body and glass", "Tyres and wheels", "Battery", "Spark plugs and ignition", "Accessories", "Tools and consumables",
    ],
    "labour_category": [
        "Service", "Engine", "Brakes", "Suspension and steering", "Transmission", "Electrical", "Air conditioning", "Body and paint",
        "Tyres and wheels", "Diagnosis", "Washing and detailing",
    ],
}
# The permission that lets a person see and add to each list.
PERMISSION = {"fitment": "inventory", "car_make": "customers", "part_brand": "inventory", "part_category": "inventory", "labour_category": "labour-codes"}
# Where each list's value is stored on records, so a rename carries through.
USED_BY = {"fitment": Item.fitment, "car_make": Car.make, "part_brand": Item.brand, "part_category": Item.category, "labour_category": LabourCode.category}


def tidy(name: str) -> str:
    """Trim, collapse spaces, and capitalise a name typed all in lower case ("liqui moly" becomes "Liqui Moly")."""
    name = re.sub(r"\s+", " ", name or "").strip()
    return name.title() if name and name == name.lower() else name


def split_fits(value: str | None) -> list[str]:
    """An item's Fits is one text of names joined by semicolons (older ones may use commas)."""
    return [p.strip() for p in re.split(r"[;,]", value or "") if p.strip()]


def squash(name: str) -> str:
    """Spelling-blind form: "Liqui-Moly", "liqui moly" and "LiquiMoly" all become "liquimoly"."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def seed(db: Session, branch_id, kind: str) -> None:
    """Puts every default name on the list, plus anything already typed on records.
    Safe to call again: names that are already there (even if retired) are left alone, so a
    later DEFAULTS update still adds new brands like BMW without bringing back a retired entry."""
    known = {
        e.key
        for e in db.scalars(
            select(PickListEntry).where(PickListEntry.branch_id == branch_id, PickListEntry.kind == kind)
        )
    }
    col = USED_BY[kind]
    used = [v for v in db.scalars(select(col).distinct()) if v and v.strip()]
    if kind == "fitment":
        used = [p for v in used for p in split_fits(v)]
    for name in [*DEFAULTS[kind], *(tidy(v) for v in used)]:
        key = name.lower()
        if name and key not in known:
            known.add(key)
            db.add(PickListEntry(branch_id=branch_id, kind=kind, name=name, key=key))
    db.flush()


def entries(db: Session, branch_id, kind: str, include_retired: bool = False) -> list[PickListEntry]:
    seed(db, branch_id, kind)
    stmt = select(PickListEntry).where(PickListEntry.branch_id == branch_id, PickListEntry.kind == kind).order_by(func.lower(PickListEntry.name))
    if not include_retired:
        stmt = stmt.where(PickListEntry.is_active)
    return list(db.scalars(stmt))


def lookalike(db: Session, branch_id, kind: str, name: str, ignore_id=None) -> str | None:
    """A spelling close to an existing entry ("Bosh" for "Bosch"), so a typo is caught before it becomes a second entry."""
    pool = {squash(e.name): e.name for e in entries(db, branch_id, kind, include_retired=True) if e.id != ignore_id}
    mine = squash(name)
    close = get_close_matches(mine, list(pool), n=1, cutoff=0.75)
    if not close:  # one letter wrong, missing, extra or swapped ("Sakuzi" for "Sakura") scores low on short names
        close = [k for k in pool if len(k) >= 5 and one_slip(mine, k)][:1]
    return pool[close[0]] if close else None


def one_slip(a: str, b: str) -> bool:
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        return len(diff) == 1 or (len(diff) == 2 and diff[1] == diff[0] + 1 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]])
    short, long = sorted((a, b), key=len)
    return any(long[:i] + long[i + 1:] == short for i in range(len(long)))


def is_used(db: Session, kind: str, name: str) -> bool:
    col = USED_BY[kind]
    if kind == "fitment":
        return any(name.lower() in (p.lower() for p in split_fits(v)) for v in db.scalars(select(col).where(col.ilike(f"%{name}%"))))
    return bool(db.scalar(select(func.count()).select_from(col.class_).where(func.lower(col) == name.lower())))


def rename_on_records(db: Session, kind: str, old: str, new: str, branch_id) -> None:
    col = USED_BY[kind]
    if kind == "fitment":
        for it in db.scalars(select(Item).where(Item.branch_id == branch_id, Item.fitment.ilike(f"%{old}%"))):
            it.fitment = "; ".join(new if p.lower() == old.lower() else p for p in split_fits(it.fitment))
        return
    stmt = update(col.class_).where(func.lower(col) == old.lower()).values({col.key: new})
    if hasattr(col.class_, "branch_id"):
        stmt = stmt.where(col.class_.branch_id == branch_id)
    db.execute(stmt)
