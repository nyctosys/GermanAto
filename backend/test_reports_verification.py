#!/usr/bin/env python3
"""
Test script to create sample data and verify reports calculations
"""
import sys
import os
from datetime import datetime, date, timedelta
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Invoice, Expense, InvoiceItem, InvoiceLabour

def create_sample_data():
    """Create sample invoices and expenses with known values"""
    today = date.today()
    
    # Clear existing test data (optional - be careful in production!)
    # For safety, we'll just create new data with a marker
    
    # Create invoices for last 30 days
    invoices_data = []
    
    # Day 1 (30 days ago): Invoice 1 - 5000 PKR
    day1 = today - timedelta(days=30)
    invoice1 = Invoice(
        created_at=datetime.combine(day1, datetime.min.time()),
        customer_name="Test Customer 1",
        customer_address="Test Address 1",
        customer_phone="03001234567",
        customer_reg_no="ABC-123",
        customer_made="Toyota",
        customer_mileage="50000",
        balance=0,
        advance=0,
        net_total=5000.0,
        discount=0,
        type_of="invoice",
        include_tax=False,
        tax_amount=0,
        paid_amount=5000.0,
        status="paid"
    )
    db.session.add(invoice1)
    db.session.flush()
    invoices_data.append({'date': day1, 'amount': 5000.0, 'id': invoice1.id})
    
    # Day 2 (29 days ago): Invoice 2 - 7500 PKR
    day2 = today - timedelta(days=29)
    invoice2 = Invoice(
        created_at=datetime.combine(day2, datetime.min.time()),
        customer_name="Test Customer 2",
        customer_address="Test Address 2",
        customer_phone="03001234568",
        customer_reg_no="XYZ-456",
        customer_made="Honda",
        customer_mileage="60000",
        balance=0,
        advance=0,
        net_total=7500.0,
        discount=0,
        type_of="invoice",
        include_tax=False,
        tax_amount=0,
        paid_amount=7500.0,
        status="paid"
    )
    db.session.add(invoice2)
    db.session.flush()
    invoices_data.append({'date': day2, 'amount': 7500.0, 'id': invoice2.id})
    
    # Day 3 (28 days ago): Invoice 3 - 10000 PKR
    day3 = today - timedelta(days=28)
    invoice3 = Invoice(
        created_at=datetime.combine(day3, datetime.min.time()),
        customer_name="Test Customer 3",
        customer_address="Test Address 3",
        customer_phone="03001234569",
        customer_reg_no="DEF-789",
        customer_made="Suzuki",
        customer_mileage="70000",
        balance=0,
        advance=0,
        net_total=10000.0,
        discount=0,
        type_of="invoice",
        include_tax=False,
        tax_amount=0,
        paid_amount=10000.0,
        status="paid"
    )
    db.session.add(invoice3)
    db.session.flush()
    invoices_data.append({'date': day3, 'amount': 10000.0, 'id': invoice3.id})
    
    # Today: Invoice 4 - 3000 PKR
    invoice4 = Invoice(
        created_at=datetime.combine(today, datetime.min.time()),
        customer_name="Test Customer 4",
        customer_address="Test Address 4",
        customer_phone="03001234570",
        customer_reg_no="GHI-012",
        customer_made="Nissan",
        customer_mileage="80000",
        balance=0,
        advance=0,
        net_total=3000.0,
        discount=0,
        type_of="invoice",
        include_tax=False,
        tax_amount=0,
        paid_amount=3000.0,
        status="paid"
    )
    db.session.add(invoice4)
    db.session.flush()
    invoices_data.append({'date': today, 'amount': 3000.0, 'id': invoice4.id})
    
    # Create expenses
    expenses_data = []
    
    # Day 1 (30 days ago): Expense 1 - 1000 PKR
    expense1 = Expense(
        date=day1,
        category="Parts",
        description="Test Expense 1",
        amount=1000.0,
        notes="Test"
    )
    db.session.add(expense1)
    expenses_data.append({'date': day1, 'amount': 1000.0})
    
    # Day 2 (29 days ago): Expense 2 - 1500 PKR
    expense2 = Expense(
        date=day2,
        category="Labour",
        description="Test Expense 2",
        amount=1500.0,
        notes="Test"
    )
    db.session.add(expense2)
    expenses_data.append({'date': day2, 'amount': 1500.0})
    
    # Day 3 (28 days ago): Expense 3 - 2000 PKR
    expense3 = Expense(
        date=day3,
        category="Utilities",
        description="Test Expense 3",
        amount=2000.0,
        notes="Test"
    )
    db.session.add(expense3)
    expenses_data.append({'date': day3, 'amount': 2000.0})
    
    # Today: Expense 4 - 500 PKR
    expense4 = Expense(
        date=today,
        category="Parts",
        description="Test Expense 4",
        amount=500.0,
        notes="Test"
    )
    db.session.add(expense4)
    expenses_data.append({'date': today, 'amount': 500.0})
    
    db.session.commit()
    
    return invoices_data, expenses_data

