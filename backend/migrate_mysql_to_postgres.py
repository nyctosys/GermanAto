#!/usr/bin/env python3
"""Copy every row from the MySQL database into PostgreSQL.

    # 1. empty Postgres schema
    DATABASE_URL=postgresql://user:pass@host/germanato_db alembic upgrade head
    # 2. copy (stop the app first so nothing writes mid-copy)
    SOURCE_DATABASE_URL=mysql+pymysql://user:pass@host/germanato_db \\
    DATABASE_URL=postgresql://user:pass@host/germanato_db \\
        python migrate_mysql_to_postgres.py

Runs in one transaction: either every table is copied or nothing is. The
target must be empty. Columns are matched by name; a column that exists on
only one side is reported and skipped (the target's default applies), so run
`alembic check` against MySQL first to see any drift.
"""
import os
import sys

from sqlalchemy import create_engine, inspect, select, text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import database_url  # noqa: E402
from models import db  # noqa: E402

BATCH = 1000


def copy(source_url, target_url):
    source = create_engine(source_url)
    target = create_engine(target_url)
    source_tables = set(inspect(source).get_table_names())
    counts = []

    with source.connect() as src, target.begin() as dst:
        for table in db.metadata.sorted_tables:  # parents before children, so FKs hold
            if dst.execute(select(table).limit(1)).first():
                sys.exit(f"Target table {table.name} is not empty; refusing to copy.")
            if table.name not in source_tables:
                print(f"  {table.name}: not in source, left empty")
                counts.append((table.name, 0, 0))
                continue

            source_cols = {c["name"] for c in inspect(source).get_columns(table.name)}
            cols = [c for c in table.columns if c.name in source_cols]
            extra = source_cols - {c.name for c in table.columns}
            missing = [c.name for c in table.columns if c.name not in source_cols]
            if extra:
                print(f"  {table.name}: source-only columns not copied: {sorted(extra)}")
            if missing:
                print(f"  {table.name}: columns missing in source, using defaults: {missing}")

            # Selecting through the model's column types converts MySQL's
            # tinyint(1) to real booleans on the way out.
            result = src.execution_options(stream_results=True).execute(select(*cols))
            copied = 0
            while rows := result.fetchmany(BATCH):
                try:
                    dst.execute(table.insert(), [dict(r._mapping) for r in rows])
                except Exception as e:
                    sys.exit(f"Copy failed in {table.name} near row {copied}: {e}\nNothing was written.")
                copied += len(rows)
            source_count = src.execute(text(f"SELECT COUNT(*) FROM `{table.name}`")).scalar()
            counts.append((table.name, source_count, copied))

            # Copied rows keep their ids, so move the id sequence past them or
            # the next insert collides with row 1.
            if "id" in table.columns and table.c.id.autoincrement:
                dst.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('\"{table.name}\"', 'id'), "
                    f"COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM \"{table.name}\""))

        bad = [(n, s, c) for n, s, c in counts if s != c]
        if bad:  # exiting inside begin() rolls the whole copy back
            sys.exit(f"Row counts differ, rolled back: {bad}")

    width = max(len(n) for n, _, _ in counts)
    for name, _, copied in counts:
        print(f"  {name:<{width}}  {copied:>8}")
    print(f"Copied {sum(c for _, _, c in counts)} rows across {len(counts)} tables.")


if __name__ == "__main__":
    src_url, dst_url = os.getenv("SOURCE_DATABASE_URL"), database_url()
    if not src_url or not src_url.startswith("mysql"):
        sys.exit("Set SOURCE_DATABASE_URL to the MySQL database (mysql+pymysql://...).")
    if not dst_url or not dst_url.startswith("postgresql"):
        sys.exit("Set DATABASE_URL to the PostgreSQL database.")
    copy(src_url, dst_url)
