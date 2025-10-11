from flask import Blueprint, request, jsonify, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Worker, User
from datetime import datetime, date
from functools import wraps
import logging

# Create blueprint for HR routes
hr_bp = Blueprint('hr', __name__)

# Set up logging
logger = logging.getLogger(__name__)

# JWT-based authentication decorators
def login_required(f):
    @wraps(f)
    @jwt_required()
    def decorated_function(*args, **kwargs):
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))
        
        if not user or not user.is_active:
            return jsonify({'error': 'User not found or inactive'}), 401
        
        return f(*args, **kwargs)
    return decorated_function

def role_required(required_roles):
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            try:
                current_user_id = get_jwt_identity()
                if not current_user_id:
                    return jsonify({'error': 'Invalid token'}), 401
                
                user = User.query.get(int(current_user_id))
                
                if not user or not user.is_active:
                    return jsonify({'error': 'User not found or inactive'}), 401
                
                # Convert to list if string
                roles_list = [required_roles] if isinstance(required_roles, str) else required_roles
                
                if user.role not in roles_list:
                    return jsonify({'error': 'Insufficient permissions'}), 403
                
                return f(*args, **kwargs)
            except (ValueError, TypeError) as e:
                logger.error(f"Error in role_required decorator: {e}")
                return jsonify({'error': 'Invalid user ID format'}), 401
            except Exception as e:
                logger.error(f"Unexpected error in role_required decorator: {e}")
                return jsonify({'error': 'Authentication error'}), 500
        return decorated_function
    return decorator

# ===== HR MANAGEMENT ROUTES =====

@hr_bp.route('/hr')
def hr_page():
    """HR management page"""
    return send_from_directory('frontend', 'hr.html')

@hr_bp.route('/hr/<int:worker_id>')
def worker_detail(worker_id):
    """Worker detail page"""
    worker = Worker.query.get_or_404(worker_id)
    return send_from_directory('frontend', 'worker_detail.html')