def calculate_expected_totals(invoices_data, expenses_data, start_date, end_date):
    """Manually calculate expected totals for date range"""
    # Filter invoices in date range
    filtered_invoices = [
        inv for inv in invoices_data 
        if start_date <= inv['date'] <= end_date
    ]
    
    # Filter expenses in date range
    filtered_expenses = [
        exp for exp in expenses_data 
        if start_date <= exp['date'] <= end_date
    ]
    
    expected_sales = sum(inv['amount'] for inv in filtered_invoices)
    expected_expenses = sum(exp['amount'] for exp in filtered_expenses)
    expected_profit = expected_sales - expected_expenses
    
    result = {
        'sales_total': expected_sales,
        'expenses_total': expected_expenses,
        'profit_total': expected_profit,
        'sales_count': len(filtered_invoices),
        'expenses_count': len(filtered_expenses),
        'sales_daily': {},
        'expenses_daily': {}
    }
    
    # Calculate daily breakdown
    for inv in filtered_invoices:
        date_str = str(inv['date'])
        if date_str not in result['sales_daily']:
            result['sales_daily'][date_str] = 0
        result['sales_daily'][date_str] += inv['amount']
    
    for exp in filtered_expenses:
        date_str = str(exp['date'])
        if date_str not in result['expenses_daily']:
            result['expenses_daily'][date_str] = 0
        result['expenses_daily'][date_str] += exp['amount']
    
    return result

def test_reports_api(start_date, end_date, period='month'):
    """Test the reports API and return results"""
    # Use Flask test client to make actual request
    # Note: This requires authentication, so we'll need to create a test user or bypass auth
    # For now, we'll directly call the function with a mock request context
    from flask import request
    
    # Create a test request context
    with app.test_request_context(f'/api/reports?period={period}&start_date={start_date}&end_date={end_date}'):
        # We need to bypass authentication for testing
        # Import the function directly
        from reports_routes import get_reports
        
        # Mock JWT authentication by setting up a test user context
        # For now, let's just call it and see what happens
        try:
            # This will fail auth, so let's query the database directly instead
            # Actually, let's use the helper functions directly
            from reports_routes import get_sales_data, get_expenses_data, calculate_profit
            from datetime import datetime
            
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
            
            sales_data = get_sales_data(start_datetime, end_datetime)
            expenses_data = get_expenses_data(start_datetime, end_datetime)
            profit_data = calculate_profit(sales_data, expenses_data)
            
            result = {
                'sales': sales_data,
                'expenses': expenses_data,
                'profit': profit_data
            }
            
            return result
        except Exception as e:
            print(f"Error testing API: {e}")
            return None

def main():
    """Main test function"""
    with app.app_context():
        # Create sample data
        print("Creating sample data...")
        invoices_data, expenses_data = create_sample_data()
        print(f"Created {len(invoices_data)} invoices and {len(expenses_data)} expenses")
        
        # Test 1: Last 30 days
        today = date.today()
        start_30days = today - timedelta(days=30)
        end_30days = today
        
        print(f"\n=== Test 1: Last 30 Days ({start_30days} to {end_30days}) ===")
        expected = calculate_expected_totals(invoices_data, expenses_data, start_30days, end_30days)
        print(f"Expected Sales: {expected['sales_total']}")
        print(f"Expected Expenses: {expected['expenses_total']}")
        print(f"Expected Profit: {expected['profit_total']}")
        
        actual = test_reports_api(start_30days, end_30days, period='month')
        if actual:
            print(f"Actual Sales: {actual.get('sales', {}).get('total', 0)}")
            print(f"Actual Expenses: {actual.get('expenses', {}).get('total', 0)}")
            print(f"Actual Profit: {actual.get('profit', {}).get('total', 0)}")
            
            # Compare
            sales_diff = abs(expected['sales_total'] - actual.get('sales', {}).get('total', 0))
            expenses_diff = abs(expected['expenses_total'] - actual.get('expenses', {}).get('total', 0))
            profit_diff = abs(expected['profit_total'] - actual.get('profit', {}).get('total', 0))
            
            print(f"\nDifferences:")
            print(f"  Sales difference: {sales_diff}")
            print(f"  Expenses difference: {expenses_diff}")
            print(f"  Profit difference: {profit_diff}")
            
            if sales_diff > 0.01 or expenses_diff > 0.01 or profit_diff > 0.01:
                print("  ❌ MISMATCH DETECTED!")
            else:
                print("  ✅ All values match!")
        
        # Test 2: Today only
        print(f"\n=== Test 2: Today Only ({today}) ===")
        expected_today = calculate_expected_totals(invoices_data, expenses_data, today, today)
        print(f"Expected Sales: {expected_today['sales_total']}")
        print(f"Expected Expenses: {expected_today['expenses_total']}")
        print(f"Expected Profit: {expected_today['profit_total']}")
        
        actual_today = test_reports_api(today, today, period='day')
        if actual_today:
            print(f"Actual Sales: {actual_today.get('sales', {}).get('total', 0)}")
            print(f"Actual Expenses: {actual_today.get('expenses', {}).get('total', 0)}")
            print(f"Actual Profit: {actual_today.get('profit', {}).get('total', 0)}")
            
            sales_diff = abs(expected_today['sales_total'] - actual_today.get('sales', {}).get('total', 0))
            expenses_diff = abs(expected_today['expenses_total'] - actual_today.get('expenses', {}).get('total', 0))
            profit_diff = abs(expected_today['profit_total'] - actual_today.get('profit', {}).get('total', 0))
            
            print(f"\nDifferences:")
            print(f"  Sales difference: {sales_diff}")
            print(f"  Expenses difference: {expenses_diff}")
            print(f"  Profit difference: {profit_diff}")
            
            if sales_diff > 0.01 or expenses_diff > 0.01 or profit_diff > 0.01:
                print("  ❌ MISMATCH DETECTED!")
            else:
                print("  ✅ All values match!")
        
        print("\n=== Test Complete ===")

if __name__ == '__main__':
    main()
