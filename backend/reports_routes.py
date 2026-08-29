from flask import Blueprint, request, jsonify
from models import db, Invoice, Expense, Customer, Inventory, RepairOrder, Vendor
from datetime import datetime, date, timedelta
import logging
from jwt_auth import login_required, role_required

# Create blueprint for reports routes
reports_bp = Blueprint('reports', __name__)

# Set up logging
logger = logging.getLogger(__name__)

# ===== REPORTS ROUTES =====

@reports_bp.route('/reports', methods=['GET'])
@login_required
@role_required(['admin', 'accountant'])
def get_reports():
    """Get comprehensive business reports and analytics"""
    try:
        # Get date filter parameters
        period = request.args.get('period', 'month')  # day, week, month, year
        start_date_param = request.args.get('start_date')
        end_date_param = request.args.get('end_date')
        
        # Set date range: use custom dates if provided, otherwise use period-based calculation
        today = date.today()
        
        # If custom dates are provided, use them (convert from string if needed)
        # Check for both None and empty strings
        if start_date_param and end_date_param and start_date_param.strip() and end_date_param.strip():
            try:
                start_date = datetime.strptime(start_date_param.strip(), '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_param.strip(), '%Y-%m-%d').date()
            except (ValueError, TypeError) as e:
                # If parsing fails, fall back to period-based calculation
                logger.warning(f"Failed to parse custom dates: {e}")
                start_date = None
                end_date = None
        else:
            start_date = None
            end_date = None
        
        # Only use period-based calculation if custom dates were not provided
        if start_date is None or end_date is None:
            if period == 'day':
                start_date = today
                end_date = today
            elif period == 'week':
                # Get last 7 days
                start_date = today - timedelta(days=6)
                end_date = today
            elif period == 'month':
                start_date = today.replace(day=1)
                end_date = today
            elif period == 'year':
                start_date = today.replace(month=1, day=1)
                end_date = today
            else:
                # Default to month if period is invalid
                start_date = today.replace(day=1)
                end_date = today
        
        # Convert to datetime for database queries
        try:
            start_datetime = datetime.combine(start_date, datetime.min.time())
            end_datetime = datetime.combine(end_date, datetime.max.time())
        except (TypeError, AttributeError) as e:
            logger.error(f"Error combining dates: start_date={start_date} (type: {type(start_date)}), end_date={end_date} (type: {type(end_date)})")
            raise ValueError(f"Invalid date values: {e}")
        
        # Get all data
        sales_data = get_sales_data(start_datetime, end_datetime)
        expenses_data = get_expenses_data(start_datetime, end_datetime)
        receivables = get_receivables()
        low_stock = get_low_stock_items()
        customer_growth = get_customer_growth(start_datetime, end_datetime)
        invoice_growth = get_invoice_growth(start_datetime, end_datetime)
        car_growth = get_car_growth(start_datetime, end_datetime)
        open_repairs = get_open_repair_orders()
        vendor_balances = get_vendor_balances()
        pending_quotes = get_pending_quotes()
        completed_today = get_completed_repair_orders_today()
        
        # Calculate profit (Sales - Expenses)
        profit_data = calculate_profit(sales_data, expenses_data)
        
        return jsonify({
            'sales': sales_data,
            'expenses': expenses_data,
            'receivables': receivables,
            'profit': profit_data,
            'low_stock': low_stock,
            'customer_growth': customer_growth,
            'invoice_growth': invoice_growth,
            'car_growth': car_growth,
            'open_repairs': open_repairs,
            'vendor_balances': vendor_balances,
            'pending_quotes': pending_quotes,
            'completed_today': completed_today,
            'period': period,
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        })
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"Error generating reports: {e}")
        logger.error(f"Traceback: {error_trace}")
        return jsonify({'error': 'Failed to generate reports', 'details': str(e)}), 500

