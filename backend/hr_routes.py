from flask import Blueprint, request, jsonify, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Worker, User, AttendanceRecord, ZKTecoDevice
from datetime import datetime, date, time, timedelta
from functools import wraps
from sqlalchemy import func, and_
from collections import defaultdict
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


@hr_bp.route('/hr/device-management')
def device_management_page():
    """ZKTeco device management page (pull method)."""
    return send_from_directory('frontend', 'device-management.html')


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


# ===== ATTENDANCE ROUTES =====

@hr_bp.route('/api/attendance', methods=['GET'])
@role_required(['admin', 'accountant', 'inventory_manager'])
def get_attendance():
    """List attendance records with optional worker_id, start_date, end_date"""
    try:
        worker_id = request.args.get('worker_id', type=int)
        start_date_str = request.args.get('start_date', '').strip()
        end_date_str = request.args.get('end_date', '').strip()

        query = AttendanceRecord.query.order_by(AttendanceRecord.date.desc(), AttendanceRecord.check_in_time.desc())

        if worker_id:
            query = query.filter(AttendanceRecord.worker_id == worker_id)
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                query = query.filter(AttendanceRecord.date >= start_date)
            except ValueError:
                pass
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                query = query.filter(AttendanceRecord.date <= end_date)
            except ValueError:
                pass

        records = query.all()
        # Include worker name for display
        out = []
        for r in records:
            d = r.to_dict()
            if r.worker:
                d['worker_name'] = f"{r.worker.first_name or ''} {r.worker.last_name or ''}".strip() or r.worker.employee_id
                d['employee_id'] = r.worker.employee_id
            out.append(d)
        return jsonify({'attendance': out, 'total': len(out)})
    except Exception as e:
        logger.error(f"Error fetching attendance: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch attendance'}), 500


@hr_bp.route('/api/attendance', methods=['POST'])
@role_required(['admin', 'accountant'])
def create_attendance():
    """Create an attendance record (manual entry)."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        worker_id = data.get('worker_id')
        date_str = data.get('date')
        check_in = data.get('check_in_time')
        check_out = data.get('check_out_time')
        notes = data.get('notes', '').strip()

        if not worker_id or not date_str:
            return jsonify({'error': 'worker_id and date are required'}), 400

        worker = Worker.query.get(worker_id)
        if not worker:
            return jsonify({'error': 'Worker not found'}), 404

        try:
            att_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format (use YYYY-MM-DD)'}), 400

        check_in_time = None
        if check_in:
            try:
                if isinstance(check_in, str) and len(check_in) <= 5:
                    h, m = map(int, check_in.split(':'))
                    check_in_time = datetime.combine(att_date, time(h, m))
                else:
                    check_in_time = datetime.strptime(check_in, '%H:%M').time()
                    check_in_time = datetime.combine(att_date, check_in_time)
            except (ValueError, TypeError):
                pass

        check_out_time = None
        if check_out:
            try:
                if isinstance(check_out, str) and len(check_out) <= 5:
                    h, m = map(int, check_out.split(':'))
                    check_out_time = datetime.combine(att_date, time(h, m))
                else:
                    check_out_time = datetime.strptime(check_out, '%H:%M').time()
                    check_out_time = datetime.combine(att_date, check_out_time)
            except (ValueError, TypeError):
                pass

        work_hours = None
        if check_in_time and check_out_time and check_out_time > check_in_time:
            delta = check_out_time - check_in_time
            work_hours = delta.total_seconds() / 3600.0

        record = AttendanceRecord(
            worker_id=worker_id,
            date=att_date,
            check_in_time=check_in_time,
            check_out_time=check_out_time,
            work_hours=work_hours,
            notes=notes or None
        )
        db.session.add(record)
        db.session.commit()
        out = record.to_dict()
        out['worker_name'] = f"{worker.first_name or ''} {worker.last_name or ''}".strip() or worker.employee_id
        out['employee_id'] = worker.employee_id
        return jsonify({'message': 'Attendance record created', 'attendance': out}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating attendance: {e}", exc_info=True)
        return jsonify({'error': 'Failed to create attendance'}), 500


@hr_bp.route('/api/attendance/<int:record_id>', methods=['PUT'])
@role_required(['admin', 'accountant'])
def update_attendance(record_id):
    """Update an attendance record."""
    try:
        record = AttendanceRecord.query.get(record_id)
        if not record:
            return jsonify({'error': 'Attendance record not found'}), 404
        data = request.get_json() or {}
        date_str = data.get('date')
        check_in = data.get('check_in_time')
        check_out = data.get('check_out_time')
        notes = data.get('notes')

        if date_str:
            try:
                record.date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        if check_in is not None:
            try:
                if isinstance(check_in, str) and len(check_in) <= 5:
                    h, m = map(int, check_in.split(':'))
                    record.check_in_time = datetime.combine(record.date, time(h, m))
                else:
                    t = datetime.strptime(check_in, '%H:%M').time()
                    record.check_in_time = datetime.combine(record.date, t)
            except (ValueError, TypeError):
                record.check_in_time = None
        if check_out is not None:
            try:
                if isinstance(check_out, str) and len(check_out) <= 5:
                    h, m = map(int, check_out.split(':'))
                    record.check_out_time = datetime.combine(record.date, time(h, m))
                else:
                    t = datetime.strptime(check_out, '%H:%M').time()
                    record.check_out_time = datetime.combine(record.date, t)
            except (ValueError, TypeError):
                record.check_out_time = None
        if notes is not None:
            record.notes = notes.strip() or None

        if record.check_in_time and record.check_out_time and record.check_out_time > record.check_in_time:
            record.work_hours = (record.check_out_time - record.check_in_time).total_seconds() / 3600.0
        else:
            record.work_hours = None

        db.session.commit()
        out = record.to_dict()
        if record.worker:
            out['worker_name'] = f"{record.worker.first_name or ''} {record.worker.last_name or ''}".strip() or record.worker.employee_id
            out['employee_id'] = record.worker.employee_id
        return jsonify({'message': 'Attendance updated', 'attendance': out})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating attendance: {e}", exc_info=True)
        return jsonify({'error': 'Failed to update attendance'}), 500


@hr_bp.route('/api/attendance/<int:record_id>', methods=['DELETE'])
@role_required(['admin', 'accountant'])
def delete_attendance(record_id):
    """Delete an attendance record."""
    try:
        record = AttendanceRecord.query.get(record_id)
        if not record:
            return jsonify({'error': 'Attendance record not found'}), 404
        db.session.delete(record)
        db.session.commit()
        return jsonify({'message': 'Attendance record deleted'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting attendance: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete attendance'}), 500


@hr_bp.route('/api/attendance/summary', methods=['GET'])
@role_required(['admin', 'accountant', 'inventory_manager'])
def get_attendance_summary():
    """Get attendance summary for a worker in a month (days_worked, total_hours). Used for salary calculation."""
    try:
        worker_id = request.args.get('worker_id', type=int)
        month = request.args.get('month', type=int)
        year = request.args.get('year', type=int)
        if not worker_id or not month or not year:
            return jsonify({'error': 'worker_id, month, and year are required'}), 400
        if month < 1 or month > 12:
            return jsonify({'error': 'Invalid month'}), 400

        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        records = AttendanceRecord.query.filter(
            and_(
                AttendanceRecord.worker_id == worker_id,
                AttendanceRecord.date >= start_date,
                AttendanceRecord.date <= end_date)
        ).all()

        days_worked = len(set(r.date for r in records))
        total_hours = sum(r.work_hours or 0 for r in records)

        return jsonify({
            'worker_id': worker_id,
            'month': month,
            'year': year,
            'days_worked': days_worked,
            'total_hours': round(total_hours, 2),
            'records_count': len(records)
        })
    except Exception as e:
        logger.error(f"Error fetching attendance summary: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch summary'}), 500


@hr_bp.route('/api/salary/calculate', methods=['GET'])
@role_required(['admin', 'accountant', 'inventory_manager'])
def calculate_salary():
    """Calculate salary for a worker for a given month based on attendance. Returns net_salary, days_worked, total_hours."""
    try:
        worker_id = request.args.get('worker_id', type=int)
        month = request.args.get('month', type=int)
        year = request.args.get('year', type=int)
        if not worker_id or not month or not year:
            return jsonify({'error': 'worker_id, month, and year are required'}), 400

        worker = Worker.query.get(worker_id)
        if not worker:
            return jsonify({'error': 'Worker not found'}), 404

        base_salary = float(worker.salary) if worker.salary else 0

        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        records = AttendanceRecord.query.filter(
            and_(
                AttendanceRecord.worker_id == worker_id,
                AttendanceRecord.date >= start_date,
                AttendanceRecord.date <= end_date)
        ).all()

        days_worked = len(set(r.date for r in records))
        total_hours = sum(r.work_hours or 0 for r in records)

        # Salary = (base_salary / 30) * days_worked (proportional to days present)
        days_in_month = (end_date - start_date).days + 1
        daily_rate = base_salary / 30.0 if base_salary else 0
        net_salary = round(daily_rate * days_worked, 2)

        return jsonify({
            'worker_id': worker_id,
            'employee_id': worker.employee_id,
            'first_name': worker.first_name,
            'last_name': worker.last_name,
            'position': worker.position,
            'department': worker.department,
            'month': month,
            'year': year,
            'base_salary': base_salary,
            'days_worked': days_worked,
            'total_hours': round(total_hours, 2),
            'daily_rate': round(daily_rate, 2),
            'net_salary': net_salary,
            'deductions': 0,
            'bonuses': 0
        })
    except Exception as e:
        logger.error(f"Error calculating salary: {e}", exc_info=True)
        return jsonify({'error': 'Failed to calculate salary'}), 500


# ===== ZKTECO DEVICE API (pull via pyzk) =====

@hr_bp.route('/api/zkteco/devices', methods=['GET'])
@role_required(['admin', 'accountant', 'inventory_manager'])
def list_zkteco_devices():
    """List registered ZKTeco devices (pull method: IP + port)."""
    try:
        devices = ZKTecoDevice.query.filter_by(is_active=True).all()
        return jsonify({'devices': [d.to_dict() for d in devices]})
    except Exception as e:
        logger.error(f"Error listing ZKTeco devices: {e}", exc_info=True)
        return jsonify({'error': 'Failed to list devices'}), 500


@hr_bp.route('/api/zkteco/devices', methods=['POST'])
@role_required(['admin', 'accountant'])
def create_zkteco_device():
    """Register a ZKTeco device (pull). Requires IP and port; tests connection before adding."""
    try:
        from zkteco_service import test_connection
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        name = (data.get('name') or '').strip() or (data.get('ip_address') or '').strip()
        ip_address = (data.get('ip_address') or '').strip()
        port = int(data.get('port') or 4370)
        timeout = int(data.get('timeout') or 30)
        if not ip_address:
            return jsonify({'error': 'ip_address is required'}), 400
        ok, msg = test_connection(ip_address, port=port, timeout=min(timeout, 15))
        if not ok:
            return jsonify({'error': 'Cannot connect to device: ' + msg}), 400
        device = ZKTecoDevice(
            name=name or ip_address,
            serial_number=(data.get('serial_number') or '').strip() or None,
            ip_address=ip_address,
            port=port,
            timeout=timeout,
            is_active=True
        )
        db.session.add(device)
        db.session.commit()
        return jsonify({'message': 'Device added', 'device': device.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating ZKTeco device: {e}", exc_info=True)
        return jsonify({'error': 'Failed to add device'}), 500


@hr_bp.route('/api/zkteco/devices/<int:device_id>', methods=['DELETE'])
@role_required(['admin', 'accountant'])
def delete_zkteco_device(device_id):
    """Remove a ZKTeco device (soft-delete: set is_active=False)."""
    try:
        device = ZKTecoDevice.query.get(device_id)
        if not device:
            return jsonify({'error': 'Device not found'}), 404
        device.is_active = False
        db.session.commit()
        return jsonify({'message': 'Device removed'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error removing ZKTeco device: {e}", exc_info=True)
        return jsonify({'error': 'Failed to remove device'}), 500


@hr_bp.route('/api/zkteco/devices/<int:device_id>/test', methods=['POST'])
@role_required(['admin', 'accountant', 'inventory_manager'])
def test_zkteco_device(device_id):
    """Test connection to a registered ZKTeco device (pull)."""
    try:
        from zkteco_service import test_connection
        device = ZKTecoDevice.query.get(device_id)
        if not device:
            return jsonify({'error': 'Device not found'}), 404
        if not device.ip_address or device.port is None:
            return jsonify({'success': False, 'message': 'Device has no IP/port configured (pull method requires IP and port)'}), 400
        ok, msg = test_connection(device.ip_address, port=device.port, timeout=min(device.timeout, 15))
        return jsonify({'success': ok, 'message': msg})
    except Exception as e:
        logger.error(f"Error testing device: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)})


@hr_bp.route('/api/zkteco/devices/<int:device_id>/sync', methods=['POST'])
@role_required(['admin', 'accountant'])
def sync_zkteco_attendance(device_id):
    """Sync attendance from ZKTeco device (pull). Matches device user_id to Worker.employee_id."""
    try:
        from zkteco_service import get_attendance_logs
        device = ZKTecoDevice.query.get(device_id)
        if not device:
            return jsonify({'error': 'Device not found'}), 404
        if not device.ip_address or device.port is None:
            return jsonify({'error': 'Device has no IP/port (pull method requires IP and port)'}), 400
        data = request.get_json() or {}
        start_date_str = (data.get('start_date') or '').strip()
        end_date_str = (data.get('end_date') or '').strip()
        start_date = None
        end_date = None
        if start_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        if end_date_str:
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        logs = get_attendance_logs(
            device.ip_address,
            port=device.port,
            timeout=device.timeout,
            start_date=start_date,
            end_date=end_date,
        )
        if not logs:
            device.last_sync = datetime.utcnow()
            device.last_sync_status = 'ok_no_logs'
            db.session.commit()
            return jsonify({
                'message': 'No attendance logs in range (or device returned none)',
                'synced': 0,
                'created': 0,
                'updated': 0,
                'skipped_unknown_user': 0
            })
        workers_by_emp = {w.employee_id: w for w in Worker.query.all() if w.employee_id}
        by_user_date = defaultdict(list)
        for log in logs:
            uid = (log.get('user_id') or '').strip()
            if not uid:
                continue
            d = log.get('date')
            ts = log.get('timestamp')
            if not d or not ts:
                continue
            by_user_date[(uid, d)].append(ts)
        created = 0
        updated = 0
        skipped_unknown = 0
        for (user_id, att_date), timestamps in by_user_date.items():
            worker = workers_by_emp.get(user_id)
            if not worker:
                skipped_unknown += 1
                continue
            timestamps.sort()
            check_in_time = timestamps[0]
            check_out_time = timestamps[-1] if len(timestamps) > 1 else None
            work_hours = None
            if check_out_time and check_in_time and check_out_time > check_in_time:
                delta = check_out_time - check_in_time
                work_hours = round(delta.total_seconds() / 3600.0, 2)
            existing = AttendanceRecord.query.filter_by(worker_id=worker.id, date=att_date).first()
            if existing:
                existing.check_in_time = check_in_time
                existing.check_out_time = check_out_time
                existing.work_hours = work_hours
                existing.notes = existing.notes or 'ZKTeco sync'
                updated += 1
            else:
                record = AttendanceRecord(
                    worker_id=worker.id,
                    date=att_date,
                    check_in_time=check_in_time,
                    check_out_time=check_out_time,
                    work_hours=work_hours,
                    notes='ZKTeco sync'
                )
                db.session.add(record)
                created += 1
        device.last_sync = datetime.utcnow()
        device.last_sync_status = 'ok'
        db.session.commit()
        return jsonify({
            'message': 'Sync completed',
            'synced': len(by_user_date),
            'created': created,
            'updated': updated,
            'skipped_unknown_user': skipped_unknown
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error syncing ZKTeco: {e}", exc_info=True)
        if device_id:
            try:
                dev = ZKTecoDevice.query.get(device_id)
                if dev:
                    dev.last_sync_status = 'error'
                    db.session.commit()
            except Exception:
                pass
        return jsonify({'error': 'Sync failed: ' + str(e)}), 500
