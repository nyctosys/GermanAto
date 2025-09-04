from flask import Blueprint, jsonify, session
from models import db, Invoice, Inventory, Car, Customer, InvoiceItem, Expense, User
from sqlalchemy import extract, func
import datetime

reports_bp = Blueprint('reports', __name__)

# Role required decorator for reports
def admin_required(f):
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        
        user = User.query.get(session['user_id'])
        if not user or not user.is_active:
            return jsonify({'error': 'User not found or inactive'}), 401
        
        if user.role != 'admin':
            return jsonify({'error': 'Admin access required for reports'}), 403
        
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@reports_bp.route('/reports/summary', methods=['GET'])
@admin_required
def reports_summary():
    total_invoices = Invoice.query.count()
    total_inventory_value = db.session.query(db.func.sum(Inventory.quantity * Inventory.price)).scalar() or 0
    total_cars = Car.query.count()
    total_customers = Customer.query.count()
    
    # Calculate total revenue from invoices
    try:
        total_invoice_revenue_result = db.session.query(
            func.sum(Invoice.net_total)
        ).filter(
            Invoice.type_of == 'invoice',
            Invoice.status.in_(['paid', 'unpaid'])
        ).scalar()
        
        if total_invoice_revenue_result is None:
            total_invoice_revenue = 0
        else:
            total_invoice_revenue = float(total_invoice_revenue_result)
            
        print(f"Debug - Total invoice revenue: {total_invoice_revenue}")
        
    except Exception as e:
        print(f"Error calculating total invoice revenue: {e}")
        total_invoice_revenue = 0
    
    # Calculate total expenses with better error handling
    try:
        # First check if there are any expenses at all
        expense_count = Expense.query.count()
        print(f"Debug - Total expense records: {expense_count}")
        
        if expense_count == 0:
            total_expenses = 0
            print("Debug - No expenses found in database")
        else:
            # Get all expenses and sum them manually to avoid SQL aggregation issues
            expenses = Expense.query.all()
            total_expenses = 0
            
            for expense in expenses:
                try:
                    if expense.amount is not None:
                        amount = float(expense.amount)
                        if not (amount != amount):  # Check for NaN
                            total_expenses += amount
                        else:
                            print(f"Debug - Found NaN amount in expense ID {expense.id}")
                except (ValueError, TypeError) as e:
                    print(f"Debug - Invalid amount in expense ID {expense.id}: {expense.amount}, Error: {e}")
                    continue
            
            print(f"Debug - Total expenses calculated manually: {total_expenses}")
        
    except Exception as e:
        print(f"Error calculating total expenses: {e}")
        total_expenses = 0
    
    # Calculate net revenue (invoices - expenses)
    try:
        total_revenue = total_invoice_revenue - total_expenses
        print(f"Debug - Net revenue calculation: {total_invoice_revenue} - {total_expenses} = {total_revenue}")
    except Exception as e:
        print(f"Error calculating net revenue: {e}")
        total_revenue = 0
    
    # Ensure all values are valid numbers
    try:
        final_revenue = float(total_revenue) if total_revenue is not None and not (total_revenue != total_revenue) else 0
        final_expenses = float(total_expenses) if total_expenses is not None and not (total_expenses != total_expenses) else 0
    except (ValueError, TypeError):
        final_revenue = 0
        final_expenses = 0
    
    return jsonify({
        'total_invoices': total_invoices,
        'total_revenue': final_revenue,
        'total_expenses': final_expenses,
        'total_inventory_value': total_inventory_value,
        'total_cars': total_cars,
        'total_customers': total_customers
    })

@reports_bp.route('/reports/invoices_per_month', methods=['GET'])
@admin_required
def invoices_per_month():
    now = datetime.datetime.now()
    months = [(now - datetime.timedelta(days=30*i)).replace(day=1) for i in range(11, -1, -1)]
    months = [m.strftime('%Y-%m') for m in months]
    # Use date_format for MySQL
    results = db.session.query(
        func.date_format(Invoice.created_at, '%Y-%m').label('month'),
        func.count(Invoice.id)
    ).group_by('month').all()
    month_counts = {m: 0 for m in months}
    for month, count in results:
        if month in month_counts:
            month_counts[month] = count
    labels = [datetime.datetime.strptime(m, '%Y-%m').strftime('%b %Y') for m in months]
    data = [month_counts[m] for m in months]
    return jsonify({'labels': labels, 'data': data})

