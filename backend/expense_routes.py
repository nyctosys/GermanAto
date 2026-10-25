from flask import Blueprint, request, jsonify, session
from models import db, Expense, User
from datetime import datetime, timedelta
from sqlalchemy import desc
from functools import wraps
from jwt_auth import login_required, role_required, admin_required
from flask_jwt_extended import jwt_required, get_jwt_identity
from log_utils import log_action
from period_lock import guard_period, guard_both, body_date, record_date
from petty_cash import wants_till, till_expenses

expense_routes = Blueprint('expense_routes', __name__)

# Decorator to check if user can edit expense based on role and time
def can_edit_expense(f):
    @wraps(f)
    @jwt_required()
    def decorated_function(*args, **kwargs):
        try:
            current_user_id = get_jwt_identity()
            if not current_user_id:
                return jsonify({'error': 'Authentication required'}), 401
            
            user = User.query.get(int(current_user_id))
            if not user or not user.is_active:
                return jsonify({'error': 'User not found or inactive'}), 401
            
            # Admins can always edit
            if user.role == 'admin':
                return f(*args, **kwargs)
            
            # For other roles, check if expense is older than 1 day
            expense_id = kwargs.get('expense_id')
            if expense_id:
                expense = Expense.query.get(expense_id)
                if not expense:
                    return jsonify({'error': 'Expense not found'}), 404
                
                # Check if expense is older than 1 day
                one_day_ago = datetime.utcnow() - timedelta(days=1)
                if expense.created_at < one_day_ago:
                    return jsonify({'error': 'Cannot edit expenses older than 1 day'}), 403
            
            return f(*args, **kwargs)
        except (ValueError, TypeError) as e:
            return jsonify({'error': 'Invalid user ID format'}), 401
        except Exception as e:
            return jsonify({'error': 'Authentication error'}), 500
    return decorated_function

@expense_routes.route('/expenses', methods=['GET'])
@login_required
def get_expenses(current_user=None):
    """Get all expenses with optional filtering"""
    try:
        # Get query parameters for filtering
        category = request.args.get('category')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        keyword = request.args.get('keyword')
        
        # Start with base query
        query = Expense.query

        # The Daily Expenses page asks for the till only: parts, payroll and
        # capital spending are owned by other ledgers and would double-count.
        if wants_till(request.args):
            query = till_expenses(query)

        # Apply filters
        if category:
            query = query.filter(Expense.category == category)
        
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(Expense.date >= start_date_obj)
            except ValueError:
                return jsonify({'error': 'Invalid start_date format. Use YYYY-MM-DD'}), 400
        
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(Expense.date <= end_date_obj)
            except ValueError:
                return jsonify({'error': 'Invalid end_date format. Use YYYY-MM-DD'}), 400
        
        if keyword:
            query = query.filter(
                db.or_(
                    Expense.description.ilike(f'%{keyword}%'),
                    Expense.notes.ilike(f'%{keyword}%')
                )
            )
        
        # Order by date (newest first)
        expenses = query.order_by(desc(Expense.date)).all()
        
        # Convert to JSON
        expenses_data = []
        for expense in expenses:
            expenses_data.append({
                'id': expense.id,
                'date': expense.date.isoformat() if expense.date else None,
                'category': expense.category,
                'description': expense.description,
                'amount': expense.amount,
                'notes': expense.notes,
                'created_at': expense.created_at.isoformat() if expense.created_at else None,
                'updated_at': expense.updated_at.isoformat() if expense.updated_at else None
            })
        
        return jsonify(expenses_data), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@expense_routes.route('/expenses/<int:expense_id>', methods=['GET'])
@login_required
def get_expense(expense_id, current_user=None):
    """Get a specific expense by ID"""
    try:
        expense = Expense.query.get_or_404(expense_id)
        
        expense_data = {
            'id': expense.id,
            'date': expense.date.isoformat() if expense.date else None,
            'category': expense.category,
            'description': expense.description,
            'amount': expense.amount,
            'notes': expense.notes,
            'created_at': expense.created_at.isoformat() if expense.created_at else None,
            'updated_at': expense.updated_at.isoformat() if expense.updated_at else None
        }
        
        return jsonify(expense_data), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@expense_routes.route('/expenses', methods=['POST'])
