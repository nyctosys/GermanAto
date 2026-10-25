"""Merge inventory items that share one manufacturer part number.

Why this exists
---------------
The cleaned workbook gives 707 items a manufacturer part number, but 38 of
those codes are claimed by more than one item. A manufacturer part number
identifies one part, so import_cleaned_inventory.py refuses to write any of
them rather than guess - which is why those 38 codes are still missing.

They are not one problem. Most are the same part entered twice, with the stock
split across two records; a few are genuinely different parts where one record
carries the wrong code. Merging the second kind would destroy real information.

What this script decides for itself, and what it does not
--------------------------------------------------------
It merges only where the two records carry *byte-identical names*. There is no
judgement in "BMW OIL FILTER" and "BMW OIL FILTER" being the same filter.

Everything else it refuses to touch until you say so, because name similarity
does not separate the two cases. Measured on this data:

    HONDA CIVIC AIR FILTER / TOYOTA AIR FILTER ZX      0.62   different parts
    FRONT BRAKE PAD WEAR SENSOR / AUDI SENSOR          0.23   the same part

A threshold anywhere between those merges the Honda into the Toyota. So the
remaining groups go into a decisions file you edit once, and the script obeys
it.

Usage
-----
    export DATABASE_URL="mysql+pymysql://user:pass@localhost/germanato_db"

    python3 resolve_duplicate_codes.py WORKBOOK.xlsx                 # report
    python3 resolve_duplicate_codes.py WORKBOOK.xlsx --write-decisions
    python3 resolve_duplicate_codes.py WORKBOOK.xlsx --apply

A merge sums the stock into one record, moves that item's transaction history
and any repair-order lines onto it, notes what happened in its description,
and deletes the emptied record. It runs in one transaction.
"""
import os
import re
import sys
import collections

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from dotenv import load_dotenv

load_dotenv()

if not os.getenv("DATABASE_URL"):
    sys.exit("Set DATABASE_URL first.")

ARGS = sys.argv[1:]
APPLY = "--apply" in ARGS
WRITE_DECISIONS = "--write-decisions" in ARGS
PATHS = [a for a in ARGS if not a.startswith("--")]
if not PATHS:
    sys.exit("Give me the cleaned workbook: python3 resolve_duplicate_codes.py FILE.xlsx")
WORKBOOK = PATHS[0]
DECISIONS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "duplicate_code_decisions.txt")

try:
    import openpyxl
except ImportError:
    sys.exit("openpyxl is needed to read the workbook: backend/env/bin/pip install openpyxl")

from sqlalchemy import text                        # noqa: E402
from app import app, db                            # noqa: E402
from models import Inventory                       # noqa: E402


def normalise(code):
    """'04E 905 602' and '04E905602' are one code written two ways."""
    return re.sub(r"[^A-Za-z0-9]", "", code or "").upper()


