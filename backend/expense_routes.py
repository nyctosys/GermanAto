from flask import Blueprint, request, jsonify, session
from models import db, Expense, User
from datetime import datetime, timedelta
from sqlalchemy import desc
from functools import wraps

expense_routes = Blueprint('expense_routes', __name__)

# Decorator to check if user can edit expense based on role and time
def can_edit_expense(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        
        user = User.query.get(session['user_id'])
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
    return decorated_function

@expense_routes.route('/expenses', methods=['GET'])
def get_expenses():
    """Get all expenses with optional filtering"""
    try:
        # Get query parameters for filtering
        category = request.args.get('category')
        date = request.args.get('date')
        keyword = request.args.get('keyword')
        
        # Start with base query
        query = Expense.query
        
        # Apply filters
        if category:
            query = query.filter(Expense.category == category)
        
        if date:
            query = query.filter(Expense.date == date)
        
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
def get_expense(expense_id):
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
def create_expense():
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
def delete_expense(expense_id):
    """Delete an expense"""
    try:
        expense = Expense.query.get_or_404(expense_id)
        
        db.session.delete(expense)
        db.session.commit()
        
        return jsonify({'message': 'Expense deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@expense_routes.route('/expenses/summary', methods=['GET'])
def get_expense_summary():
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