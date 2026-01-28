#!/usr/bin/env python3
"""
Comprehensive verification script: Query ALL data from DB, calculate manually, and verify against reports API
"""
import sys
import os
from datetime import datetime, date, timedelta
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Invoice, Expense
from sqlalchemy import func

def get_all_invoices():
    """Get all invoices from database"""
    invoices = db.session.query(Invoice).order_by(Invoice.created_at).all()
    
    invoice_data = []
    for inv in invoices:
        invoice_data.append({
            'id': inv.id,
            'created_at': inv.created_at.date() if inv.created_at else None,
            'net_total': float(inv.net_total) if inv.net_total else 0.0,
            'paid_amount': float(inv.paid_amount) if inv.paid_amount else 0.0,
            'type_of': inv.type_of,
            'status': inv.status
        })
    
    return invoice_data

def get_all_expenses():
    """Get all expenses from database"""
    expenses = db.session.query(Expense).order_by(Expense.date).all()
    
    expense_data = []
    for exp in expenses:
        expense_data.append({
            'id': exp.id,
            'date': exp.date,
            'amount': float(exp.amount) if exp.amount else 0.0,
            'category': exp.category,
            'description': exp.description
        })
    
    return expense_data

def calculate_manual_receivables(invoices):
    """Manually calculate receivables from all invoices"""
    # Receivables = sum of (net_total - paid_amount) for invoices where net_total > paid_amount
    # Note: Receivables should only include invoices, not quotes
    receivables_total = 0.0
    receivables_details = []
    
    for inv in invoices:
        # Only count invoices, not quotes
        if inv['type_of'] != 'invoice':
            continue
            
        net_total = inv.get('net_total', 0.0)
        paid_amount = inv.get('paid_amount', 0.0)
        
        # Calculate receivable amount
        receivable = net_total - paid_amount
        
        # Only include if there's an outstanding balance
        if receivable > 0:
            receivables_total += receivable
            receivables_details.append({
                'id': inv['id'],
                'net_total': net_total,
                'paid_amount': paid_amount,
                'receivable': receivable
            })
    
    return receivables_total, receivables_details

def calculate_manual_totals(invoices, expenses, start_date, end_date):
    """Manually calculate totals for a date range"""
    # Filter invoices in date range (only invoices, not quotes)
    filtered_invoices = [
        inv for inv in invoices
        if inv['created_at'] and 
           start_date <= inv['created_at'] <= end_date and
           inv['type_of'] == 'invoice'  # Only count invoices, not quotes
    ]
    
    # Filter expenses in date range
    filtered_expenses = [
        exp for exp in expenses
        if start_date <= exp['date'] <= end_date
    ]
    
    # Calculate totals
    sales_total = sum(inv['net_total'] for inv in filtered_invoices)
    expenses_total = sum(exp['amount'] for exp in filtered_expenses)
    profit_total = sales_total - expenses_total
    
    # Daily breakdown
    sales_daily = {}
    for inv in filtered_invoices:
        date_str = str(inv['created_at'])
        if date_str not in sales_daily:
            sales_daily[date_str] = 0
        sales_daily[date_str] += inv['net_total']
    
    expenses_daily = {}
    for exp in filtered_expenses:
        date_str = str(exp['date'])
        if date_str not in expenses_daily:
            expenses_daily[date_str] = 0
        expenses_daily[date_str] += exp['amount']
    
    result = {
        'sales_total': sales_total,
        'expenses_total': expenses_total,
        'profit_total': profit_total,
        'sales_count': len(filtered_invoices),
        'expenses_count': len(filtered_expenses),
        'sales_daily': sales_daily,
        'expenses_daily': expenses_daily,
        'invoice_details': filtered_invoices,
        'expense_details': filtered_expenses
    }
    
    return result

def test_reports_api(start_date, end_date, period='month'):
    """Test the reports API and return results"""
    # Use the helper functions directly
    from reports_routes import get_sales_data, get_expenses_data, calculate_profit, get_receivables
    
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    sales_data = get_sales_data(start_datetime, end_datetime)
    expenses_data = get_expenses_data(start_datetime, end_datetime)
    profit_data = calculate_profit(sales_data, expenses_data)
    receivables = get_receivables()
    
    result = {
        'sales': sales_data,
        'expenses': expenses_data,
        'profit': profit_data,
        'receivables': receivables
    }
    
    return result

def compare_results(manual, api, date_range_name):
    """Compare manual calculations with API results"""
    sales_diff = abs(manual['sales_total'] - api['sales'].get('total', 0))
    expenses_diff = abs(manual['expenses_total'] - api['expenses'].get('total', 0))
    profit_diff = abs(manual['profit_total'] - api['profit'].get('total', 0))
    
    sales_match = sales_diff < 0.01
    expenses_match = expenses_diff < 0.01
    profit_match = profit_diff < 0.01
    
    result = {
        'date_range': date_range_name,
        'manual': manual,
        'api': {
            'sales_total': api['sales'].get('total', 0),
            'expenses_total': api['expenses'].get('total', 0),
            'profit_total': api['profit'].get('total', 0)
        },
        'differences': {
            'sales': sales_diff,
            'expenses': expenses_diff,
            'profit': profit_diff
        },
        'matches': {
            'sales': sales_match,
            'expenses': expenses_match,
            'profit': profit_match
        },
        'all_match': sales_match and expenses_match and profit_match
    }
    
    return result

