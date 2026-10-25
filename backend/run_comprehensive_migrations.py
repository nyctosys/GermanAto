#!/usr/bin/env python3
"""Run comprehensive database migrations to add columns and new tables."""

import os
import sys
from sqlalchemy import inspect, text
import json

# Add current folder to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db


def table_exists(inspector, name):
    return name in inspector.get_table_names()


def column_exists(inspector, table_name, column_name):
    try:
        columns = [c["name"] for c in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def run_migrations():
    with app.app_context():
        inspector = inspect(db.engine)
        dialect = db.engine.dialect.name
        print(f"Database dialect: {dialect}")

        with db.engine.begin() as connection:
            # 1. Rename vendor_consignments to purchase_orders if needed
            if table_exists(inspector, "vendor_consignments") and not table_exists(inspector, "purchase_orders"):
                print("Renaming vendor_consignments table to purchase_orders...")
                connection.execute(text("RENAME TABLE vendor_consignments TO purchase_orders"))
                print("Table renamed successfully")
                # Re-inspect to update cached tables
                inspector = inspect(connection)
            
            # 2. Handle purchase_orders table status field and other fields
            target_po_table = "purchase_orders" if (table_exists(inspector, "purchase_orders") or not table_exists(inspector, "vendor_consignments")) else "vendor_consignments"
            
            if table_exists(inspector, target_po_table):
                print(f"Checking columns in {target_po_table}...")
                if not column_exists(inspector, target_po_table, "status"):
                    connection.execute(text(f"ALTER TABLE {target_po_table} ADD COLUMN status VARCHAR(50) NOT NULL DEFAULT 'ordered'"))
                    print("Added status column to purchase orders")
                if not column_exists(inspector, target_po_table, "created_by_user"):
                    connection.execute(text(f"ALTER TABLE {target_po_table} ADD COLUMN created_by_user VARCHAR(80) NULL"))
                    print("Added created_by_user column to purchase orders")
                if not column_exists(inspector, target_po_table, "updated_at"):
                    connection.execute(text(f"ALTER TABLE {target_po_table} ADD COLUMN updated_at DATETIME NULL"))
                    print("Added updated_at column to purchase orders")

            # 3. Create app_logs table if not exists
            if not table_exists(inspector, "app_logs"):
                print("Creating app_logs table...")
                connection.execute(text("""
                    CREATE TABLE app_logs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id INT NULL,
                        username VARCHAR(80) NULL,
                        action VARCHAR(100) NOT NULL,
                        module VARCHAR(50) NOT NULL,
                        reference_id INT NULL,
                        details TEXT NOT NULL,
                        ip_address VARCHAR(45) NULL,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
                """))
                print("Created app_logs table successfully")
            else:
                print("app_logs table already exists")

            # 4. Alter invoice table
            if table_exists(inspector, "invoice"):
                print("Checking columns in invoice...")
                if not column_exists(inspector, "invoice", "created_by_user"):
                    connection.execute(text("ALTER TABLE invoice ADD COLUMN created_by_user VARCHAR(80) NULL"))
                    print("Added created_by_user column to invoice")
                if not column_exists(inspector, "invoice", "updated_by_user"):
                    connection.execute(text("ALTER TABLE invoice ADD COLUMN updated_by_user VARCHAR(80) NULL"))
                    print("Added updated_by_user column to invoice")
                if not column_exists(inspector, "invoice", "updated_at"):
                    connection.execute(text("ALTER TABLE invoice ADD COLUMN updated_at DATETIME NULL"))
                    print("Added updated_at column to invoice")
                if not column_exists(inspector, "invoice", "payments_history"):
                    connection.execute(text("ALTER TABLE invoice ADD COLUMN payments_history TEXT NULL"))
                    print("Added payments_history column to invoice")

            # 5. Alter repair_order table
            if table_exists(inspector, "repair_order"):
                print("Checking columns in repair_order...")
                if not column_exists(inspector, "repair_order", "created_by_user"):
                    connection.execute(text("ALTER TABLE repair_order ADD COLUMN created_by_user VARCHAR(80) NULL"))
                    print("Added created_by_user column to repair_order")
                if not column_exists(inspector, "repair_order", "updated_by_user"):
                    connection.execute(text("ALTER TABLE repair_order ADD COLUMN updated_by_user VARCHAR(80) NULL"))
                    print("Added updated_by_user column to repair_order")
                if not column_exists(inspector, "repair_order", "workers_json"):
                    connection.execute(text("ALTER TABLE repair_order ADD COLUMN workers_json TEXT NULL"))
                    print("Added workers_json column to repair_order")

            # 6. Alter vendor_ledger table
            if table_exists(inspector, "vendor_ledger"):
                print("Checking columns in vendor_ledger...")
                if not column_exists(inspector, "vendor_ledger", "created_by_user"):
                    connection.execute(text("ALTER TABLE vendor_ledger ADD COLUMN created_by_user VARCHAR(80) NULL"))
                    print("Added created_by_user column to vendor_ledger")
                if not column_exists(inspector, "vendor_ledger", "payment_notes"):
                    connection.execute(text("ALTER TABLE vendor_ledger ADD COLUMN payment_notes TEXT NULL"))
                    print("Added payment_notes column to vendor_ledger")
                if not column_exists(inspector, "vendor_ledger", "attachment_path"):
                    connection.execute(text("ALTER TABLE vendor_ledger ADD COLUMN attachment_path VARCHAR(255) NULL"))
                    print("Added attachment_path column to vendor_ledger")
            # 7. Create role_permissions table
            if not table_exists(inspector, "role_permissions"):
                print("Creating role_permissions table...")
                connection.execute(text("""
                    CREATE TABLE role_permissions (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        role VARCHAR(50) NOT NULL,
                        permission VARCHAR(100) NOT NULL,
                        UNIQUE KEY unique_role_permission (role, permission)
                    )
                """))
                print("role_permissions table created.")
                
                # Pre-populate default role permissions
                default_permissions = [
                    # Accountant
                    ('accountant', 'home'),
                    ('accountant', 'invoice'),
                    ('accountant', 'search'),
                    ('accountant', 'car'),
                    ('accountant', 'daily-expenses'),
                    ('accountant', 'vendors'),
                    ('accountant', 'vendor-detail'),
                    ('accountant', 'hr'),
                    ('accountant', 'worker-detail'),
                    ('accountant', 'repair-order'),
                    ('accountant', 'repair-orders-management'),
                    ('accountant', 'settings'),
                    
                    # Inventory Manager
                    ('inventory_manager', 'home'),
                    ('inventory_manager', 'inventory'),
                    ('inventory_manager', 'repair-order'),
                    ('inventory_manager', 'repair-orders-management'),
                    ('inventory_manager', 'settings')
                ]
                print("Pre-populating default role permissions...")
                for role, perm in default_permissions:
                    connection.execute(text("INSERT INTO role_permissions (role, permission) VALUES (:role, :perm)"), {"role": role, "perm": perm})
                print("Default role permissions pre-populated.")

        print("All database migrations run successfully!")


if __name__ == "__main__":
    run_migrations()
