from flask import Blueprint, request, jsonify, send_from_directory, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Worker, User, AttendanceRecord, ZKTecoDevice
from datetime import datetime, date, time, timedelta
from functools import wraps
from sqlalchemy import func, and_
from sqlalchemy.exc import IntegrityError
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
            notes=notes or None,
            source="manual",
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


# ===== ZKTECO PUSH PROTOCOL (device sends data to server; no auth) =====

def _iclock_ok():
    """Return 200 OK with plain text body for ZKTeco device."""
    return Response("OK", status=200, mimetype="text/plain; charset=utf-8")


def _update_device_last_seen(sn):
    """Update last_seen_at for device with given serial_number. Swallow errors."""
    if not sn or not str(sn).strip():
        return
    try:
        device = ZKTecoDevice.query.filter_by(serial_number=sn.strip(), is_active=True).first()
        if device:
            device.last_seen_at = datetime.utcnow()
            db.session.commit()
    except Exception as e:
        logger.warning("Could not update ZKTecoDevice last_seen_at for SN=%s: %s", sn, e)
        try:
            db.session.rollback()
        except Exception:
            pass


@hr_bp.route('/iclock/getrequest', methods=['GET'])
def iclock_getrequest():
    """ZKTeco device heartbeat. No auth. Update last_seen_at and return OK."""
    try:
        sn = request.args.get("SN", "").strip()
        if sn:
            _update_device_last_seen(sn)
        return _iclock_ok()
    except Exception as e:
        logger.error("iclock/getrequest error: %s", e, exc_info=True)
        return _iclock_ok()


@hr_bp.route('/iclock/cdata', methods=['GET', 'POST'])
def iclock_cdata():
    """ZKTeco device push (options, ATTLOG, OPERLOG, etc.). No auth. Persist ATTLOG to AttendanceRecord."""
    try:
        sn = request.args.get("SN", "").strip()
        table = request.args.get("table", "").strip()
        if sn:
            _update_device_last_seen(sn)
        if request.method == "GET":
            return _iclock_ok()
        body = request.get_data(as_text=True) or ""
        if not body.strip():
            return _iclock_ok()
        if table == "ATTLOG":
            _process_attlog(body, sn)
        else:
            logger.debug("iclock/cdata table=%s SN=%s (not ATTLOG, no DB write)", table, sn)
        return _iclock_ok()
    except Exception as e:
        logger.error("iclock/cdata error: %s", e, exc_info=True)
        try:
            db.session.rollback()
        except Exception:
            pass
        return _iclock_ok()