def get_sales_data(start_date, end_date):
    """Get comprehensive sales data for the specified period"""
    try:
        # Get daily sales with trend data (only invoices, exclude quotes)
        daily_sales = db.session.execute(db.text("""
            SELECT 
                DATE(created_at) as date,
                SUM(net_total) as total,
                COUNT(*) as count
            FROM invoice 
            WHERE created_at >= :start_date AND created_at <= :end_date
            AND type_of = 'invoice'
            GROUP BY DATE(created_at)
            ORDER BY date
        """), {'start_date': start_date, 'end_date': end_date}).fetchall()
        
        # Get monthly sales (only invoices, exclude quotes)
        monthly_sales = db.session.execute(db.text("""
            SELECT 
                DATE_FORMAT(created_at, '%Y-%m') as month,
                SUM(net_total) as total
            FROM invoice 
            WHERE created_at >= :start_date AND created_at <= :end_date
            AND type_of = 'invoice'
            GROUP BY DATE_FORMAT(created_at, '%Y-%m')
            ORDER BY month
        """), {'start_date': start_date, 'end_date': end_date}).fetchall()
        
        # Get yearly sales (only invoices, exclude quotes)
        yearly_sales = db.session.execute(db.text("""
            SELECT 
                YEAR(created_at) as year,
                SUM(net_total) as total
            FROM invoice 
            WHERE created_at >= :start_date AND created_at <= :end_date
            AND type_of = 'invoice'
            GROUP BY YEAR(created_at)
            ORDER BY year
        """), {'start_date': start_date, 'end_date': end_date}).fetchall()
        
        return {
            'daily': [{'date': str(row[0]), 'total': float(row[1] or 0)} for row in daily_sales],
            'monthly': [{'month': str(row[0]), 'total': float(row[1] or 0)} for row in monthly_sales],
            'yearly': [{'year': int(row[0]), 'total': float(row[1] or 0)} for row in yearly_sales],
            'total': sum(float(row[1] or 0) for row in daily_sales)
        }
    except Exception as e:
        logger.error(f"Error getting sales data: {e}")
        return {'daily': [], 'monthly': [], 'yearly': [], 'total': 0}

def get_expenses_data(start_date, end_date):
    """Get expenses data for the specified period"""
    try:
        # Get daily expenses
        daily_expenses = db.session.execute(db.text("""
            SELECT 
                DATE(date) as date,
                SUM(amount) as total
            FROM expense 
            WHERE date >= :start_date AND date <= :end_date
            GROUP BY DATE(date)
            ORDER BY date
        """), {'start_date': start_date, 'end_date': end_date}).fetchall()
        
        # Get monthly expenses
        monthly_expenses = db.session.execute(db.text("""
            SELECT 
                DATE_FORMAT(date, '%Y-%m') as month,
                SUM(amount) as total
            FROM expense 
            WHERE date >= :start_date AND date <= :end_date
            GROUP BY DATE_FORMAT(date, '%Y-%m')
            ORDER BY month
        """), {'start_date': start_date, 'end_date': end_date}).fetchall()
        
        # Get yearly expenses
        yearly_expenses = db.session.execute(db.text("""
            SELECT 
                YEAR(date) as year,
                SUM(amount) as total
            FROM expense 
            WHERE date >= :start_date AND date <= :end_date
            GROUP BY YEAR(date)
            ORDER BY year
        """), {'start_date': start_date, 'end_date': end_date}).fetchall()
        
        return {
            'daily': [{'date': str(row[0]), 'total': float(row[1] or 0)} for row in daily_expenses],
            'monthly': [{'month': str(row[0]), 'total': float(row[1] or 0)} for row in monthly_expenses],
            'yearly': [{'year': int(row[0]), 'total': float(row[1] or 0)} for row in yearly_expenses],
            'total': sum(float(row[1] or 0) for row in daily_expenses)
        }
    except Exception as e:
        logger.error(f"Error getting expenses data: {e}")
        return {'daily': [], 'monthly': [], 'yearly': [], 'total': 0}

def get_receivables():
    """Get total receivables from invoices (net_total - paid_amount) - only invoices, exclude quotes"""
    try:
        result = db.session.execute(db.text("""
            SELECT SUM(net_total - COALESCE(paid_amount, 0)) as receivables 
            FROM invoice 
            WHERE net_total > COALESCE(paid_amount, 0)
            AND type_of = 'invoice'
        """)).fetchone()
        
        return float(result[0] or 0)
    except Exception as e:
        logger.error(f"Error getting receivables: {e}")
        return 0

def calculate_profit(sales_data, expenses_data):
    """Calculate profit (Sales - Expenses)"""
    try:
        daily_profit = []
        for sales_day in sales_data['daily']:
            expenses_day = next(
                (exp for exp in expenses_data['daily'] if exp['date'] == sales_day['date']), 
                {'total': 0}
            )
            daily_profit.append({
                'date': sales_day['date'],
                'total': sales_day['total'] - expenses_day['total']
            })
        
        monthly_profit = []
        for sales_month in sales_data['monthly']:
            expenses_month = next(
                (exp for exp in expenses_data['monthly'] if exp['month'] == sales_month['month']), 
                {'total': 0}
            )
            monthly_profit.append({
                'month': sales_month['month'],
                'total': sales_month['total'] - expenses_month['total']
            })
        
        yearly_profit = []
        for sales_year in sales_data['yearly']:
            expenses_year = next(
                (exp for exp in expenses_data['yearly'] if exp['year'] == sales_year['year']), 
                {'total': 0}
            )
            yearly_profit.append({
                'year': sales_year['year'],
                'total': sales_year['total'] - expenses_year['total']
            })
        
        return {
            'daily': daily_profit,
            'monthly': monthly_profit,
            'yearly': yearly_profit,
            'total': sales_data['total'] - expenses_data['total']
        }
    except Exception as e:
        logger.error(f"Error calculating profit: {e}")
        return {'daily': [], 'monthly': [], 'yearly': [], 'total': 0}

