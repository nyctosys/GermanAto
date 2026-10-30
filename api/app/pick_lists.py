"""Team-managed pick-lists. The defaults below only seed a branch's list the first time it is opened;
after that the team adds, renames and retires entries themselves (Settings, Pick-lists)."""
import re
from difflib import get_close_matches

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import Car, Item, LabourCode, PickListEntry

DEFAULTS: dict[str, list[str]] = {
    "car_make": [
        "Toyota", "Honda", "Suzuki", "Nissan", "Mitsubishi", "Daihatsu", "Mazda", "Subaru", "Lexus", "Hyundai", "Kia", "Changan", "MG",
        "Proton", "Haval", "DFSK", "FAW", "Isuzu", "BMW", "Mercedes-Benz", "Audi", "Volkswagen", "Porsche", "Land Rover", "Jaguar",
        "Volvo", "Peugeot", "Renault", "Ford", "Chevrolet", "Jeep", "Tesla", "BYD",
    ],
    "part_brand": [
        "Toyota Genuine", "Honda Genuine", "Suzuki Genuine", "Bosch", "Mann", "Mahle", "Denso", "NGK", "Brembo", "ATE", "TRW", "Sachs",
        "Bilstein", "KYB", "Monroe", "Gates", "Continental", "Valeo", "Hella", "Castrol", "Shell", "Mobil", "Total", "Liqui Moly", "Febi",
        "Lemförder", "Meyle", "SKF", "Optimax", "Local",
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
PERMISSION = {"car_make": "customers", "part_brand": "inventory", "part_category": "inventory", "labour_category": "labour-codes"}
# Where each list's value is stored on records, so a rename carries through.
USED_BY = {"car_make": Car.make, "part_brand": Item.brand, "part_category": Item.category, "labour_category": LabourCode.category}


def tidy(name: str) -> str:
    """Trim, collapse spaces, and capitalise a name typed all in lower case ("liqui moly" becomes "Liqui Moly")."""
    name = re.sub(r"\s+", " ", name or "").strip()
    return name.title() if name and name == name.lower() else name


def seed(db: Session, branch_id, kind: str) -> None:
    """Fills an empty list with the defaults plus anything already typed on records, once."""
    if db.scalar(select(func.count()).select_from(PickListEntry).where(PickListEntry.branch_id == branch_id, PickListEntry.kind == kind)):
        return
    col = USED_BY[kind]
    used = [v for v in db.scalars(select(col).distinct()) if v and v.strip()]
    seen: set[str] = set()
    for name in [*DEFAULTS[kind], *(tidy(v) for v in used)]:
        if name and name.lower() not in seen:
            seen.add(name.lower())
            db.add(PickListEntry(branch_id=branch_id, kind=kind, name=name, key=name.lower()))
    db.flush()


def entries(db: Session, branch_id, kind: str, include_retired: bool = False) -> list[PickListEntry]:
    seed(db, branch_id, kind)
    stmt = select(PickListEntry).where(PickListEntry.branch_id == branch_id, PickListEntry.kind == kind).order_by(func.lower(PickListEntry.name))
    if not include_retired:
        stmt = stmt.where(PickListEntry.is_active)
    return list(db.scalars(stmt))


def lookalike(db: Session, branch_id, kind: str, name: str, ignore_id=None) -> str | None:
    """A spelling close to an existing entry ("Bosh" for "Bosch"), so a typo is caught before it becomes a second entry."""
    pool = {e.key: e.name for e in entries(db, branch_id, kind, include_retired=True) if e.id != ignore_id}
    close = get_close_matches(name.lower(), list(pool), n=1, cutoff=0.82)
    return pool[close[0]] if close else None


def rename_on_records(db: Session, kind: str, old: str, new: str, branch_id) -> None:
    col = USED_BY[kind]
    stmt = update(col.class_).where(func.lower(col) == old.lower()).values({col.key: new})
    if hasattr(col.class_, "branch_id"):
        stmt = stmt.where(col.class_.branch_id == branch_id)
    db.execute(stmt)