@hr_bp.route('/api/workers', methods=['GET'])
@role_required(['admin', 'accountant', 'inventory_manager'])
def get_workers():
    """Get all workers with optional search and filter"""
    try:
        search_query = request.args.get('search', '').strip()
        status_filter = request.args.get('status', '').strip()
        department_filter = request.args.get('department', '').strip()
        
        logger.info(f"Fetching workers with filters - search: '{search_query}', status: '{status_filter}', department: '{department_filter}'")
        
        query = Worker.query

        # Apply search filter
        if search_query:
            search_term = f"%{search_query}%"
            query = query.filter(
                db.or_(
                    Worker.first_name.ilike(search_term),
                    Worker.last_name.ilike(search_term),
                    Worker.employee_id.ilike(search_term),
                    Worker.phone.ilike(search_term),
                    Worker.position.ilike(search_term)
                )
            )

        # Apply status filter
        if status_filter:
            query = query.filter(Worker.status == status_filter)

        # Apply department filter
        if department_filter:
            query = query.filter(Worker.department.ilike(f"%{department_filter}%"))

        # Order by hire date (newest first)
        workers = query.order_by(Worker.hire_date.desc()).all()
        
        logger.info(f"Successfully fetched {len(workers)} workers")

        return jsonify({
            'workers': [worker.to_dict() for worker in workers],
            'total': len(workers)
        })

    except Exception as e:
        logger.error(f"Error fetching workers: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch workers'}), 500

@hr_bp.route('/api/workers/<int:worker_id>', methods=['GET'])
@role_required(['admin', 'accountant', 'inventory_manager'])
def get_worker(worker_id):
    """Get specific worker by ID"""
    try:
        worker = Worker.query.get(worker_id)
        if not worker:
            return jsonify({'error': 'Worker not found'}), 404

        return jsonify(worker.to_dict())

    except Exception as e:
        logger.error(f"Error fetching worker {worker_id}: {e}")
        return jsonify({'error': 'Failed to fetch worker'}), 500

@hr_bp.route('/api/workers', methods=['POST'])
@role_required(['admin', 'accountant'])
def create_worker():
    """Create a new worker"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Validate required fields
        required_fields = ['employee_id', 'first_name', 'last_name', 'phone', 'address', 'cnic', 'date_of_birth', 'hire_date', 'position', 'department']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field.replace("_", " ").title()} is required'}), 400

        # Check if employee ID already exists
        existing_worker = Worker.query.filter_by(employee_id=data['employee_id']).first()
        if existing_worker:
            return jsonify({'error': 'Employee ID already exists'}), 400

        # Check if CNIC already exists
        existing_cnic = Worker.query.filter_by(cnic=data['cnic']).first()
        if existing_cnic:
            return jsonify({'error': 'CNIC already exists'}), 400

        # Create new worker
        worker = Worker(
            employee_id=data['employee_id'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            email=data.get('email'),
            phone=data['phone'],
            address=data['address'],
            cnic=data['cnic'],
            date_of_birth=datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date(),
            hire_date=datetime.strptime(data['hire_date'], '%Y-%m-%d').date(),
            position=data['position'],
            department=data['department'],
            salary=float(data['salary']) if data.get('salary') else None,
            status=data.get('status', 'active'),
            emergency_contact_name=data.get('emergency_contact_name'),
            emergency_contact_phone=data.get('emergency_contact_phone'),
            notes=data.get('notes')
        )

        db.session.add(worker)
        db.session.commit()

        return jsonify({
            'message': 'Worker created successfully',
            'worker': worker.to_dict()
        }), 201

    except ValueError as e:
        db.session.rollback()
        logger.error(f"Invalid date format: {e}")
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating worker: {e}")
        return jsonify({'error': 'Failed to create worker'}), 500

@hr_bp.route('/api/workers/<int:worker_id>', methods=['PUT'])
@role_required(['admin', 'accountant'])
def update_worker(worker_id):
    """Update an existing worker"""
    try:
        worker = Worker.query.get(worker_id)
        if not worker:
            return jsonify({'error': 'Worker not found'}), 404

        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Update fields
        if 'employee_id' in data:
            # Check if new employee ID already exists (excluding current worker)
            existing = Worker.query.filter(Worker.employee_id == data['employee_id'], Worker.id != worker_id).first()
            if existing:
                return jsonify({'error': 'Employee ID already exists'}), 400
            worker.employee_id = data['employee_id']

        if 'first_name' in data:
            worker.first_name = data['first_name']
        if 'last_name' in data:
            worker.last_name = data['last_name']
        if 'email' in data:
            worker.email = data['email']
        if 'phone' in data:
            worker.phone = data['phone']
        if 'address' in data:
            worker.address = data['address']
        if 'cnic' in data:
            # Check if new CNIC already exists (excluding current worker)
            existing = Worker.query.filter(Worker.cnic == data['cnic'], Worker.id != worker_id).first()
            if existing:
                return jsonify({'error': 'CNIC already exists'}), 400
            worker.cnic = data['cnic']
        if 'date_of_birth' in data:
            worker.date_of_birth = datetime.strptime(data['date_of_birth'], '%Y-%m-%d').date()
        if 'hire_date' in data:
            worker.hire_date = datetime.strptime(data['hire_date'], '%Y-%m-%d').date()
        if 'position' in data:
            worker.position = data['position']
        if 'department' in data:
            worker.department = data['department']
        if 'salary' in data:
            worker.salary = float(data['salary']) if data['salary'] else None
        if 'status' in data:
            worker.status = data['status']
        if 'emergency_contact_name' in data:
            worker.emergency_contact_name = data['emergency_contact_name']
        if 'emergency_contact_phone' in data:
            worker.emergency_contact_phone = data['emergency_contact_phone']
        if 'notes' in data:
            worker.notes = data['notes']

        worker.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({
            'message': 'Worker updated successfully',
            'worker': worker.to_dict()
        })

    except ValueError as e:
        db.session.rollback()
        logger.error(f"Invalid date format: {e}")
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating worker {worker_id}: {e}")
        return jsonify({'error': 'Failed to update worker'}), 500

@hr_bp.route('/api/workers/<int:worker_id>', methods=['DELETE'])
@role_required(['admin', 'accountant'])
def delete_worker(worker_id):
    """Delete a worker"""
    try:
        worker = Worker.query.get(worker_id)
        if not worker:
            return jsonify({'error': 'Worker not found'}), 404

        db.session.delete(worker)
        db.session.commit()

        return jsonify({'message': 'Worker deleted successfully'})

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting worker {worker_id}: {e}")
        return jsonify({'error': 'Failed to delete worker'}), 500

@hr_bp.route('/api/workers/departments', methods=['GET'])
@role_required(['admin', 'accountant', 'inventory_manager'])
def get_departments():
    """Get list of all departments"""
    try:
        departments = db.session.query(Worker.department).distinct().all()
        department_list = [dept[0] for dept in departments if dept[0]]
        return jsonify({'departments': sorted(department_list)})

    except Exception as e:
        logger.error(f"Error fetching departments: {e}")
        return jsonify({'error': 'Failed to fetch departments'}), 500

@hr_bp.route('/api/workers/positions', methods=['GET'])
@role_required(['admin', 'accountant', 'inventory_manager'])
def get_positions():
    """Get list of all positions"""
    try:
        positions = db.session.query(Worker.position).distinct().all()
        position_list = [pos[0] for pos in positions if pos[0]]
        return jsonify({'positions': sorted(position_list)})

    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        return jsonify({'error': 'Failed to fetch positions'}), 500

@hr_bp.route('/api/workers/debug', methods=['GET'])
@role_required(['admin'])
def debug_workers():
    """Debug endpoint to help diagnose worker endpoint issues"""
    try:
        debug_info = {}
        
        # Test database connection
        try:
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
            debug_info['database_connection'] = 'OK'
        except Exception as e:
            debug_info['database_connection'] = f'ERROR: {str(e)}'
        
        # Test Worker model
        try:
            worker_count = Worker.query.count()
            debug_info['worker_count'] = worker_count
            debug_info['worker_model'] = 'OK'
        except Exception as e:
            debug_info['worker_model'] = f'ERROR: {str(e)}'
        
        # Test JWT token
        try:
            current_user_id = get_jwt_identity()
            debug_info['jwt_user_id'] = current_user_id
            debug_info['jwt_token'] = 'OK'
        except Exception as e:
            debug_info['jwt_token'] = f'ERROR: {str(e)}'
        
        # Test user lookup
        try:
            current_user_id = get_jwt_identity()
            user = User.query.get(int(current_user_id))
            if user:
                debug_info['user_lookup'] = f'OK - User: {user.username}, Role: {user.role}'
            else:
                debug_info['user_lookup'] = 'ERROR: User not found'
        except Exception as e:
            debug_info['user_lookup'] = f'ERROR: {str(e)}'
        
        return jsonify(debug_info)
        
    except Exception as e:
        logger.error(f"Error in debug endpoint: {e}", exc_info=True)
        return jsonify({'error': f'Debug failed: {str(e)}'}), 500

@hr_bp.route('/api/workers/test-auth', methods=['GET'])
@jwt_required()
def test_auth():
    """Simple test endpoint to check JWT authentication"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))
        
        if not user:
            return jsonify({'error': 'User not found'}), 401
            
        return jsonify({
            'message': 'Authentication successful',
            'user_id': current_user_id,
            'username': user.username,
            'role': user.role
        })
        
    except Exception as e:
        logger.error(f"Error in test auth endpoint: {e}", exc_info=True)
        return jsonify({'error': f'Auth test failed: {str(e)}'}), 500
