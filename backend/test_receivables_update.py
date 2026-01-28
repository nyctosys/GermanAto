#!/usr/bin/env python3
"""
Test script to verify receivables update when invoice balances change
"""
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Invoice
from reports_routes import get_receivables

def test_receivables_update():
    """Test that receivables update when paid_amount changes"""
    print("=" * 80)
    print("RECEIVABLES UPDATE VERIFICATION")
    print("=" * 80)
    
    with app.app_context():
        # Get initial receivables
        initial_receivables = get_receivables()
        print(f"\n1. Initial Receivables: PKR {initial_receivables:,.2f}")
        
        # Find an invoice with outstanding balance
        invoice = db.session.query(Invoice).filter(
            Invoice.type_of == 'invoice',
            Invoice.net_total > db.func.coalesce(Invoice.paid_amount, 0)
        ).first()
        
        if not invoice:
            print("\n⚠️  No invoices with outstanding balance found. Cannot test.")
            return
        
        print(f"\n2. Found test invoice:")
        print(f"   Invoice ID: {invoice.id}")
        print(f"   Net Total: PKR {invoice.net_total:,.2f}")
        print(f"   Paid Amount: PKR {invoice.paid_amount or 0:,.2f}")
        print(f"   Current Receivable: PKR {(invoice.net_total - (invoice.paid_amount or 0)):,.2f}")
        
        # Calculate receivable before update
        receivable_before = invoice.net_total - (invoice.paid_amount or 0)
        
        # Update paid_amount (add a small amount)
        test_payment = min(100.0, receivable_before * 0.1)  # Pay 10% or 100 PKR, whichever is smaller
        old_paid_amount = invoice.paid_amount or 0
        new_paid_amount = old_paid_amount + test_payment
        
        print(f"\n3. Updating invoice balance:")
        print(f"   Adding payment: PKR {test_payment:,.2f}")
        print(f"   Old paid_amount: PKR {old_paid_amount:,.2f}")
        print(f"   New paid_amount: PKR {new_paid_amount:,.2f}")
        
        invoice.paid_amount = new_paid_amount
        db.session.commit()
        
        # Get receivables after update
        updated_receivables = get_receivables()
        print(f"\n4. Updated Receivables: PKR {updated_receivables:,.2f}")
        
        # Calculate expected receivables
        expected_receivables = initial_receivables - test_payment
        difference = abs(updated_receivables - expected_receivables)
        
        print(f"\n5. Verification:")
        print(f"   Expected Receivables: PKR {expected_receivables:,.2f}")
        print(f"   Actual Receivables: PKR {updated_receivables:,.2f}")
        print(f"   Difference: PKR {difference:,.2f}")
        
        if difference < 0.01:
            print(f"\n✅ SUCCESS! Receivables updated correctly!")
            print(f"   Receivables decreased by PKR {test_payment:,.2f} as expected.")
        else:
            print(f"\n❌ FAILURE! Receivables did not update correctly!")
            print(f"   Expected decrease: PKR {test_payment:,.2f}")
            print(f"   Actual decrease: PKR {(initial_receivables - updated_receivables):,.2f}")
        
        # Restore original paid_amount
        print(f"\n6. Restoring original balance...")
        invoice.paid_amount = old_paid_amount
        db.session.commit()
        
        restored_receivables = get_receivables()
        restore_diff = abs(restored_receivables - initial_receivables)
        
        print(f"   Restored Receivables: PKR {restored_receivables:,.2f}")
        print(f"   Difference from initial: PKR {restore_diff:,.2f}")
        
        if restore_diff < 0.01:
            print(f"   ✅ Successfully restored!")
        else:
            print(f"   ⚠️  Warning: Restored value differs from initial")
        
        print("\n" + "=" * 80)
        
        return difference < 0.01

if __name__ == '__main__':
    success = test_receivables_update()
    sys.exit(0 if success else 1)
