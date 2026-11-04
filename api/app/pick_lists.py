"""Team-managed pick-lists. DEFAULTS seed each list and fill in any new names that are still
missing; the team adds, renames and retires entries themselves (Settings, Pick-lists)."""
import re
from difflib import get_close_matches

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import Car, Item, LabourCode, PickListEntry

# Common make + model names for Fits. Search narrows as you type ("bm" → BMW M5, BMW 3 Series, …).
# The team can still add more; registered cars (year make model) are merged in on seed too.
FITMENT_CARS = [
    # Honda
    "Honda Civic", "Honda City", "Honda Accord", "Honda BR-V", "Honda HR-V", "Honda Vezel", "Honda Fit", "Honda Freed",
    "Honda N-Wgn", "Honda Grace", "Honda Insight", "Honda CR-V", "Honda Odyssey", "Honda Jade",
    # Toyota
    "Toyota Corolla", "Toyota Yaris", "Toyota Camry", "Toyota Fortuner", "Toyota Hilux", "Toyota Revo", "Toyota Prado",
    "Toyota Land Cruiser", "Toyota Aqua", "Toyota Prius", "Toyota Vitz", "Toyota Passo", "Toyota Rush", "Toyota Raize",
    "Toyota Corolla Cross", "Toyota RAV4", "Toyota Crown", "Toyota Mark X", "Toyota Premio", "Toyota Allion",
    "Toyota Hiace", "Toyota Coaster", "Toyota Surf", "Toyota Axio", "Toyota Fielder",
    # Suzuki
    "Suzuki Alto", "Suzuki Cultus", "Suzuki Swift", "Suzuki Wagon R", "Suzuki Bolan", "Suzuki Ravi", "Suzuki Mehran",
    "Suzuki Jimny", "Suzuki Every", "Suzuki Vitara", "Suzuki Ciaz", "Suzuki Baleno", "Suzuki Spacia", "Suzuki Hustler",
    "Suzuki Carry", "Suzuki APV", "Suzuki Ertiga", "Suzuki SX4",
    # Daihatsu / Nissan / Mitsubishi
    "Daihatsu Mira", "Daihatsu Cuore", "Daihatsu Move", "Daihatsu Hijet", "Daihatsu Tanto", "Daihatsu Cast",
    "Nissan Dayz", "Nissan Note", "Nissan Sunny", "Nissan Patrol", "Nissan X-Trail", "Nissan Clipper", "Nissan Juke",
    "Nissan Leaf", "Nissan Skyline", "Mitsubishi Pajero", "Mitsubishi Lancer", "Mitsubishi Mirage", "Mitsubishi Outlander",
    "Mitsubishi Ek Wagon", "Mitsubishi Minicab",
    # Korean / Chinese popular here
    "Hyundai Tucson", "Hyundai Elantra", "Hyundai Sonata", "Hyundai Santa Fe", "Hyundai Staria", "Hyundai Ioniq",
    "Hyundai Porter", "Kia Sportage", "Kia Picanto", "Kia Carnival", "Kia Sorento", "Kia Stonic", "Kia Grand Carnival",
    "Changan Alsvin", "Changan Karvaan", "Changan Oshan X7", "Changan M9", "MG HS", "MG ZS", "MG 5", "MG 4",
    "Haval Jolion", "Haval H6", "BYD Atto 3", "BYD Seal", "BYD Sealion", "Proton Saga", "Proton X70", "Proton X50",
    "FAW V2", "DFSK Glory 580", "Isuzu D-Max",
    # German / European (workshop focus)
    "BMW 1 Series", "BMW 2 Series", "BMW 3 Series", "BMW 4 Series", "BMW 5 Series", "BMW 6 Series", "BMW 7 Series",
    "BMW 8 Series", "BMW X1", "BMW X2", "BMW X3", "BMW X4", "BMW X5", "BMW X6", "BMW X7",
    "BMW M2", "BMW M3", "BMW M4", "BMW M5", "BMW M8", "BMW iX", "BMW i4", "BMW i7", "BMW Z4",
    "Mercedes-Benz A-Class", "Mercedes-Benz B-Class", "Mercedes-Benz C-Class", "Mercedes-Benz E-Class",
    "Mercedes-Benz S-Class", "Mercedes-Benz CLA", "Mercedes-Benz CLS", "Mercedes-Benz GLA", "Mercedes-Benz GLB",
    "Mercedes-Benz GLC", "Mercedes-Benz GLE", "Mercedes-Benz GLS", "Mercedes-Benz G-Class", "Mercedes-Benz V-Class",
    "Audi A1", "Audi A3", "Audi A4", "Audi A5", "Audi A6", "Audi A7", "Audi A8", "Audi Q2", "Audi Q3", "Audi Q5",
    "Audi Q7", "Audi Q8", "Audi TT", "Audi e-tron", "Audi RS5", "Audi RS6", "Audi RS7",
    "Volkswagen Golf", "Volkswagen Passat", "Volkswagen Tiguan", "Volkswagen Polo", "Volkswagen Arteon",
    "Porsche Cayenne", "Porsche Macan", "Porsche Panamera", "Porsche 911", "Porsche Taycan",
    "Land Rover Range Rover", "Land Rover Discovery", "Land Rover Defender", "Land Rover Evoque", "Land Rover Velar",
    "Jaguar XF", "Jaguar XE", "Jaguar F-Pace", "Volvo XC40", "Volvo XC60", "Volvo XC90", "Volvo S60", "Volvo S90",
    "Peugeot 2008", "Peugeot 3008", "Peugeot 5008", "Renault Duster", "Renault Koleos",
    # Other common
    "Lexus RX", "Lexus LX", "Lexus ES", "Lexus NX", "Lexus GX", "Mazda CX-5", "Mazda 3", "Mazda 6", "Mazda CX-30",
    "Subaru Forester", "Subaru XV", "Subaru Impreza", "Subaru Legacy", "Ford Ranger", "Ford Everest", "Ford Mustang",
    "Jeep Wrangler", "Jeep Grand Cherokee", "Jeep Compass", "Chevrolet Captiva", "Tesla Model 3", "Tesla Model Y",
    "Tesla Model S", "Tesla Model X", "MINI Cooper",
]

DEFAULTS: dict[str, list[str]] = {
    "fitment": FITMENT_CARS,
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


def car_fit_label(year: int | None, make: str, model: str) -> str:
    """Same shape as the car title on screen: '2014 Honda Civic'."""
    return " ".join(p for p in ([str(year)] if year else []) + [make or "", model or ""] if p).strip()


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
        # Every car on file appears as a Fits choice (year make model), so stock pickers match the Cars list.
        used += [car_fit_label(c.year, c.make, c.model) for c in db.scalars(select(Car))]
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