def get_low_stock_items():
    """Get inventory items with low stock"""
    try:
        low_stock_items = db.session.execute(db.text("""
            SELECT name, quantity, reorder_level, category
            FROM inventory 
            WHERE quantity <= reorder_level
            ORDER BY (quantity / NULLIF(reorder_level, 0)) ASC
        """)).fetchall()
        
        return [
            {
                'item_name': row[0],
                'quantity': int(row[1]),
                'reorder_level': int(row[2]),
                'category': row[3],
                'urgency': 'critical' if row[1] <= row[2] * 0.5 else 'warning'
            }
            for row in low_stock_items
        ]
    except Exception as e:
        logger.error(f"Error getting low stock items: {e}")
        return []

def get_customer_growth(start_date, end_date):
    """Get customer growth metrics"""
    try:
        # Daily growth
        daily_growth = db.session.execute(db.text("""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as count
            FROM customer 
            WHERE created_at >= :start_date AND created_at <= :end_date
            GROUP BY DATE(created_at)
            ORDER BY date
        """), {'start_date': start_date, 'end_date': end_date}).fetchall()
        
        # Monthly growth
        monthly_growth = db.session.execute(db.text("""
            SELECT 
                DATE_FORMAT(created_at, '%Y-%m') as month,
                COUNT(*) as count
            FROM customer 
            WHERE created_at >= :start_date AND created_at <= :end_date
            GROUP BY DATE_FORMAT(created_at, '%Y-%m')
            ORDER BY month
        """), {'start_date': start_date, 'end_date': end_date}).fetchall()
        
        # Yearly growth
        yearly_growth = db.session.execute(db.text("""
            SELECT 
                YEAR(created_at) as year,
                COUNT(*) as count
            FROM customer 
            WHERE created_at >= :start_date AND created_at <= :end_date
            GROUP BY YEAR(created_at)
            ORDER BY year
        """), {'start_date': start_date, 'end_date': end_date}).fetchall()
        
        return {
            'daily': [{'date': str(row[0]), 'count': int(row[1])} for row in daily_growth],
            'monthly': [{'month': str(row[0]), 'count': int(row[1])} for row in monthly_growth],
            'yearly': [{'year': int(row[0]), 'count': int(row[1])} for row in yearly_growth],
            'total': sum(int(row[1]) for row in daily_growth)
        }
    except Exception as e:
        logger.error(f"Error getting customer growth: {e}")
        return {'daily': [], 'monthly': [], 'yearly': [], 'total': 0}

def get_invoice_growth(start_date, end_date):
    """Get invoice growth metrics"""
    try:
        # Daily growth
        daily_growth = db.session.execute(db.text("""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as count
            FROM invoice 
            WHERE created_at >= :start_date AND created_at <= :end_date
            GROUP BY DATE(created_at)
            ORDER BY date
        """), {'start_date': start_date, 'end_date': end_date}).fetchall()
        
        # Monthly growth
        monthly_growth = db.session.execute(db.text("""
            SELECT 
                DATE_FORMAT(created_at, '%Y-%m') as month,
                COUNT(*) as count
            FROM invoice 
            WHERE created_at >= :start_date AND created_at <= :end_date
            GROUP BY DATE_FORMAT(created_at, '%Y-%m')
            ORDER BY month
        """), {'start_date': start_date, 'end_date': end_date}).fetchall()
        
        # Yearly growth
        yearly_growth = db.session.execute(db.text("""
            SELECT 
                YEAR(created_at) as year,
                COUNT(*) as count
            FROM invoice 
            WHERE created_at >= :start_date AND created_at <= :end_date
            GROUP BY YEAR(created_at)
            ORDER BY year
        """), {'start_date': start_date, 'end_date': end_date}).fetchall()
        
        return {
            'daily': [{'date': str(row[0]), 'count': int(row[1])} for row in daily_growth],
            'monthly': [{'month': str(row[0]), 'count': int(row[1])} for row in monthly_growth],
            'yearly': [{'year': int(row[0]), 'count': int(row[1])} for row in yearly_growth],
            'total': sum(int(row[1]) for row in daily_growth)
        }
    except Exception as e:
        logger.error(f"Error getting invoice growth: {e}")
        return {'daily': [], 'monthly': [], 'yearly': [], 'total': 0}

