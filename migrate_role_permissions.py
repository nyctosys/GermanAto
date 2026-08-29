#!/usr/bin/env python3
"""
Production migration – create the `role_permissions` table and seed default rows.

Usage (from the project's virtual‑env):
    $ python migrate_role_permissions.py   # creates table + seeds data
    $ python migrate_role_permissions.py --downgrade   # drops the table

The script expects a `DATABASE_URL` environment variable
(e.g. mysql://user:pwd@host:3306/germanato) – the same format Flask‑SQLAlchemy
uses in the app configuration.
"""

import os
import sys
import argparse
from pathlib import Path

from sqlalchemy import (
    create_engine,
    Table,
    Column,
    Integer,
    String,
    UniqueConstraint,
    MetaData,
    inspect,
    text,
)
from sqlalchemy.exc import OperationalError, ProgrammingError

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def get_engine() -> "Engine":
    """Create a SQLAlchemy engine from the DATABASE_URL env variable."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        sys.stderr.write(
            "❌  DATABASE_URL environment variable is not set.\n"
            "    Export it before running this script, e.g.\n"
            "    export DATABASE_URL='mysql://user:pwd@host:3306/germanato'\n"
        )
        sys.exit(1)

    # echo=False silences the SQL logs – remove or set to True for debugging
    return create_engine(db_url, echo=False)


def table_exists(engine, table_name: str) -> bool:
    """Return True if the given table already exists in the DB."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def create_role_permissions_table(metadata: MetaData) -> Table:
    """Define the role_permissions table schema."""
    return Table(
        "role_permissions",
        metadata,
        Column("id", Integer, primary_key=True, autoincrement=True),
        Column("role", String(64), nullable=False),
        Column("permission", String(64), nullable=False),
        UniqueConstraint("role", "permission", name="uq_role_permission"),
    )


def seed_default_permissions(conn):
    """Insert the default permission matrix (idempotent)."""
    default_matrix = [
        # Accountant
        {"role": "accountant", "permission": "invoice"},
        {"role": "accountant", "permission": "vendors"},
        {"role": "accountant", "permission": "daily-expenses"},
        {"role": "accountant", "permission": "hr"},
        # Inventory Manager
        {"role": "inventory_manager", "permission": "inventory"},
        {"role": "inventory_manager", "permission": "vendors"},
        {"role": "inventory_manager", "permission": "daily-expenses"},
        {"role": "inventory_manager", "permission": "hr"},
    ]

    # Use INSERT IGNORE / ON CONFLICT to avoid duplicate rows
    # MySQL: INSERT IGNORE
    # PostgreSQL: ON CONFLICT DO NOTHING
    # We'll detect the dialect and adjust accordingly.
    dialect = conn.engine.dialect.name

    if dialect == "postgresql":
        insert_stmt = text(
            """
            INSERT INTO role_permissions (role, permission)
            VALUES (:role, :permission)
            ON CONFLICT (role, permission) DO NOTHING
            """
        )
    else:  # MySQL, MariaDB, SQLite fallback
        insert_stmt = text(
            """
            INSERT IGNORE INTO role_permissions (role, permission)
            VALUES (:role, :permission)
            """
        )

    for row in default_matrix:
        conn.execute(insert_stmt, **row)


def upgrade(engine):
    """Create the table (if missing) and seed data."""
    metadata = MetaData()
    role_perm_tbl = create_role_permissions_table(metadata)

    if table_exists(engine, "role_permissions"):
        print("✅  Table `role_permissions` already exists – skipping creation.")
    else:
        print("📦  Creating table `role_permissions` …")
        metadata.create_all(engine, tables=[role_perm_tbl])
        print("✅  Table created.")

    # Seed the default rows – the INSERT statements are idempotent.
    with engine.begin() as conn:
        print("🔧  Seeding default role‑permission mappings …")
        seed_default_permissions(conn)
        print("✅  Seed data inserted (duplicates ignored).")


def downgrade(engine):
    """Drop the role_permissions table."""
    if not table_exists(engine, "role_permissions"):
        print("ℹ️  Table `role_permissions` does not exist – nothing to drop.")
        return

    print("⚠️  Dropping table `role_permissions` …")
    meta = MetaData()
    role_perm_tbl = Table("role_permissions", meta, autoload_with=engine)
    role_perm_tbl.drop(engine)
    print("✅  Table dropped.")


# ----------------------------------------------------------------------
# Main entry point
# ----------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Production migration – role_permissions table."
    )
    parser.add_argument(
        "--downgrade",
        action="store_true",
        help="Drop the role_permissions table instead of creating it",
    )
    args = parser.parse_args()

    # Ensure we are running inside the project's venv (optional safety check)
    venv_path = os.getenv("VIRTUAL_ENV")
    if not venv_path:
        sys.stderr.write(
            "⚠️  No virtual‑env detected (VIRTUAL_ENV is empty). "
            "Make sure you run this script from the same venv that the app uses.\n"
        )

    engine = get_engine()

    try:
        if args.downgrade:
            downgrade(engine)
        else:
            upgrade(engine)
    except (OperationalError, ProgrammingError) as exc:
        sys.stderr.write(f"❌  Database error: {exc}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
