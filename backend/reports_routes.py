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

def _iso(value):
    """ISO string for a timestamp column, whichever type the driver returned.

    Raw db.text() queries hand back datetimes as datetime objects on MySQL but
    as strings on SQLite; calling .isoformat() blindly made whole widgets fail
    closed and return [] with only a log line to show for it.
    """
    if value is None:
        return None
    return value.isoformat() if hasattr(value, 'isoformat') else str(value)



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

def _roll_up_counts(daily_rows):
    """Month/year counts derived from daily rows: [(date_str, count), ...]."""
    rolled = _roll_up(daily_rows)
    return {
        'daily': [{'date': d['date'], 'count': int(d['total'])} for d in rolled['daily']],
        'monthly': [{'month': m['month'], 'count': int(m['total'])} for m in rolled['monthly']],
        'yearly': [{'year': y['year'], 'count': int(y['total'])} for y in rolled['yearly']],
        'total': int(rolled['total']),
    }


def _roll_up(daily_rows):
    """Month and year totals derived from daily rows: [(date_str, total), ...].

    Keeps the buckets internally consistent by construction and avoids
    MySQL-only DATE_FORMAT()/YEAR(), which made these figures collapse to 0 on
    any other engine.
    """
    daily, months, years = [], {}, {}
    for row in daily_rows:
        day = str(row[0])
        total = float(row[1] or 0)
        daily.append({'date': day, 'total': total})
        months[day[:7]] = months.get(day[:7], 0.0) + total
        years[int(day[:4])] = years.get(int(day[:4]), 0.0) + total

    return {
        'daily': daily,
        'monthly': [{'month': m, 'total': t} for m, t in sorted(months.items())],
        'yearly': [{'year': y, 'total': t} for y, t in sorted(years.items())],
        'total': sum(d['total'] for d in daily),
    }


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
        
        return _roll_up(daily_sales)

    except Exception as e:
        logger.error(f"Error getting sales data: {e}")
        return {'daily': [], 'monthly': [], 'yearly': [], 'total': 0}

def get_expenses_data(start_date, end_date):
    """Get expenses data for the specified period"""
    try:
        # expense.date is a DATE column, so bound it with dates. Comparing it
        # against datetimes only worked because MySQL coerces the types.
        params = {
            'start_date': start_date.date() if hasattr(start_date, 'date') else start_date,
            'end_date': end_date.date() if hasattr(end_date, 'date') else end_date,
        }

        # Get daily expenses
        daily_expenses = db.session.execute(db.text("""
            SELECT 
                DATE(date) as date,
                SUM(amount) as total
            FROM expense 
            WHERE date >= :start_date AND date <= :end_date
            GROUP BY DATE(date)
            ORDER BY date
        """), params).fetchall()
        
        return _roll_up(daily_expenses)

    except Exception as e:
        logger.error(f"Error getting expenses data: {e}")
        return {'daily': [], 'monthly': [], 'yearly': [], 'total': 0}