def get_car_growth(start_date, end_date):
    """Get car growth metrics"""
    try:
        # Daily growth
        daily_growth = db.session.execute(db.text("""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as count
            FROM car 
            WHERE created_at >= :start_date AND created_at <= :end_date
            GROUP BY DATE(created_at)
            ORDER BY date
        """), {'start_date': start_date, 'end_date': end_date}).fetchall()
        
        # Monthly growth
        monthly_growth = db.session.execute(db.text("""
            SELECT 
                DATE_FORMAT(created_at, '%Y-%m') as month,
                COUNT(*) as count
            FROM car 
            WHERE created_at >= :start_date AND created_at <= :end_date
            GROUP BY DATE_FORMAT(created_at, '%Y-%m')
            ORDER BY month
        """), {'start_date': start_date, 'end_date': end_date}).fetchall()
        
        # Yearly growth
        yearly_growth = db.session.execute(db.text("""
            SELECT 
                YEAR(created_at) as year,
                COUNT(*) as count
            FROM car 
            WHERE created_at >= :start_date AND created_at <= :end_date
            GROUP BY YEAR(created_at)
            ORDER BY year
        """), {'start_date': start_date, 'end_date': end_date}).fetchall()
        
        return {
            'daily': [{'date': str(row[0]), 'count': int(row[1])} for row in daily_growth],
            'monthly': [{'month': str(row[0]), 'count': int(row[1])} for row in monthly_growth],
            'yearly': [{'year': int(row[0]), 'count': int(row[1])} for row in yearly_growth],
            'total': sum(int(row[1]) for row in daily_growth)
        }
    except Exception as e:
        logger.error(f"Error getting car growth: {e}")
        return {'daily': [], 'monthly': [], 'yearly': [], 'total': 0}

def get_open_repair_orders():
    """Get open repair orders"""
    try:
        open_orders = db.session.execute(db.text("""
            SELECT 
                id, customer_name, customer_phone, current_status, 
                created_at, updated_at, problem_description
            FROM repair_order 
            WHERE current_status != 'completed'
            ORDER BY created_at DESC
            LIMIT 20
        """)).fetchall()
        
        return [
            {
                'id': int(row[0]),
                'customer_name': row[1],
                'customer_phone': row[2],
                'status': row[3],
                'created_at': row[4].isoformat() if row[4] else None,
                'updated_at': row[5].isoformat() if row[5] else None,
                'problem_description': row[6]
            }
            for row in open_orders
        ]
    except Exception as e:
        logger.error(f"Error getting open repair orders: {e}")
        return []

def get_vendor_balances():
    """Get vendors with their current balances from ledger"""
    try:
        vendors = db.session.execute(db.text("""
            SELECT 
                v.name as vendor_name,
                COALESCE(SUM(vl.balance), 0) as current_balance
            FROM vendors v
            LEFT JOIN vendor_ledger vl ON v.id = vl.vendor_id
            GROUP BY v.id, v.name
            HAVING current_balance > 0
            ORDER BY current_balance DESC
            LIMIT 10
        """)).fetchall()
        
        return [
            {
                'vendor_name': row[0],
                'closing_balance': float(row[1])
            }
            for row in vendors
        ]
    except Exception as e:
        logger.error(f"Error getting vendor balances: {e}")
        return []

def get_pending_quotes():
    """Get pending quotes (quotes are stored as invoices with type 'quote')"""
    try:
        quotes = db.session.execute(db.text("""
            SELECT 
                id, customer_name, net_total, created_at, status
            FROM invoice 
            WHERE type_of = 'quote' AND status = 'pending'
            ORDER BY created_at DESC
            LIMIT 20
        """)).fetchall()
        
        return [
            {
                'id': int(row[0]),
                'customer_name': row[1],
                'total_amount': float(row[2] or 0),
                'created_at': row[3].isoformat() if row[3] else None,
                'quote_number': f"Q-{row[0]:04d}",  # Generate quote number from ID
                'status': row[4]
            }
            for row in quotes
        ]
    except Exception as e:
        logger.error(f"Error getting pending quotes: {e}")
        return []

def get_completed_repair_orders_today():
    """Get repair orders completed today"""
    try:
        today = date.today()
        completed = db.session.execute(db.text("""
            SELECT 
                id, customer_name, customer_phone, current_status,
                updated_at, problem_description
            FROM repair_order 
            WHERE current_status = 'completed' 
            AND DATE(updated_at) = :today
            ORDER BY updated_at DESC
        """), {'today': today}).fetchall()
        
        return [
            {
                'id': int(row[0]),
                'customer_name': row[1],
                'customer_phone': row[2],
                'status': row[3],
                'updated_at': row[4].isoformat() if row[4] else None,
                'problem_description': row[5]
            }
            for row in completed
        ]
    except Exception as e:
        logger.error(f"Error getting completed repair orders today: {e}")
        return []
