from flask import Blueprint, request, jsonify, session
from models import db, Expense, User
from datetime import datetime, timedelta
from sqlalchemy import desc
from functools import wraps
from jwt_auth import login_required, role_required, admin_required
from flask_jwt_extended import jwt_required, get_jwt_identity
from log_utils import log_action
from period_lock import guard_period, guard_both, body_date, record_date

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
    """Get daily opening/closing balances and in/out ledger for a specific month"""
    try:
        from models import CashReceived, Expense
        from datetime import date
        import calendar
        
        # Get target month, default to current month
        month_param = request.args.get('month') # Format: YYYY-MM
        if not month_param:
            month_param = datetime.utcnow().strftime('%Y-%m')
            
        try:
            year, month = map(int, month_param.split('-'))
            start_date = date(year, month, 1)
            # Find the last day of the month
            _, last_day = calendar.monthrange(year, month)
            end_date = date(year, month, last_day)
        except ValueError:
            return jsonify({'error': 'Invalid month format. Use YYYY-MM'}), 400
            
        # 1. Calculate opening balance prior to the start of this month
        # Sum of all cash received prior to start_date
        total_cash_prior = db.session.query(db.func.sum(CashReceived.amount)).filter(CashReceived.date < start_date).scalar() or 0.0
        # Sum of all expenses prior to start_date
        total_exp_prior = db.session.query(db.func.sum(Expense.amount)).filter(Expense.date < start_date).scalar() or 0.0
        
        initial_balance = float(total_cash_prior) - float(total_exp_prior)
        
        # 2. Get all cash received and expenses for the target month
        cash_records = CashReceived.query.filter(CashReceived.date >= start_date, CashReceived.date <= end_date).all()
        expense_records = Expense.query.filter(Expense.date >= start_date, Expense.date <= end_date).all()
        
        # Group records by date
        cash_by_date = {}
        for r in cash_records:
            d_str = r.date.strftime('%Y-%m-%d')
            cash_by_date.setdefault(d_str, []).append(r)
            
        expenses_by_date = {}
        for r in expense_records:
            d_str = r.date.strftime('%Y-%m-%d')
            expenses_by_date.setdefault(d_str, []).append(r)
            
        # 3. Generate daily ledger entries
        daily_ledger = []
        current_balance = initial_balance
        
        # Iterate through every day of the month
        for day in range(1, last_day + 1):
            cur_date = date(year, month, day)
            d_str = cur_date.strftime('%Y-%m-%d')
            
            day_cash_list = cash_by_date.get(d_str, [])
            day_exp_list = expenses_by_date.get(d_str, [])
            
            day_inflow = sum(float(r.amount) for r in day_cash_list)
            day_outflow = sum(float(r.amount) for r in day_exp_list)
            
            opening_bal = current_balance
            net_change = day_inflow - day_outflow
            closing_bal = opening_bal + net_change
            current_balance = closing_bal
            
            daily_ledger.append({
                'date': d_str,
                'opening_balance': round(opening_bal, 2),
                'inflow': round(day_inflow, 2),
                'outflow': round(day_outflow, 2),
                'closing_balance': round(closing_bal, 2)
            })
            
        # 4. Detailed transactions list (sorted by date)
        details = []
        for r in cash_records:
            details.append({
                'id': f"in-{r.id}",
                'date': r.date.strftime('%Y-%m-%d'),
                'type': 'in',
                'description': r.description,
                'amount': float(r.amount),
                'payment_method': r.payment_method,
                'notes': r.notes or ""
            })
        for r in expense_records:
            details.append({
                'id': f"out-{r.id}",
                'date': r.date.strftime('%Y-%m-%d'),
                'type': 'out',
                'description': r.description,
                'amount': float(r.amount),
                'category': r.category,
                'notes': r.notes or ""
            })
        details.sort(key=lambda x: (x['date'], x['type'] == 'out'))
        
        return jsonify({
            'month': month_param,
            'initial_balance': round(initial_balance, 2),
            'daily_ledger': daily_ledger,
            'details': details
        }), 200
    except Exception as e:
        logger.error(f"Error generating monthly ledger: {e}")
        return jsonify({'error': 'Failed to generate monthly ledger'}), 500 