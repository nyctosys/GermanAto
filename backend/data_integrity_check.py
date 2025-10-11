#!/usr/bin/env python3
"""
Data Integrity Check Script
===========================

This script performs ongoing data integrity checks to ensure
the reliability and accuracy of the Reports & Analytics system.

Usage:
    python data_integrity_check.py

Checks:
- Data consistency across tables
- Referential integrity
- Data validation rules
- Anomaly detection
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db
from datetime import datetime, date

def check_referential_integrity():
    """Check referential integrity between tables"""
    print("🔗 REFERENTIAL INTEGRITY CHECK")
    print("=" * 40)
    
    issues = []
    
    # Check invoice items reference valid invoices
    orphaned_items = db.session.execute(db.text("""
        SELECT COUNT(*) FROM invoice_item ii 
        LEFT JOIN invoice i ON ii.invoice_id = i.id 
        WHERE i.id IS NULL
    """)).fetchone()[0]
    
    if orphaned_items > 0:
        issues.append(f"❌ {orphaned_items} orphaned invoice items")
    else:
        print("✅ Invoice items integrity: OK")
    
    # Check repair order parts reference valid repair orders
    orphaned_parts = db.session.execute(db.text("""
        SELECT COUNT(*) FROM repair_order_part rop 
        LEFT JOIN repair_order ro ON rop.repair_order_id = ro.id 
        WHERE ro.id IS NULL
    """)).fetchone()[0]
    
    if orphaned_parts > 0:
        issues.append(f"❌ {orphaned_parts} orphaned repair order parts")
    else:
        print("✅ Repair order parts integrity: OK")
    
    # Check cars reference valid customers
    orphaned_cars = db.session.execute(db.text("""
        SELECT COUNT(*) FROM car c 
        LEFT JOIN customer cu ON c.customer_id = cu.id 
        WHERE c.customer_id IS NOT NULL AND cu.id IS NULL
    """)).fetchone()[0]
    
    if orphaned_cars > 0:
        issues.append(f"❌ {orphaned_cars} orphaned cars")
    else:
        print("✅ Cars integrity: OK")
    
    return issues

def check_data_consistency():
    """Check data consistency rules"""
    print("\n📊 DATA CONSISTENCY CHECK")
    print("=" * 40)
    
    issues = []
    
    # Check for negative quantities in inventory
    negative_quantities = db.session.execute(db.text("""
        SELECT COUNT(*) FROM inventory WHERE quantity < 0
    """)).fetchone()[0]
    
    if negative_quantities > 0:
        issues.append(f"❌ {negative_quantities} items with negative quantities")
    else:
        print("✅ Inventory quantities: OK")
    
    # Check for negative amounts in invoices
    negative_amounts = db.session.execute(db.text("""
        SELECT COUNT(*) FROM invoice WHERE net_total < 0
    """)).fetchone()[0]
    
    if negative_amounts > 0:
        issues.append(f"❌ {negative_amounts} invoices with negative amounts")
    else:
        print("✅ Invoice amounts: OK")
    
    # Check for future dates
    future_dates = db.session.execute(db.text("""
        SELECT COUNT(*) FROM invoice WHERE created_at > NOW()
    """)).fetchone()[0]
    
    if future_dates > 0:
        issues.append(f"❌ {future_dates} invoices with future dates")
    else:
        print("✅ Invoice dates: OK")
    
    # Check for missing required fields
    missing_customer_names = db.session.execute(db.text("""
        SELECT COUNT(*) FROM invoice WHERE customer_name IS NULL OR customer_name = ''
    """)).fetchone()[0]
    
    if missing_customer_names > 0:
        issues.append(f"❌ {missing_customer_names} invoices with missing customer names")
    else:
        print("✅ Customer names: OK")
    
    return issues

def check_business_rules():
    """Check business logic rules"""
    print("\n💼 BUSINESS RULES CHECK")
    print("=" * 40)
    
    issues = []
    
    # Check for duplicate part numbers
    duplicate_parts = db.session.execute(db.text("""
        SELECT part_number, COUNT(*) as count 
        FROM inventory 
        GROUP BY part_number 
        HAVING count > 1
    """)).fetchall()
    
    if duplicate_parts:
        issues.append(f"❌ {len(duplicate_parts)} duplicate part numbers found")
        for part in duplicate_parts:
            issues.append(f"   - {part[0]}: {part[1]} occurrences")
    else:
        print("✅ Part numbers uniqueness: OK")
    
    # Check for duplicate VINs
    duplicate_vins = db.session.execute(db.text("""
        SELECT vin, COUNT(*) as count 
        FROM car 
        WHERE vin IS NOT NULL AND vin != ''
        GROUP BY vin 
        HAVING count > 1
    """)).fetchall()
    
    if duplicate_vins:
        issues.append(f"❌ {len(duplicate_vins)} duplicate VINs found")
    else:
        print("✅ VIN uniqueness: OK")
    
    # Check for invalid status values
    invalid_statuses = db.session.execute(db.text("""
        SELECT current_status, COUNT(*) as count 
        FROM repair_order 
        WHERE current_status NOT IN ('received', 'diagnosis', 'in_progress', 'waiting_parts', 'completed', 'cancelled', 'complete')
        GROUP BY current_status
    """)).fetchall()
    
    if invalid_statuses:
        issues.append(f"❌ {len(invalid_statuses)} invalid repair order statuses")
        for status in invalid_statuses:
            issues.append(f"   - {status[0]}: {status[1]} occurrences")
    else:
        print("✅ Repair order statuses: OK")
    
    return issues

def check_data_anomalies():
    """Check for data anomalies"""
    print("\n🔍 ANOMALY DETECTION")
    print("=" * 40)
    
    issues = []
    
    # Check for unusually high invoice amounts
    high_invoices = db.session.execute(db.text("""
        SELECT id, customer_name, net_total 
        FROM invoice 
        WHERE net_total > 100000
        ORDER BY net_total DESC
        LIMIT 5
    """)).fetchall()
    
    if high_invoices:
        print(f"⚠️  {len(high_invoices)} invoices over 100,000 PKR:")
        for invoice in high_invoices:
            print(f"   - Invoice {invoice[0]}: {invoice[2]:,.2f} PKR ({invoice[1]})")
    
    # Check for zero-amount invoices
    zero_invoices = db.session.execute(db.text("""
        SELECT COUNT(*) FROM invoice WHERE net_total = 0
    """)).fetchone()[0]
    
    if zero_invoices > 0:
        issues.append(f"⚠️  {zero_invoices} invoices with zero amount")
    else:
        print("✅ Zero-amount invoices: None found")
    
    # Check for very old pending quotes
    old_quotes = db.session.execute(db.text("""
        SELECT COUNT(*) FROM invoice 
        WHERE type_of = 'quote' AND status = 'pending' 
        AND created_at < DATE_SUB(NOW(), INTERVAL 30 DAY)
    """)).fetchone()[0]
    
    if old_quotes > 0:
        issues.append(f"⚠️  {old_quotes} quotes pending for over 30 days")
    else:
        print("✅ Old pending quotes: None found")
    
    return issues

def check_performance_metrics():
    """Check system performance metrics"""
    print("\n⚡ PERFORMANCE METRICS")
    print("=" * 40)
    
    # Count records in major tables
    table_counts = {}
    tables = ['customer', 'car', 'invoice', 'inventory', 'repair_order', 'expense', 'vendor']
    
    for table in tables:
        try:
            count = db.session.execute(db.text(f"SELECT COUNT(*) FROM {table}")).fetchone()[0]
            table_counts[table] = count
            print(f"✅ {table}: {count:,} records")
        except Exception as e:
            print(f"❌ {table}: Error - {str(e)}")
    
    # Check for large tables that might need optimization
    large_tables = {k: v for k, v in table_counts.items() if v > 10000}
    if large_tables:
        print(f"\n⚠️  Large tables (>10K records): {large_tables}")
    
    return table_counts

def generate_integrity_report():
    """Generate comprehensive integrity report"""
    print("🔍 DATA INTEGRITY CHECK REPORT")
    print("=" * 50)
    print(f"Check Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    all_issues = []
    
    try:
        with app.app_context():
            # Run all checks
            all_issues.extend(check_referential_integrity())
            all_issues.extend(check_data_consistency())
            all_issues.extend(check_business_rules())
            all_issues.extend(check_data_anomalies())
            performance_data = check_performance_metrics()
            
            # Summary
            print("\n📋 INTEGRITY SUMMARY")
            print("=" * 30)
            
            if all_issues:
                print(f"❌ {len(all_issues)} issues found:")
                for issue in all_issues:
                    print(f"   {issue}")
                print("\n⚠️  Please review and fix these issues for optimal data integrity.")
            else:
                print("✅ All integrity checks passed!")
                print("✅ Data is consistent and reliable.")
            
            print(f"\n📊 Database Statistics:")
            for table, count in performance_data.items():
                print(f"   {table}: {count:,} records")
            
    except Exception as e:
        print(f"\n❌ INTEGRITY CHECK FAILED: {str(e)}")
        return False
    
    return len(all_issues) == 0

if __name__ == "__main__":
    success = generate_integrity_report()
    sys.exit(0 if success else 1)
