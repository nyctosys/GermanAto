#!/usr/bin/env python3
"""
Database Cleanup Script for GermanATO Auto Trader
Deletes all inventory items, duplicate customers, duplicate cars, and all repair orders
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def delete_all_inventory():
    """Delete all inventory items"""
    from models import db, Inventory
    
    try:
        count = Inventory.query.count()
        if count == 0:
            print("✅ No inventory items to delete")
            return 0
        
        Inventory.query.delete()
        db.session.commit()
        print(f"✅ Deleted {count} inventory item(s)")
        return count
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error deleting inventory items: {e}")
        return 0

def delete_duplicate_customers():
    """Delete duplicate customers (keeping one of each duplicate set)"""
    from models import db, Customer
    
    try:
        # Get all customers
        all_customers = Customer.query.all()
        
        # Group customers by their key fields (name, phone, address)
        # Handle NULL values properly
        customer_groups = {}
        
        for customer in all_customers:
            # Create a key tuple, using None for NULL values
            key = (
                customer.name if customer.name else None,
                customer.phone if customer.phone else None,
                customer.address if customer.address else None
            )
            
            if key not in customer_groups:
                customer_groups[key] = []
            customer_groups[key].append(customer)
        
        total_deleted = 0
        
        # Find and delete duplicates
        for key, customers in customer_groups.items():
            if len(customers) > 1:
                # Sort by ID and keep the first one (lowest ID)
                customers.sort(key=lambda c: c.id)
                keep_customer = customers[0]
                to_delete = customers[1:]
                
                for customer in to_delete:
                    db.session.delete(customer)
                    total_deleted += 1
                
                name = key[0] or 'N/A'
                phone = key[1] or 'N/A'
                print(f"  Found {len(customers)} duplicate(s) for customer '{name}' ({phone}) - keeping ID {keep_customer.id}, deleting {len(to_delete)}")
        
        if total_deleted > 0:
            db.session.commit()
            print(f"✅ Deleted {total_deleted} duplicate customer(s)")
        else:
            print("✅ No duplicate customers found")
        
        return total_deleted
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error deleting duplicate customers: {e}")
        return 0

def delete_duplicate_cars():
    """Delete duplicate cars (keeping one of each duplicate set)"""
    from models import db, Car
    
    try:
        # Get all cars
        all_cars = Car.query.all()
        
        # Group cars by their key fields (all fields except id, created_at, updated_at)
        # Handle NULL values properly
        car_groups = {}
        
        for car in all_cars:
            # Create a key tuple, using None for NULL values
            key = (
                car.make if car.make else None,
                car.model if car.model else None,
                car.plate_no if car.plate_no else None,
                car.mileage if car.mileage else None,
                car.vin if car.vin else None,
                car.color if car.color else None,
                car.chasis_no if car.chasis_no else None,
                car.customer_id if car.customer_id else None
            )
            
            if key not in car_groups:
                car_groups[key] = []
            car_groups[key].append(car)
        
        total_deleted = 0
        
        # Find and delete duplicates
        for key, cars in car_groups.items():
            if len(cars) > 1:
                # Sort by ID and keep the first one (lowest ID)
                cars.sort(key=lambda c: c.id)
                keep_car = cars[0]
                to_delete = cars[1:]
                
                for car in to_delete:
                    db.session.delete(car)
                    total_deleted += 1
                
                make = key[0] or 'N/A'
                model = key[1] or 'N/A'
                plate_no = key[2] or 'N/A'
                car_desc = f"{make} {model}" if make != 'N/A' and model != 'N/A' else f"Car (Plate: {plate_no})"
                print(f"  Found {len(cars)} duplicate(s) for {car_desc} - keeping ID {keep_car.id}, deleting {len(to_delete)}")
        
        if total_deleted > 0:
            db.session.commit()
            print(f"✅ Deleted {total_deleted} duplicate car(s)")
        else:
            print("✅ No duplicate cars found")
        
        return total_deleted
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error deleting duplicate cars: {e}")
        return 0

def delete_all_repair_orders():
    """Delete all repair orders"""
    from models import db, RepairOrder
    
    try:
        count = RepairOrder.query.count()
        if count == 0:
            print("✅ No repair orders to delete")
            return 0
        
        # RepairOrderPart and RepairOrderLabour will be deleted automatically due to cascade
        RepairOrder.query.delete()
        db.session.commit()
        print(f"✅ Deleted {count} repair order(s)")
        return count
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error deleting repair orders: {e}")
        return 0

def main():
    """Main cleanup function"""
    print("🧹 Database Cleanup Script for GermanATO")
    print("=" * 50)
    print()
    print("⚠️  WARNING: This script will:")
    print("   - Delete ALL inventory items")
    print("   - Delete duplicate customers (keeping one of each)")
    print("   - Delete duplicate cars (keeping one of each)")
    print("   - Delete ALL repair orders")
    print()
    
    # Ask for confirmation
    response = input("Are you sure you want to proceed? (yes/no): ").strip().lower()
    if response != 'yes':
        print("❌ Operation cancelled")
        return False
    
    try:
        # Import after environment is loaded
        from models import db
        from app import app
        
        with app.app_context():
            print()
            print("Starting cleanup...")
            print("-" * 50)
            
            # 1. Delete all inventory items
            print("\n1. Deleting all inventory items...")
            inventory_deleted = delete_all_inventory()
            
            # 2. Delete duplicate customers
            print("\n2. Finding and deleting duplicate customers...")
            customers_deleted = delete_duplicate_customers()
            
            # 3. Delete duplicate cars
            print("\n3. Finding and deleting duplicate cars...")
            cars_deleted = delete_duplicate_cars()
            
            # 4. Delete all repair orders
            print("\n4. Deleting all repair orders...")
            repair_orders_deleted = delete_all_repair_orders()
            
            print()
            print("=" * 50)
            print("✅ Cleanup completed successfully!")
            print()
            print("Summary:")
            print(f"  - Inventory items deleted: {inventory_deleted}")
            print(f"  - Duplicate customers deleted: {customers_deleted}")
            print(f"  - Duplicate cars deleted: {cars_deleted}")
            print(f"  - Repair orders deleted: {repair_orders_deleted}")
            print()
            
            return True
            
    except Exception as e:
        print(f"\n❌ Error during cleanup: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

