#!/usr/bin/env python3
"""Add barcode lookup fields to the inventory table."""

from sqlalchemy import inspect, text

from app import app
from models import db


def add_column(connection, dialect, table_columns, name, definition):
    if name in table_columns:
        print(f"Column {name} already exists")
        return

    connection.execute(text(f"ALTER TABLE inventory ADD COLUMN {name} {definition}"))
    print(f"Added column {name}")


def add_index(connection, dialect, existing_indexes, name, column):
    if name in existing_indexes:
        print(f"Index {name} already exists")
        return

    unique = "UNIQUE " if name.startswith("uq_") else ""
    connection.execute(text(f"CREATE {unique}INDEX {name} ON inventory ({column})"))
    print(f"Added index {name}")


def main():
    with app.app_context():
        inspector = inspect(db.engine)
        columns = {column["name"] for column in inspector.get_columns("inventory")}
        indexes = {index["name"] for index in inspector.get_indexes("inventory")}
        dialect = db.engine.dialect.name

        with db.engine.begin() as connection:
            add_column(connection, dialect, columns, "barcode", "VARCHAR(100) NULL")
            add_column(
                connection,
                dialect,
                columns,
                "manufacturer_part_number",
                "VARCHAR(100) NULL",
            )

            inspector = inspect(connection)
            indexes = {index["name"] for index in inspector.get_indexes("inventory")}
            add_index(connection, dialect, indexes, "uq_inventory_barcode", "barcode")
            add_index(
                connection,
                dialect,
                indexes,
                "uq_inventory_manufacturer_part_number",
                "manufacturer_part_number",
            )

        print("Inventory barcode migration complete")


if __name__ == "__main__":
    main()
