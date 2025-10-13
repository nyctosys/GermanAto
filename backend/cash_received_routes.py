from flask import Blueprint, request, jsonify, session
from models import db, CashReceived, User
from datetime import datetime, timedelta
from sqlalchemy import desc
from functools import wraps
from jwt_auth import login_required, role_required, admin_required
from flask_jwt_extended import jwt_required, get_jwt_identity

cash_received_routes = Blueprint('cash_received_routes', __name__)

# Decorator to check if user can edit cash received based on role and time
def can_edit_cash_received(f):
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
            
            # For other roles, check if cash received is older than 1 day
            cash_id = kwargs.get('cash_id')
            if cash_id:
                cash_received = CashReceived.query.get(cash_id)
                if not cash_received:
                    return jsonify({'error': 'Cash received record not found'}), 404
                
                # Check if cash received is older than 1 day
                one_day_ago = datetime.utcnow() - timedelta(days=1)
                if cash_received.created_at < one_day_ago:
                    return jsonify({'error': 'Cannot edit cash received records older than 1 day'}), 403
            
            return f(*args, **kwargs)
        except (ValueError, TypeError) as e:
            return jsonify({'error': 'Invalid user ID format'}), 401
        except Exception as e:
            return jsonify({'error': 'Authentication error'}), 500
    return decorated_function

@cash_received_routes.route('/cash-received', methods=['GET'])
@login_required
def get_cash_received():
    """Get all cash received records with optional filtering"""
    try:
        # Get query parameters for filtering
        payment_method = request.args.get('payment_method')
        date = request.args.get('date')
        keyword = request.args.get('keyword')
        
        # Start with base query
        query = CashReceived.query
        
        # Apply filters
        if payment_method:
            query = query.filter(CashReceived.payment_method == payment_method)
        
        if date:
            query = query.filter(CashReceived.date == date)
        
        if keyword:
            query = query.filter(
                db.or_(
                    CashReceived.description.ilike(f'%{keyword}%'),
                    CashReceived.notes.ilike(f'%{keyword}%')
                )
            )
        
        # Order by date (newest first)
        cash_records = query.order_by(desc(CashReceived.date)).all()
        
        # Convert to JSON
        cash_data = []
        for cash in cash_records:
            cash_data.append({
                'id': cash.id,
                'date': cash.date.isoformat() if cash.date else None,
                'description': cash.description,
                'amount': cash.amount,
                'payment_method': cash.payment_method,
                'notes': cash.notes,
                'created_at': cash.created_at.isoformat() if cash.created_at else None,
                'updated_at': cash.updated_at.isoformat() if cash.updated_at else None
            })
        
        return jsonify(cash_data), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@cash_received_routes.route('/cash-received/<int:cash_id>', methods=['GET'])
@login_required
def get_cash_received_by_id(cash_id):
    """Get a specific cash received record by ID"""
    try:
        cash_received = CashReceived.query.get_or_404(cash_id)
        
        cash_data = {
            'id': cash_received.id,
            'date': cash_received.date.isoformat() if cash_received.date else None,
            'description': cash_received.description,
            'amount': cash_received.amount,
            'payment_method': cash_received.payment_method,
            'notes': cash_received.notes,
            'created_at': cash_received.created_at.isoformat() if cash_received.created_at else None,
            'updated_at': cash_received.updated_at.isoformat() if cash_received.updated_at else None
        }
        
        return jsonify(cash_data), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@cash_received_routes.route('/cash-received', methods=['POST'])
