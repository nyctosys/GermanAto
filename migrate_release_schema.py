#!/usr/bin/env python3
"""Bring an existing database up to the current app schema.

Safe to run more than once. This handles columns that Flask-SQLAlchemy
create_all() will not add to existing tables.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import Boolean, Date, DateTime, Float, Integer, Numeric, String, Text, inspect, text
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / "backend" / ".env", override=False)
load_dotenv(ROOT / ".env", override=False)
sys.path.insert(0, str(ROOT / "backend"))

from app import app
from models import db


DEFAULT_ROLE_PERMISSIONS = {
    "accountant": [
        "home",
        "invoice",
        "search",
        "car",
        "daily-expenses",
        "vendors",
        "vendor-detail",
        "hr",
        "worker-detail",
        "repair-order",
        "repair-orders-management",
        "settings",
    ],
    "inventory_manager": [
        "home",
        "inventory",
        "repair-order",
        "repair-orders-management",
        "settings",
    ],
}

MISSING_COLUMNS = {
    "inventory": {
        "barcode": "VARCHAR(100) NULL",
        "manufacturer_part_number": "VARCHAR(100) NULL",
    },
    "purchase_orders": {
        "status": "VARCHAR(50) NOT NULL DEFAULT 'ordered'",
        "created_by_user": "VARCHAR(80) NULL",
        "updated_at": "DATETIME NULL",
    },
    "invoice": {
        "created_by_user": "VARCHAR(80) NULL",
        "updated_by_user": "VARCHAR(80) NULL",
        "updated_at": "DATETIME NULL",
        "payments_history": "TEXT NULL",
    },
    "repair_order": {
        "created_by_user": "VARCHAR(80) NULL",
        "updated_by_user": "VARCHAR(80) NULL",
        "workers_json": "TEXT NULL",
    },
    "vendor_ledger": {
        "created_by_user": "VARCHAR(80) NULL",
        "payment_notes": "TEXT NULL",
        "attachment_path": "VARCHAR(255) NULL",
    },
    "attendance_records": {
        "source": "VARCHAR(50) NULL",
        "zkteco_device_id": "INT NULL",
    },
    "zkteco_devices": {
        "serial_number": "VARCHAR(64) NULL",
        "last_seen_at": "DATETIME NULL",
    },
    "role_permissions": {
        "role": "VARCHAR(50) NOT NULL",
        "permission": "VARCHAR(100) NOT NULL",
    },
}

TYPE_DEFINITIONS = {
    Boolean: "BOOLEAN",
    Date: "DATE",
    DateTime: "DATETIME",
    Float: "FLOAT",
    Integer: "INT",
    Text: "TEXT",
}

UNIQUE_INDEXES = {
    "inventory": {
        "uq_inventory_barcode": "barcode",
        "uq_inventory_manufacturer_part_number": "manufacturer_part_number",
    }
}


def table_names(connection):
    return set(inspect(connection).get_table_names())


def column_names(connection, table):
    return {column["name"] for column in inspect(connection).get_columns(table)}


def index_names(connection, table):
    return {index["name"] for index in inspect(connection).get_indexes(table)}


def has_duplicate_values(connection, table, column):
    duplicate = connection.execute(text(f"""
        SELECT {column}
        FROM {table}
        WHERE {column} IS NOT NULL AND {column} != ''
        GROUP BY {column}
        HAVING COUNT(*) > 1
        LIMIT 1
    """)).first()
    return duplicate is not None


def add_missing_columns(connection):
    tables = table_names(connection)
    for table, columns in MISSING_COLUMNS.items():
        if table not in tables:
            continue

        existing = column_names(connection, table)
        for column, definition in columns.items():
            if column in existing:
                print(f"Column {table}.{column} already exists")
                continue

            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
            print(f"Added column {table}.{column}")


def column_definition(column):
    for type_class, definition in TYPE_DEFINITIONS.items():
        if isinstance(column.type, type_class):
            return definition

    if isinstance(column.type, String):
        return f"VARCHAR({column.type.length or 255})"

    if isinstance(column.type, Numeric):
        precision = column.type.precision or 10
        scale = column.type.scale or 2
        return f"NUMERIC({precision}, {scale})"

    return None


def add_model_columns(connection):
    tables = table_names(connection)
    for table in sorted(db.metadata.tables.values(), key=lambda item: item.name):
        if table.name not in tables:
            continue

        existing = column_names(connection, table.name)
        for column in table.columns:
            if column.primary_key or column.name in existing:
                continue

            definition = column_definition(column)
            if not definition:
                print(f"Skipped {table.name}.{column.name}; unsupported column type {column.type}")
                continue

            connection.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {column.name} {definition} NULL"))
            print(f"Added model column {table.name}.{column.name}")


def add_missing_indexes(connection):
    tables = table_names(connection)
    for table, indexes in UNIQUE_INDEXES.items():
        if table not in tables:
            continue

        existing = index_names(connection, table)
        for index, columns in indexes.items():
            if index in existing:
                print(f"Index {index} already exists")
                continue
            if has_duplicate_values(connection, table, columns):
                print(f"Skipped index {index}; duplicate {table}.{columns} values exist")
                continue

            connection.execute(text(f"CREATE UNIQUE INDEX {index} ON {table} ({columns})"))
            print(f"Added index {index}")


def seed_role_permissions(connection):
    if "role_permissions" not in table_names(connection):
        return
    existing_columns = column_names(connection, "role_permissions")
    if not {"role", "permission"}.issubset(existing_columns):
        print("Skipping role permission seed; role_permissions table is missing required columns")
        return

    exists = text(
        """
        SELECT 1 FROM role_permissions
        WHERE role = :role AND permission = :permission
        LIMIT 1
        """
    )
    insert = text(
        """
        INSERT INTO role_permissions (role, permission)
        VALUES (:role, :permission)
        """
    )
    for role, permissions in DEFAULT_ROLE_PERMISSIONS.items():
        for permission in permissions:
            params = {"role": role, "permission": permission}
            if connection.execute(exists, params).first() is None:
                connection.execute(insert, params)

    print("Role permissions seeded")


def run():
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is not set. Check backend/.env or export DATABASE_URL.")

    with app.app_context():
        print(f"Database dialect: {db.engine.dialect.name}")
        db.create_all()

        with db.engine.begin() as connection:
            add_missing_columns(connection)
            add_model_columns(connection)
            add_missing_indexes(connection)
            seed_role_permissions(connection)

    print("Release schema migration complete")


if __name__ == "__main__":
    try:
        run()
    except SQLAlchemyError as exc:
        print(f"Database migration failed: {exc}", file=sys.stderr)
        sys.exit(1)