def main():
    """Main verification function"""
    with app.app_context():
        print("=" * 80)
        print("COMPREHENSIVE REPORTS VERIFICATION")
        print("=" * 80)
        
        # Get all data
        print("\n1. Fetching all data from database...")
        all_invoices = get_all_invoices()
        all_expenses = get_all_expenses()
        
        print(f"   Found {len(all_invoices)} invoices")
        print(f"   Found {len(all_expenses)} expenses")
        
        if len(all_invoices) == 0 and len(all_expenses) == 0:
            print("\n⚠️  No data found in database. Cannot verify.")
            return
        
        # Get date ranges
        today = date.today()
        date_ranges = [
            ('Today', today, today, 'day'),
            ('Last 7 Days', today - timedelta(days=6), today, 'week'),
            ('Last 30 Days', today - timedelta(days=29), today, 'month'),
            ('This Month', today.replace(day=1), today, 'month'),
            ('This Year', today.replace(month=1, day=1), today, 'year'),
        ]
        
        # Add custom ranges if we have data
        if all_invoices:
            first_invoice_date = min(inv['created_at'] for inv in all_invoices if inv['created_at'])
            if first_invoice_date:
                date_ranges.append(('All Time', first_invoice_date, today, 'year'))
        
        print(f"\n2. Testing {len(date_ranges)} date ranges...")
        print("=" * 80)
        
        # Verify receivables separately (receivables are not date-filtered)
        print("\n💰 RECEIVABLES VERIFICATION")
        print("=" * 80)
        manual_receivables, receivables_details = calculate_manual_receivables(all_invoices)
        from reports_routes import get_receivables
        api_receivables = get_receivables()
        
        receivables_diff = abs(manual_receivables - api_receivables)
        receivables_match = receivables_diff < 0.01
        
        print(f"Manual Calculation:")
        print(f"  Receivables: PKR {manual_receivables:,.2f} ({len(receivables_details)} invoices with outstanding balance)")
        print(f"\nAPI Results:")
        print(f"  Receivables: PKR {api_receivables:,.2f}")
        print(f"\nDifference: PKR {receivables_diff:,.2f} {'✅' if receivables_match else '❌'}")
        
        if receivables_match:
            print(f"\n✅ Receivables match!")
        else:
            print(f"\n❌ RECEIVABLES MISMATCH DETECTED!")
            print(f"\n  Sample invoices with receivables:")
            for inv in receivables_details[:10]:
                print(f"    Invoice #{inv['id']}: Net={inv['net_total']:,.2f}, Paid={inv['paid_amount']:,.2f}, Receivable={inv['receivable']:,.2f}")
        
        print("\n" + "=" * 80)
        print("DATE RANGE VERIFICATIONS")
        print("=" * 80)
        
        all_results = []
        for range_name, start_date, end_date, period in date_ranges:
            print(f"\n📅 Testing: {range_name} ({start_date} to {end_date})")
            print("-" * 80)
            
            # Calculate manually
            manual = calculate_manual_totals(all_invoices, all_expenses, start_date, end_date)
            
            # Get API results
            api = test_reports_api(start_date, end_date, period)
            
            # Compare
            comparison = compare_results(manual, api, range_name)
            all_results.append(comparison)
            
            # Print results
            print(f"Manual Calculation:")
            print(f"  Sales:    PKR {manual['sales_total']:,.2f} ({manual['sales_count']} invoices)")
            print(f"  Expenses: PKR {manual['expenses_total']:,.2f} ({manual['expenses_count']} expenses)")
            print(f"  Profit:   PKR {manual['profit_total']:,.2f}")
            
            print(f"\nAPI Results:")
            print(f"  Sales:    PKR {api['sales'].get('total', 0):,.2f}")
            print(f"  Expenses: PKR {api['expenses'].get('total', 0):,.2f}")
            print(f"  Profit:   PKR {api['profit'].get('total', 0):,.2f}")
            
            print(f"\nDifferences:")
            print(f"  Sales:    PKR {comparison['differences']['sales']:,.2f} {'✅' if comparison['matches']['sales'] else '❌'}")
            print(f"  Expenses: PKR {comparison['differences']['expenses']:,.2f} {'✅' if comparison['matches']['expenses'] else '❌'}")
            print(f"  Profit:   PKR {comparison['differences']['profit']:,.2f} {'✅' if comparison['matches']['profit'] else '❌'}")
            
            if comparison['all_match']:
                print(f"\n✅ All values match!")
            else:
                print(f"\n❌ MISMATCH DETECTED!")
                
                # Show details if mismatch
                if not comparison['matches']['sales']:
                    print(f"\n  Sales Mismatch Details:")
                    print(f"    Manual invoices in range: {manual['sales_count']}")
                    print(f"    API daily count: {len(api['sales'].get('daily', []))}")
                    if manual['invoice_details']:
                        print(f"    Sample manual invoices:")
                        for inv in manual['invoice_details'][:5]:
                            print(f"      Invoice #{inv['id']}: {inv['created_at']} - PKR {inv['net_total']:,.2f}")
        
        # Summary
        print("\n" + "=" * 80)
        print("VERIFICATION SUMMARY")
        print("=" * 80)
        
        matches = sum(1 for r in all_results if r['all_match'])
        total = len(all_results)
        
        print(f"\nDate Ranges Tested: {total}")
        print(f"Fully Matching: {matches}")
        print(f"With Mismatches: {total - matches}")
        
        if matches == total:
            print("\n✅ ALL VERIFICATIONS PASSED!")
        else:
            print("\n❌ SOME VERIFICATIONS FAILED!")
            print("\nFailed ranges:")
            for r in all_results:
                if not r['all_match']:
                    print(f"  - {r['date_range']}: Sales diff={r['differences']['sales']:.2f}, "
                          f"Expenses diff={r['differences']['expenses']:.2f}, "
                          f"Profit diff={r['differences']['profit']:.2f}")
        
        print("\n" + "=" * 80)
        print("=" * 80)

if __name__ == '__main__':
    main()