def read_workbook(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = wb.active.iter_rows(values_only=True)
    header = [str(h).strip() if h else "" for h in next(rows)]
    try:
        i_code = header.index("Manufacturer Part Number")
        i_part = header.index("Part Number")
        i_name = header.index("Item Name")
    except ValueError:
        sys.exit("That workbook has no 'Manufacturer Part Number' / 'Part Number' / "
                 "'Item Name' columns - is it the cleaned inventory report?")

    out = []
    for row in rows:
        if not row:
            continue
        code = str(row[i_code] or "").strip()
        part = str(row[i_part] or "").strip()
        if code and part:
            out.append((code, part, str(row[i_name] or "").strip()))
    return out


def contested_groups(entries):
    groups = collections.defaultdict(list)
    for code, part, name in entries:
        key = normalise(code)
        if key:
            groups[key].append({"code": code, "part_number": part, "name": name})
    return {k: v for k, v in groups.items() if len({e["part_number"] for e in v}) > 1}


def certain(group):
    """Same code, same name - no judgement required."""
    return len({e["name"].strip().upper() for e in group}) == 1


def load_decisions():
    """code -> surviving part number, from the file you edited."""
    decisions = {}
    if not os.path.exists(DECISIONS_FILE):
        return decisions
    with open(DECISIONS_FILE, encoding="utf-8") as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            bits = line.split()
            if len(bits) >= 2 and bits[1].upper() != "SEPARATE":
                decisions[bits[0].upper()] = bits[1]
    return decisions


def write_decisions(groups, rows_by_part):
    lines = [
        "# One line per contested manufacturer code.",
        "#",
        "#   CODE   <part number that should survive>   -> merge the others into it",
        "#   CODE   SEPARATE                            -> leave alone; one code is wrong",
        "#",
        "# Groups whose items have identical names are merged without needing a line",
        "# here. Everything below needs your eye, because the names differ and only",
        "# someone holding the parts can say whether that matters.",
        "",
    ]
    for key in sorted(groups):
        group = groups[key]
        if certain(group):
            continue
        lines.append(f"# {key}")
        for entry in group:
            row = rows_by_part.get(entry["part_number"])
            stock = f"{row.quantity} in stock" if row else "NOT IN DATABASE"
            shelf = f", {row.location}" if row and row.location else ""
            lines.append(f"#     {entry['part_number']:<8} {stock:<16}{shelf:<18} "
                         f"{entry['code']:<20} {entry['name'][:44]}")
        lines.append(f"{key}   SEPARATE")
        lines.append("")

    with open(DECISIONS_FILE, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return DECISIONS_FILE


def pick_survivor(rows, named_part=None):
    """The record the others fold into.

    Your choice wins. Failing that: most stock, then one that has a shelf
    location, then the oldest record - it has the longest history attached.
    """
    if named_part:
        for row in rows:
            if row.part_number == named_part:
                return row
    return sorted(rows, key=lambda r: (-(r.quantity or 0), 0 if r.location else 1, r.id))[0]


def merge(survivor, losers, code):
    moved_tx = moved_parts = 0
    gained = 0

    for loser in losers:
        gained += loser.quantity or 0
        moved_tx += db.session.execute(
            text("UPDATE inventory_transactions SET inventory_id = :keep WHERE inventory_id = :drop"),
            {"keep": survivor.id, "drop": loser.id}).rowcount
        moved_parts += db.session.execute(
            text("UPDATE repair_order_part SET inventory_id = :keep WHERE inventory_id = :drop"),
            {"keep": survivor.id, "drop": loser.id}).rowcount

    survivor.quantity = (survivor.quantity or 0) + gained
    survivor.manufacturer_part_number = code
    note = ("Merged " + ", ".join(l.part_number for l in losers) +
            f" into this item ({gained} units) - same manufacturer code {code}.")
    survivor.description = f"{survivor.description}\n{note}".strip() if survivor.description else note

    for loser in losers:
        db.session.delete(loser)

    return {"gained": gained, "moved_tx": moved_tx, "moved_parts": moved_parts}


def main():
    entries = read_workbook(WORKBOOK)
    groups = contested_groups(entries)

    with app.app_context():
        wanted = {e["part_number"] for g in groups.values() for e in g}
        rows_by_part = {
            r.part_number: r
            for r in Inventory.query.filter(Inventory.part_number.in_(wanted)).all()
        } if wanted else {}

        if WRITE_DECISIONS:
            path = write_decisions(groups, rows_by_part)
            print(f"Wrote {path}")
            print("Edit it, then re-run with --apply.")
            return

        decisions = load_decisions()
        auto = [k for k in sorted(groups) if certain(groups[k])]
        chosen = [k for k in sorted(groups) if not certain(groups[k]) and k in decisions]
        waiting = [k for k in sorted(groups) if not certain(groups[k]) and k not in decisions]

        print(f"contested codes in the workbook : {len(groups)}")
        print(f"  identical names, safe to merge: {len(auto)}")
        print(f"  merging because you said so   : {len(chosen)}")
        print(f"  waiting on a decision         : {len(waiting)}")

        merged = skipped = 0
        for key in auto + chosen:
            group = groups[key]
            rows = [rows_by_part[e["part_number"]] for e in group
                    if e["part_number"] in rows_by_part]
            if len(rows) < 2:
                print(f"\n  ~ {key}: only {len(rows)} of these exist in the database - skipping")
                skipped += 1
                continue

            survivor = pick_survivor(rows, decisions.get(key))
            losers = [r for r in rows if r.id != survivor.id]
            code = next(e["code"] for e in group if e["part_number"] == survivor.part_number)

            print(f"\n  {key}")
            print(f"    keep {survivor.part_number:<8} {survivor.quantity or 0:>4} units  {survivor.name[:44]}")
            for loser in losers:
                print(f"    fold {loser.part_number:<8} {loser.quantity or 0:>4} units  {loser.name[:44]}")

            if APPLY:
                result = merge(survivor, losers, code)
                print(f"    -> {survivor.part_number} now holds {survivor.quantity} units, "
                      f"{result['moved_tx']} transactions and {result['moved_parts']} "
                      f"repair-order lines moved")
            merged += 1

        if waiting:
            print(f"\nWAITING ON YOU ({len(waiting)}) - the names differ, so only you can say "
                  "whether\nthese are one part or two:")
            for key in waiting:
                print(f"\n  {key}")
                for entry in groups[key]:
                    row = rows_by_part.get(entry["part_number"])
                    stock = f"{row.quantity or 0} units" if row else "not in database"
                    print(f"    {entry['part_number']:<8} {stock:<14} {entry['name'][:52]}")
            print(f"\n  Run --write-decisions to get an editable list of these.")

        if APPLY:
            db.session.commit()
            print(f"\nDone. {merged} code(s) merged"
                  f"{f', {skipped} skipped' if skipped else ''}.")
            print("Re-run import_cleaned_inventory.py to write the codes that are now free.")
        else:
            print(f"\nDry run - nothing written. {merged} code(s) would be merged.")
            print("Re-run with --apply to commit.")


if __name__ == "__main__":
    main()