def _process_attlog(body, sn):
    """Parse ATTLOG body (tab-separated: user_id, timestamp, punch) and merge into AttendanceRecord."""
    workers_by_emp = {w.employee_id: w for w in Worker.query.all() if w.employee_id}
    zkteco_device_id = None
    if sn:
        dev = ZKTecoDevice.query.filter_by(serial_number=sn.strip(), is_active=True).first()
        if dev:
            zkteco_device_id = dev.id
    TIMESTAMP_FMT = "%Y-%m-%d %H:%M:%S"
    for line in body.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            logger.warning("ATTLOG invalid line (expected at least 3 fields): %s", line[:100])
            continue
        user_id = (parts[0] or "").strip()
        ts_str = (parts[1] or "").strip()
        punch = (parts[2] or "").strip()
        if punch not in ("0", "1", "255"):
            logger.warning("ATTLOG invalid punch (expected 0, 1, or 255): user_id=%s punch=%s", user_id, punch)
            continue
        try:
            ts = datetime.strptime(ts_str, TIMESTAMP_FMT)
        except ValueError:
            logger.warning("ATTLOG invalid timestamp: user_id=%s ts=%s", user_id, ts_str)
            continue
        worker = workers_by_emp.get(user_id)
        if not worker:
            logger.warning("ATTLOG unknown user_id=%s SN=%s (no Worker with this employee_id)", user_id, sn)
            continue
        att_date = ts.date()
        record = AttendanceRecord.query.filter_by(worker_id=worker.id, date=att_date).first()
        if not record:
            record = AttendanceRecord(
                worker_id=worker.id,
                date=att_date,
                check_in_time=None,
                check_out_time=None,
                work_hours=None,
                notes="ZKTeco push",
                source="ZKTeco push",
                zkteco_device_id=zkteco_device_id,
            )
            db.session.add(record)
        if punch == "0":
            if record.check_in_time is None or ts < record.check_in_time:
                record.check_in_time = ts
        elif punch == "1":
            if record.check_out_time is None or ts > record.check_out_time:
                record.check_out_time = ts
        else:
            # Some ZKTeco setups send 255 for generic punch (no explicit in/out).
            # Fallback: earliest punch becomes check-in, later punch becomes check-out.
            if record.check_in_time is None:
                record.check_in_time = ts
            elif ts < record.check_in_time:
                record.check_in_time = ts
            elif record.check_out_time is None or ts > record.check_out_time:
                record.check_out_time = ts
        if record.check_in_time and record.check_out_time and record.check_out_time > record.check_in_time:
            delta = record.check_out_time - record.check_in_time
            record.work_hours = round(delta.total_seconds() / 3600.0, 2)
        else:
            record.work_hours = None
        record.notes = record.notes or "ZKTeco push"
        record.source = record.source or "ZKTeco push"
        record.zkteco_device_id = zkteco_device_id
    db.session.commit()


# ===== ZKTECO DEVICE API (PUSH: register by serial number) =====

@hr_bp.route('/api/zkteco/devices', methods=['GET'])
@role_required(['admin', 'accountant', 'inventory_manager'])
def list_zkteco_devices():
    """List registered ZKTeco devices (PUSH: identified by serial number)."""
    try:
        devices = ZKTecoDevice.query.filter_by(is_active=True).all()
        return jsonify({'devices': [d.to_dict() for d in devices]})
    except Exception as e:
        logger.error(f"Error listing ZKTeco devices: {e}", exc_info=True)
        return jsonify({'error': 'Failed to list devices'}), 500


@hr_bp.route('/api/zkteco/devices', methods=['POST'])
@role_required(['admin', 'accountant'])
def create_zkteco_device():
    """Register a ZKTeco device (PUSH). Requires serial_number; set Cloud Server on device to this server."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body required'}), 400
        serial_number = (data.get('serial_number') or '').strip()
        if not serial_number:
            return jsonify({'error': 'serial_number is required'}), 400
        name = (data.get('name') or '').strip() or serial_number
        ip_address = (data.get('ip_address') or '').strip() or None
        port = data.get('port')
        if port is not None:
            try:
                port = int(port)
            except (TypeError, ValueError):
                port = None
        timeout = 30
        if data.get('timeout') is not None:
            try:
                timeout = max(5, min(120, int(data.get('timeout'))))
            except (TypeError, ValueError):
                pass
        existing = ZKTecoDevice.query.filter_by(serial_number=serial_number).first()
        if existing:
            if existing.is_active:
                return jsonify({'error': 'A device with this serial number is already registered'}), 400
            existing.name = name
            existing.ip_address = ip_address
            existing.port = port
            existing.timeout = timeout
            existing.is_active = True
            db.session.commit()
            return jsonify({'message': 'Device re-added', 'device': existing.to_dict()}), 201
        device = ZKTecoDevice(
            name=name,
            serial_number=serial_number,
            ip_address=ip_address,
            port=port,
            timeout=timeout,
            is_active=True,
        )
        db.session.add(device)
        db.session.commit()
        return jsonify({'message': 'Device added', 'device': device.to_dict()}), 201
    except IntegrityError as e:
        db.session.rollback()
        logger.warning("ZKTeco device create IntegrityError (duplicate SN?): %s", e)
        return jsonify({'error': 'A device with this serial number already exists'}), 400
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