@role_required(['admin', 'accountant'])
@guard_period(body_date('date'))
def create_expense(current_user=None):
    """Create a new expense"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['date', 'category', 'description', 'amount']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Parse date
        try:
            expense_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        # Validate amount
        try:
            amount = float(data['amount'])
            if amount < 0:
                return jsonify({'error': 'Amount must be positive'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid amount'}), 400
        
        # Create new expense
        new_expense = Expense(
            date=expense_date,
            category=data['category'],
            description=data['description'],
            amount=amount,
            notes=data.get('notes', '')
        )
        
        db.session.add(new_expense)
        log_action(current_user, 'CREATE', 'expenses', new_expense.id, f"Created expense: {new_expense.description} ({new_expense.amount} PKR, Category: {new_expense.category})")
        db.session.commit()
        
        # Return the created expense
        expense_data = {
            'id': new_expense.id,
            'date': new_expense.date.isoformat() if new_expense.date else None,
            'category': new_expense.category,
            'description': new_expense.description,
            'amount': new_expense.amount,
            'notes': new_expense.notes,
            'created_at': new_expense.created_at.isoformat() if new_expense.created_at else None,
            'updated_at': new_expense.updated_at.isoformat() if new_expense.updated_at else None
        }
        
        return jsonify(expense_data), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@expense_routes.route('/expenses/<int:expense_id>', methods=['PUT'])
@can_edit_expense
@guard_both(Expense, 'expense_id')
def update_expense(expense_id):
    """Update an existing expense"""
    try:
        expense = Expense.query.get_or_404(expense_id)
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['date', 'category', 'description', 'amount']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Parse date
        try:
            expense_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        # Validate amount
        try:
            amount = float(data['amount'])
            if amount < 0:
                return jsonify({'error': 'Amount must be positive'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid amount'}), 400
        
        # Update expense
        expense.date = expense_date
        expense.category = data['category']
        expense.description = data['description']
        expense.amount = amount
        expense.notes = data.get('notes', '')
        expense.updated_at = datetime.utcnow()
        
        current_user = None
        current_user_id = get_jwt_identity()
        if current_user_id:
            current_user = User.query.get(int(current_user_id))
            
        log_action(current_user, 'UPDATE', 'expenses', expense.id, f"Updated expense ID {expense.id}: {expense.description} ({expense.amount} PKR)")
        db.session.commit()
        
        # Return the updated expense
        expense_data = {
            'id': expense.id,
            'date': expense.date.isoformat() if expense.date else None,
            'category': expense.category,
            'description': expense.description,
            'amount': expense.amount,
            'notes': expense.notes,
            'created_at': expense.created_at.isoformat() if expense.created_at else None,
            'updated_at': expense.updated_at.isoformat() if expense.updated_at else None
        }
        
        return jsonify(expense_data), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@expense_routes.route('/expenses/<int:expense_id>', methods=['DELETE'])
@can_edit_expense
@guard_period(record_date(Expense, 'expense_id'))
def delete_expense(expense_id):
    """Delete an expense"""
    try:
        expense = Expense.query.get_or_404(expense_id)
        
        current_user = None
        current_user_id = get_jwt_identity()
        if current_user_id:
            current_user = User.query.get(int(current_user_id))
            
        log_action(current_user, 'DELETE', 'expenses', expense_id, f"Deleted expense ID {expense_id}: {expense.description} ({expense.amount} PKR)")
        db.session.delete(expense)
        db.session.commit()
        
        return jsonify({'message': 'Expense deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@expense_routes.route('/expenses/summary', methods=['GET'])
@login_required
def get_expense_summary(current_user=None):
    """Get expense summary statistics"""
    try:
        # Get query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Start with base query
        query = Expense.query

        # Same narrowing as the list, so the cards and the table agree.
        if wants_till(request.args):
            query = till_expenses(query)
        
        # Apply date filters if provided
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(Expense.date >= start_date_obj)
            except ValueError:
                return jsonify({'error': 'Invalid start_date format. Use YYYY-MM-DD'}), 400
        
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(Expense.date <= end_date_obj)
            except ValueError:
                return jsonify({'error': 'Invalid end_date format. Use YYYY-MM-DD'}), 400
        
        # Get all expenses for the period
        expenses = query.all()
        
        # Calculate summary
        total_amount = sum(expense.amount for expense in expenses)
        
        # Group by category
        category_totals = {}
        for expense in expenses:
            category = expense.category
            if category not in category_totals:
                category_totals[category] = 0
            category_totals[category] += expense.amount
        
        # Get today's expenses
        today = datetime.now().date()
        today_expenses = [exp for exp in expenses if exp.date == today]
        today_total = sum(exp.amount for exp in today_expenses)
        
        # Get this month's expenses
        current_month = datetime.now().replace(day=1).date()
        month_expenses = [exp for exp in expenses if exp.date >= current_month]
        month_total = sum(exp.amount for exp in month_expenses)
        
        summary = {
            'total_amount': total_amount,
            'today_total': today_total,
            'month_total': month_total,
            'category_totals': category_totals,
            'total_expenses': len(expenses),
            'today_expenses': len(today_expenses),
            'month_expenses': len(month_expenses)
        }
        
        return jsonify(summary), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500 

@expense_routes.route('/expenses/monthly-ledger', methods=['GET'])
@login_required
def get_monthly_ledger(current_user=None):
    """Every rupee in and out over a period, with running balances.

    This is the full picture on purpose - unlike the Daily Expenses till, it
    counts parts, payroll, capital spending and invoice settlements too.

    Accepts either ?month=YYYY-MM or an explicit ?start_date=&end_date= range.
    """
    try:
        from models import CashReceived, Expense
        from datetime import date
        import calendar

        def parse_day(value):
            return datetime.strptime(value, '%Y-%m-%d').date()

        start_param = request.args.get('start_date')
        end_param = request.args.get('end_date')
        month_param = request.args.get('month')

        if start_param and end_param:
            # Explicit range wins, so "last 90 days" and "this quarter" work.
            try:
                start_date = parse_day(start_param)
                end_date = parse_day(end_param)
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
            if end_date < start_date:
                return jsonify({'error': 'end_date is before start_date'}), 400
            label = f"{start_date.isoformat()} to {end_date.isoformat()}"
        else:
            if not month_param:
                month_param = datetime.utcnow().strftime('%Y-%m')
            try:
                year, month = map(int, month_param.split('-'))
                start_date = date(year, month, 1)
                end_date = date(year, month, calendar.monthrange(year, month)[1])
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid month format. Use YYYY-MM'}), 400
            label = month_param

        span_days = (end_date - start_date).days + 1
        if span_days > 400:
            return jsonify({'error': 'Range is too long. Choose 400 days or fewer.'}), 400

        # Opening balance: everything that happened before this period.
        cash_prior = db.session.query(db.func.sum(CashReceived.amount)).filter(
            CashReceived.date < start_date).scalar() or 0.0
        exp_prior = db.session.query(db.func.sum(Expense.amount)).filter(
            Expense.date < start_date).scalar() or 0.0
        initial_balance = float(cash_prior) - float(exp_prior)

        cash_records = CashReceived.query.filter(
            CashReceived.date >= start_date, CashReceived.date <= end_date).all()
        expense_records = Expense.query.filter(
            Expense.date >= start_date, Expense.date <= end_date).all()

        cash_by_date, expenses_by_date = {}, {}
        for r in cash_records:
            cash_by_date.setdefault(r.date.isoformat(), []).append(r)
        for r in expense_records:
            expenses_by_date.setdefault(r.date.isoformat(), []).append(r)

        # Day-by-day balances across every day in the range, including quiet ones.
        daily_ledger = []
        running = initial_balance
        for offset in range(span_days):
            cur = start_date + timedelta(days=offset)
            key = cur.isoformat()
            inflow = sum(float(r.amount) for r in cash_by_date.get(key, []))
            outflow = sum(float(r.amount) for r in expenses_by_date.get(key, []))
            opening = running
            running = opening + inflow - outflow
            daily_ledger.append({
                'date': key,
                'opening_balance': round(opening, 2),
                'inflow': round(inflow, 2),
                'outflow': round(outflow, 2),
                'entry_count': len(cash_by_date.get(key, [])) + len(expenses_by_date.get(key, [])),
                'closing_balance': round(running, 2),
            })

        # Every individual movement, carrying its own running balance so a row
        # can be read on its own without re-deriving the arithmetic.
        details = []
        for r in cash_records:
            details.append({
                'id': f"in-{r.id}",
                'record_id': r.id,
                'date': r.date.isoformat(),
                'type': 'in',
                'description': r.description,
                'amount': float(r.amount),
                'bucket': r.payment_method or 'Unspecified',
                'invoice_id': getattr(r, 'invoice_id', None),
                'notes': r.notes or '',
            })
        for r in expense_records:
            details.append({
                'id': f"out-{r.id}",
                'record_id': r.id,
                'date': r.date.isoformat(),
                'type': 'out',
                'description': r.description,
                'amount': float(r.amount),
                'bucket': r.category or 'Uncategorised',
                'invoice_id': None,
                'notes': r.notes or '',
            })
        details.sort(key=lambda x: (x['date'], x['type'] == 'out', x['id']))

        running = initial_balance
        for d in details:
            running += d['amount'] if d['type'] == 'in' else -d['amount']
            d['balance'] = round(running, 2)

        # Where the money actually went, biggest first.
        def breakdown(rows, kind):
            totals = {}
            for d in rows:
                if d['type'] != kind:
                    continue
                b = totals.setdefault(d['bucket'], {'bucket': d['bucket'], 'total': 0.0, 'count': 0})
                b['total'] += d['amount']
                b['count'] += 1
            out = sorted(totals.values(), key=lambda x: x['total'], reverse=True)
            for b in out:
                b['total'] = round(b['total'], 2)
            return out

        total_in = round(sum(float(r.amount) for r in cash_records), 2)
        total_out = round(sum(float(r.amount) for r in expense_records), 2)
        settled = [d for d in details if d['type'] == 'in' and d['invoice_id']]

        return jsonify({
            'month': label,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'days': span_days,
            'initial_balance': round(initial_balance, 2),
            'total_in': total_in,
            'total_out': total_out,
            'net_change': round(total_in - total_out, 2),
            'closing_balance': round(initial_balance + total_in - total_out, 2),
            'entry_count': len(details),
            'invoice_settlements': {
                'count': len(settled),
                'total': round(sum(d['amount'] for d in settled), 2),
            },
            'expense_breakdown': breakdown(details, 'out'),
            'income_breakdown': breakdown(details, 'in'),
            'daily_ledger': daily_ledger,
            'details': details,
        }), 200
    except Exception as e:
        logger.error(f"Error generating monthly ledger: {e}")
        return jsonify({'error': 'Failed to generate monthly ledger'}), 500
