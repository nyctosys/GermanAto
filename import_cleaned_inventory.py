"""Apply the cleaned inventory workbook to the database.

Imports *names and manufacturer codes only*. Deliberately does not touch:

  * quantities - the workbook is a 29 Aug snapshot and stock has moved since,
    so importing them would silently reverse two days of movements;
  * categories - they were not cleaned, and reworking them is a separate job;
  * items missing from the workbook - 20 were created after it was generated.

Matching is on part_number, which is stable.

    DATABASE_URL="mysql+pymysql://user:pass@localhost/germanato_db" \\
        python3 import_cleaned_inventory.py path/to/workbook.xlsx [--apply]

Without --apply it reports every change it would make and writes nothing.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from dotenv import load_dotenv

load_dotenv()

if not os.getenv("DATABASE_URL"):
    sys.exit("Set DATABASE_URL first.")

args = [a for a in sys.argv[1:] if not a.startswith("--")]
if not args:
    sys.exit("Give the path to the cleaned .xlsx")
WORKBOOK = args[0]
APPLY = "--apply" in sys.argv

import openpyxl                                            # noqa: E402
from app import app, db                                    # noqa: E402
from models import Inventory                               # noqa: E402

# Codes that survived the clean. A model year is not a part code, so those are
# excluded rather than mangled.
CODE_PATTERNS = [
    r"\bA\s?\d{3}\s?\d{3}\s?\d{2}\s?\d{2}\b",
    r"\b\d{5}\s?[A-Z]{2,3}\s?\d{2,3}\b",
    r"\b\d{5,}\b",
    r"\b[A-Z]\d{4,}\b",
]
YEAR = re.compile(r"\b(19|20)\d{2}\b")


def residual_code(name):
    """A manufacturer code still embedded in the name, or None."""
    upper = (name or "").upper()
    for pattern in CODE_PATTERNS:
        for match in re.finditer(pattern, upper):
            if YEAR.fullmatch(match.group(0).strip()):
                continue                      # a model year, not a part code
            return match.group(0).strip()
    return None


def load_rows(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    sheet = wb["Inventory"]
    header = [c.value for c in sheet[1]]
    rows = [dict(zip(header, r)) for r in sheet.iter_rows(min_row=2, values_only=True) if any(r)]
    return {str(r["Part Number"]).strip(): r for r in rows if r.get("Part Number")}


def main():
    sheet_rows = load_rows(WORKBOOK)

    with app.app_context():
        items = {i.part_number.strip(): i for i in Inventory.query.all()}

        renamed, coded, unchanged, missing = [], [], 0, []
        needs_review = []

        # manufacturer_part_number is UNIQUE, and rightly so - one code means one
        # part. Where the workbook gives the same code to several items they are
        # duplicates that have to be merged first, so their codes are held back
        # rather than failing the whole import.
        norm = lambda v: re.sub(r"[^A-Z0-9]", "", str(v or "").upper())
        code_owners = {}
        for pn, row in sheet_rows.items():
            code = norm(row.get("Manufacturer Part Number"))
            if code:
                code_owners.setdefault(code, []).append(pn)
        contested = {c: pns for c, pns in code_owners.items() if len(pns) > 1}
        blocked_parts = {pn for pns in contested.values() for pn in pns}

        # A code already held by a different item in the database blocks too.
        held = {norm(i.manufacturer_part_number): pn
                for pn, i in items.items() if i.manufacturer_part_number}

        for part_number, item in items.items():
            row = sheet_rows.get(part_number)
            if not row:
                missing.append(part_number)
                continue

            new_name = str(row.get("Item Name") or "").strip()
            new_mpn = str(row.get("Manufacturer Part Number") or "").strip()
            changed = False

            if new_name and new_name != item.name:
                renamed.append((part_number, item.name, new_name))
                item.name = new_name
                changed = True

            # Only fill a code in; never overwrite one the database already has
            # with a blank from the sheet, and never create a duplicate code.
            if new_mpn and new_mpn != (item.manufacturer_part_number or "").strip():
                code = norm(new_mpn)
                owner = held.get(code)
                if part_number in blocked_parts or (owner and owner != part_number):
                    pass                      # reported below, left for the merge
                else:
                    coded.append((part_number, item.manufacturer_part_number, new_mpn))
                    item.manufacturer_part_number = new_mpn
                    held[code] = part_number
                    changed = True

            leftover = residual_code(new_name)
            if leftover:
                needs_review.append((part_number, new_name, leftover,
                                     bool(new_mpn or item.manufacturer_part_number)))
            if not changed:
                unchanged += 1

        print(f"items in database        : {len(items)}")
        print(f"matched in workbook      : {len(items) - len(missing)}")
        print(f"not in workbook (skipped): {len(missing)}   <- created after it was generated")
        print(f"names to update          : {len(renamed)}")
        print(f"codes to fill in         : {len(coded)}")
        print(f"already correct          : {unchanged}")

        if needs_review:
            print(f"\nSTILL CARRY A CODE IN THE NAME ({len(needs_review)}) - review by hand:")
            for pn, name, code, has_mpn in needs_review:
                warn = "" if has_mpn else "   <-- no code recorded; moving it is the only copy"
                print(f"  {pn:<7} {name[:46]:<46} code~{code}{warn}")

        if contested:
            print(f"\nCODES HELD BACK ({len(contested)}) - the same code on more than one item.")
            print("  These are true duplicates: merge them, adding the stock up, then re-run.")
            for code, pns in list(contested.items())[:15]:
                stock = {pn: (items[pn].quantity if pn in items else '?') for pn in pns}
                name = sheet_rows[pns[0]].get("Item Name")
                print(f"  {code:<18} {pns}  {str(name)[:32]:<32} stock {stock}")
            if len(contested) > 15:
                print(f"  ... and {len(contested) - 15} more")

        if APPLY:
            db.session.commit()
            print("\nCommitted names and codes. Quantities, categories and stock untouched.")
        else:
            db.session.rollback()
            print("\nDry run - nothing written. Re-run with --apply to commit.")


if __name__ == "__main__":
    main()