@reports_bp.route('/reports/inventory_by_category', methods=['GET'])
@admin_required
def inventory_by_category():
    results = db.session.query(
        Inventory.category,
        func.sum(Inventory.quantity * Inventory.price)
    ).group_by(Inventory.category).all()
    labels = [r[0] for r in results]
    data = [float(r[1] or 0) for r in results]
    return jsonify({'labels': labels, 'data': data})

@reports_bp.route('/reports/top_products', methods=['GET'])
@admin_required
def top_products():
    results = db.session.query(
        InvoiceItem.product_name,
        func.sum(InvoiceItem.quantity).label('total_sold')
    ).group_by(InvoiceItem.product_name)
    results = results.order_by(func.sum(InvoiceItem.quantity).desc()).limit(10).all()
    labels = [r[0] for r in results]
    data = [int(r[1]) for r in results]
    return jsonify({'labels': labels, 'data': data})

@reports_bp.route('/reports/customer_growth', methods=['GET'])
@admin_required
def customer_growth():
    now = datetime.datetime.now()
    months = [(now - datetime.timedelta(days=30*i)).replace(day=1) for i in range(11, -1, -1)]
    months = [m.strftime('%Y-%m') for m in months]
    results = db.session.query(
        func.date_format(Customer.created_at, '%Y-%m').label('month'),
        func.count(Customer.id)
    ).group_by('month').all()
    month_counts = {m: 0 for m in months}
    for month, count in results:
        if month in month_counts:
            month_counts[month] = count
    labels = [datetime.datetime.strptime(m, '%Y-%m').strftime('%b %Y') for m in months]
    data = [month_counts[m] for m in months]
    return jsonify({'labels': labels, 'data': data})

@reports_bp.route('/reports/revenue_per_month', methods=['GET'])
@admin_required
def revenue_per_month():
    now = datetime.datetime.now()
    months = [(now - datetime.timedelta(days=30*i)).replace(day=1) for i in range(11, -1, -1)]
    months = [m.strftime('%Y-%m') for m in months]
    
    # Calculate revenue from invoices (only invoices, not quotes)
    invoice_results = db.session.query(
        func.date_format(Invoice.created_at, '%Y-%m').label('month'),
        func.sum(Invoice.net_total)
    ).filter(
        Invoice.type_of == 'invoice',
        Invoice.status.in_(['paid', 'unpaid'])  # Include both paid and unpaid invoices
    ).group_by('month').all()
    
    # Calculate expenses per month
    expense_results = db.session.query(
        func.date_format(Expense.date, '%Y-%m').label('month'),
        func.sum(Expense.amount)
    ).group_by('month').all()
    
    # Initialize month data
    month_revenue = {m: 0 for m in months}
    month_expenses = {m: 0 for m in months}
    
    # Populate invoice revenue
    for month, revenue in invoice_results:
        if month in month_revenue:
            month_revenue[month] = float(revenue or 0)
    
    # Populate expenses
    for month, expense in expense_results:
        if month in month_expenses:
            month_expenses[month] = float(expense or 0)
    
    # Calculate net revenue (revenue - expenses) for each month
    net_revenue = {}
    for month in months:
        net_revenue[month] = month_revenue[month] - month_expenses[month]
    
    labels = [datetime.datetime.strptime(m, '%Y-%m').strftime('%b %Y') for m in months]
    data = [net_revenue[m] for m in months]
    
    return jsonify({'labels': labels, 'data': data})

@reports_bp.route('/reports/debug/expenses', methods=['GET'])
@admin_required
def debug_expenses():
    """Debug endpoint to check expenses data"""
    try:
        # Get total count of expenses
        total_expense_count = Expense.query.count()
        
        # Get all expenses with their amounts
        expenses = db.session.query(Expense.id, Expense.amount, Expense.date, Expense.description).all()
        
        # Calculate sum manually
        total_amount = sum(expense.amount for expense in expenses) if expenses else 0
        
        return jsonify({
            'total_expense_count': total_expense_count,
            'total_amount': total_amount,
            'expenses': [
                {
                    'id': exp.id,
                    'amount': exp.amount,
                    'date': exp.date.isoformat() if exp.date else None,
                    'description': exp.description
                } for exp in expenses
            ]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500 