@role_required(['admin', 'accountant'])
def create_cash_received():
    """Create a new cash received record"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['date', 'description', 'amount', 'payment_method']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Parse date
        try:
            cash_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        # Validate amount
        try:
            amount = float(data['amount'])
            if amount < 0:
                return jsonify({'error': 'Amount must be positive'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid amount'}), 400
        
        # Create new cash received record
        new_cash = CashReceived(
            date=cash_date,
            description=data['description'],
            amount=amount,
            payment_method=data['payment_method'],
            notes=data.get('notes', '')
        )
        
        db.session.add(new_cash)
        db.session.commit()
        
        # Return the created cash received record
        cash_data = {
            'id': new_cash.id,
            'date': new_cash.date.isoformat() if new_cash.date else None,
            'description': new_cash.description,
            'amount': new_cash.amount,
            'payment_method': new_cash.payment_method,
            'notes': new_cash.notes,
            'created_at': new_cash.created_at.isoformat() if new_cash.created_at else None,
            'updated_at': new_cash.updated_at.isoformat() if new_cash.updated_at else None
        }
        
        return jsonify(cash_data), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@cash_received_routes.route('/cash-received/<int:cash_id>', methods=['PUT'])
@can_edit_cash_received
def update_cash_received(cash_id):
    """Update an existing cash received record"""
    try:
        cash_received = CashReceived.query.get_or_404(cash_id)
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['date', 'description', 'amount', 'payment_method']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Parse date
        try:
            cash_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        # Validate amount
        try:
            amount = float(data['amount'])
            if amount < 0:
                return jsonify({'error': 'Amount must be positive'}), 400
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid amount'}), 400
        
        # Update cash received record
        cash_received.date = cash_date
        cash_received.description = data['description']
        cash_received.amount = amount
        cash_received.payment_method = data['payment_method']
        cash_received.notes = data.get('notes', '')
        cash_received.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Return the updated cash received record
        cash_data = {
            'id': cash_received.id,
            'date': cash_received.date.isoformat() if cash_received.date else None,
            'description': cash_received.description,
            'amount': cash_received.amount,
            'payment_method': cash_received.payment_method,
            'notes': cash_received.notes,
            'created_at': cash_received.created_at.isoformat() if cash_received.created_at else None,
            'updated_at': cash_received.updated_at.isoformat() if cash_received.updated_at else None
        }
        
        return jsonify(cash_data), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@cash_received_routes.route('/cash-received/<int:cash_id>', methods=['DELETE'])
@can_edit_cash_received
def delete_cash_received(cash_id):
    """Delete a cash received record"""
    try:
        cash_received = CashReceived.query.get_or_404(cash_id)
        
        db.session.delete(cash_received)
        db.session.commit()
        
        return jsonify({'message': 'Cash received record deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@cash_received_routes.route('/cash-received/summary', methods=['GET'])
@login_required
def get_cash_received_summary():
    """Get cash received summary statistics"""
    try:
        # Get query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Start with base query
        query = CashReceived.query
        
        # Apply date filters if provided
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(CashReceived.date >= start_date_obj)
            except ValueError:
                return jsonify({'error': 'Invalid start_date format. Use YYYY-MM-DD'}), 400
        
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(CashReceived.date <= end_date_obj)
            except ValueError:
                return jsonify({'error': 'Invalid end_date format. Use YYYY-MM-DD'}), 400
        
        # Get all cash received records for the period
        cash_records = query.all()
        
        # Calculate summary
        total_amount = sum(cash.amount for cash in cash_records)
        
        # Group by payment method
        payment_method_totals = {}
        for cash in cash_records:
            method = cash.payment_method
            if method not in payment_method_totals:
                payment_method_totals[method] = 0
            payment_method_totals[method] += cash.amount
        
        # Get today's cash received
        today = datetime.now().date()
        today_cash = [cash for cash in cash_records if cash.date == today]
        today_total = sum(cash.amount for cash in today_cash)
        
        # Get this month's cash received
        current_month = datetime.now().replace(day=1).date()
        month_cash = [cash for cash in cash_records if cash.date >= current_month]
        month_total = sum(cash.amount for cash in month_cash)
        
        summary = {
            'total_amount': total_amount,
            'today_total': today_total,
            'month_total': month_total,
            'payment_method_totals': payment_method_totals,
            'total_records': len(cash_records),
            'today_records': len(today_cash),
            'month_records': len(month_cash)
        }
        
        return jsonify(summary), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
