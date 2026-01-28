"""
One-time Migration Script
Migrates existing departments from Worker table and categories from Inventory table
to the central Department and Category tables in Settings.

Run this script once on production to populate the settings tables with existing data.

Usage:
    python migrate_departments_categories.py
"""

import sys
import os

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, Department, Category, Worker, Inventory

def migrate_departments():
    """Migrate unique departments from Worker table to Department table"""
    print("\n=== Migrating Departments ===")
    
    # Get all unique department names from Worker table
    existing_departments = db.session.query(Worker.department).filter(
        Worker.department.isnot(None),
        Worker.department != ''
    ).distinct().all()
    
    migrated_count = 0
    skipped_count = 0
    
    for (dept_name,) in existing_departments:
        if dept_name and dept_name.strip():
            dept_name = dept_name.strip()
            # Check if department already exists in Department table
            existing = Department.query.filter_by(name=dept_name).first()
            if not existing:
                new_dept = Department(
                    name=dept_name,
                    description=f"Migrated from existing HR data",
                    is_active=True
                )
                db.session.add(new_dept)
                migrated_count += 1
                print(f"  ✓ Added department: {dept_name}")
            else:
                skipped_count += 1
                print(f"  - Skipped (already exists): {dept_name}")
    
    db.session.commit()
    print(f"\nDepartments: {migrated_count} added, {skipped_count} skipped (already existed)")
    return migrated_count

def migrate_categories():
    """Migrate unique categories from Inventory table to Category table"""
    print("\n=== Migrating Categories ===")
    
    # Get all unique category names from Inventory table
    existing_categories = db.session.query(Inventory.category).filter(
        Inventory.category.isnot(None),
        Inventory.category != ''
    ).distinct().all()
    
    migrated_count = 0
    skipped_count = 0
    
    for (cat_name,) in existing_categories:
        if cat_name and cat_name.strip():
            cat_name = cat_name.strip()
            # Check if category already exists in Category table
            existing = Category.query.filter_by(name=cat_name).first()
            if not existing:
                new_cat = Category(
                    name=cat_name,
                    description=f"Migrated from existing inventory data",
                    is_active=True
                )
                db.session.add(new_cat)
                migrated_count += 1
                print(f"  ✓ Added category: {cat_name}")
            else:
                skipped_count += 1
                print(f"  - Skipped (already exists): {cat_name}")
    
    db.session.commit()
    print(f"\nCategories: {migrated_count} added, {skipped_count} skipped (already existed)")
    return migrated_count

def main():
    print("=" * 50)
    print("Department & Category Migration Script")
    print("=" * 50)
    print("\nThis script will migrate existing departments and categories")
    print("from HR Management and Inventory to the central Settings tables.")
    print("\nThis is safe to run multiple times - it won't create duplicates.")
    
    with app.app_context():
        # Migrate departments
        dept_count = migrate_departments()
        
        # Migrate categories
        cat_count = migrate_categories()
        
        print("\n" + "=" * 50)
        print("Migration Complete!")
        print("=" * 50)
        print(f"\nTotal new departments added: {dept_count}")
        print(f"Total new categories added: {cat_count}")
        print("\nYou can now manage these in Settings → Manage Departments/Categories")

if __name__ == "__main__":
    main()