def get_receivables():
    """Total still owed on invoices, matching calculate_invoice_status().

    Amount due is net_total + tax - discount, and a customer can pay through
    either `advance` or `paid_amount`. Counting only net_total - paid_amount
    overstated receivables by every advance ever taken.
    """
    try:
        result = db.session.execute(db.text("""
            SELECT SUM(due - paid) AS receivables FROM (
                SELECT
                    net_total
                        + CASE WHEN include_tax THEN COALESCE(tax_amount, 0) ELSE 0 END
                        - COALESCE(discount, 0) AS due,
                    COALESCE(advance, 0) + COALESCE(paid_amount, 0) AS paid
                FROM invoice
                WHERE type_of = 'invoice'
            ) outstanding
            WHERE due > paid
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
        
        return _roll_up_counts(daily_growth)

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
        
        return _roll_up_counts(daily_growth)

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
        
        return _roll_up_counts(daily_growth)

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
            -- The app writes 'complete'; 'completed' never matched, so finished
            -- orders were reported as still open. Both spellings handled.
            WHERE current_status NOT IN ('complete', 'completed')
            ORDER BY created_at DESC
            LIMIT 20
        """)).fetchall()
        
        return [
            {
                'id': int(row[0]),
                'customer_name': row[1],
                'customer_phone': row[2],
                'status': row[3],
                'created_at': _iso(row[4]),
                'updated_at': _iso(row[5]),
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
                'created_at': _iso(row[3]),
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
            WHERE current_status IN ('complete', 'completed')
            AND DATE(updated_at) = :today
            ORDER BY updated_at DESC
        """), {'today': today}).fetchall()
        
        return [
            {
                'id': int(row[0]),
                'customer_name': row[1],
                'customer_phone': row[2],
                'status': row[3],
                'updated_at': _iso(row[4]),
                'problem_description': row[5]
            }
            for row in completed
        ]
    except Exception as e:
        logger.error(f"Error getting completed repair orders today: {e}")
        return []


# ===== DASHBOARD =====

# Each dashboard section is gated by the same permission that guards its page,
# so a user only ever sees work they can actually act on.
DASHBOARD_SECTIONS = (
    ('invoices', 'invoice'),
    ('quotes', 'invoice'),
    ('repairs', 'repair-order'),
    ('expenses', 'daily-expenses'),
    ('inventory', 'inventory'),
    ('insights', 'reports'),
)


def _dashboard_invoices():
    """Unpaid / partially paid invoices, using the same maths as receivables."""
    row = db.session.execute(db.text("""
        SELECT COUNT(*) AS cnt, COALESCE(SUM(due - paid), 0) AS owed
        FROM (
            SELECT
                net_total
                    + CASE WHEN include_tax THEN COALESCE(tax_amount, 0) ELSE 0 END
                    - COALESCE(discount, 0) AS due,
                COALESCE(advance, 0) + COALESCE(paid_amount, 0) AS paid
            FROM invoice
            WHERE type_of = 'invoice'
        ) outstanding
        WHERE due > paid
    """)).fetchone()

    recent = db.session.execute(db.text("""
        SELECT id, customer_name, created_at,
               net_total
                   + CASE WHEN include_tax THEN COALESCE(tax_amount, 0) ELSE 0 END
                   - COALESCE(discount, 0)
                   - COALESCE(advance, 0) - COALESCE(paid_amount, 0) AS owed
        FROM invoice
        WHERE type_of = 'invoice'
          AND net_total
              + CASE WHEN include_tax THEN COALESCE(tax_amount, 0) ELSE 0 END
              - COALESCE(discount, 0)
              > COALESCE(advance, 0) + COALESCE(paid_amount, 0)
        ORDER BY created_at ASC
        LIMIT 5
    """)).fetchall()

    return {
        'unpaid_count': int(row[0] or 0),
        'unpaid_total': float(row[1] or 0),
        'oldest': [
            {
                'id': int(r[0]),
                'customer_name': r[1],
                'created_at': _iso(r[2]),
                'owed': float(r[3] or 0),
            }
            for r in recent
        ],
    }


def _dashboard_quotes():
    row = db.session.execute(db.text("""
        SELECT COUNT(*) AS cnt, COALESCE(SUM(net_total), 0) AS value
        FROM invoice
        WHERE type_of = 'quote' AND status = 'pending'
    """)).fetchone()
    return {
        'pending_count': int(row[0] or 0),
        'pending_value': float(row[1] or 0),
        'items': get_pending_quotes()[:5],
    }


def _dashboard_repairs():
    by_status = db.session.execute(db.text("""
        SELECT current_status, COUNT(*)
        FROM repair_order
        WHERE current_status NOT IN ('complete', 'completed')
        GROUP BY current_status
    """)).fetchall()

    done_today = db.session.execute(db.text("""
        SELECT COUNT(*) FROM repair_order
        WHERE current_status IN ('complete', 'completed')
          AND DATE(updated_at) = :today
    """), {'today': date.today()}).fetchone()

    counts = {str(r[0]): int(r[1]) for r in by_status}
    return {
        'open_count': sum(counts.values()),
        'by_status': counts,
        'completed_today': int(done_today[0] or 0),
        'items': get_open_repair_orders()[:5],
    }


def _dashboard_expenses():
    today = date.today()
    row = db.session.execute(db.text("""
        SELECT
            COALESCE(SUM(CASE WHEN date = :today THEN amount END), 0) AS today_total,
            COALESCE(SUM(CASE WHEN date >= :month_start THEN amount END), 0) AS month_total
        FROM expense
        WHERE date >= :month_start
    """), {'today': today, 'month_start': today.replace(day=1)}).fetchone()
    return {
        'today_total': float(row[0] or 0),
        'month_total': float(row[1] or 0),
    }


def _dashboard_inventory():
    low = get_low_stock_items()
    return {'low_stock_count': len(low), 'items': low[:5]}


def _dashboard_insights():
    """Month-to-date business summary for admins."""
    today = date.today()
    start = datetime.combine(today.replace(day=1), datetime.min.time())
    end = datetime.combine(today, datetime.max.time())

    sales = get_sales_data(start, end)
    expenses = get_expenses_data(start, end)
    return {
        'sales_month': sales['total'],
        'expenses_month': expenses['total'],
        'profit_month': sales['total'] - expenses['total'],
        'receivables': get_receivables(),
        'sales_daily': sales['daily'],
        'expenses_daily': expenses['daily'],
    }


DASHBOARD_BUILDERS = {
    'invoices': _dashboard_invoices,
    'quotes': _dashboard_quotes,
    'repairs': _dashboard_repairs,
    'expenses': _dashboard_expenses,
    'inventory': _dashboard_inventory,
    'insights': _dashboard_insights,
}


def _user_permissions(user):
    """The user's effective permissions, resolved exactly as
    /api/auth/permissions/my resolves them so the dashboard and the nav agree."""
    from models import RolePermission
    from jwt_auth import ADMIN_PERMISSIONS, DEFAULT_ROLE_PERMISSIONS

    if user.role == 'admin':
        return set(ADMIN_PERMISSIONS)

    perms = [p.permission for p in RolePermission.query.filter_by(role=user.role).all()]
    if not perms and RolePermission.query.first() is None:
        perms = DEFAULT_ROLE_PERMISSIONS.get(user.role, [])
    return set(perms)


@reports_bp.route('/dashboard', methods=['GET'])
@login_required
def get_dashboard(current_user=None):
    """Role-scoped dashboard: the pending work this user can act on.

    One request instead of one per widget, and each section is omitted entirely
    when the user lacks the permission that guards it.
    """
    permissions = _user_permissions(current_user)

    data, failed = {}, []
    for section, permission in DASHBOARD_SECTIONS:
        if permission not in permissions:
            continue
        try:
            data[section] = DASHBOARD_BUILDERS[section]()
        except Exception as e:
            # One broken widget must not blank the whole dashboard.
            db.session.rollback()
            logger.error(f"Dashboard section '{section}' failed: {e}")
            failed.append(section)

    return jsonify({
        'sections': data,
        'unavailable': failed,
        'role': current_user.role,
        'generated_at': datetime.utcnow().isoformat(),
    }), 200
