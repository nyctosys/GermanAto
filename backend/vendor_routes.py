from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Vendor, VendorLedger, VendorConsignment, User
from datetime import datetime, date
from functools import wraps
import logging

# Create blueprint for vendor routes
vendor_bp = Blueprint('vendor', __name__)

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
            current_user_id = get_jwt_identity()
            user = User.query.get(int(current_user_id))
            
            if not user or not user.is_active:
                return jsonify({'error': 'User not found or inactive'}), 401
            
            # Convert to list if string
            roles_list = [required_roles] if isinstance(required_roles, str) else required_roles
            
            if user.role not in roles_list:
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ===== VENDOR MANAGEMENT ROUTES =====

@vendor_bp.route('/vendors')
def vendors_page():
    """Vendor management page"""
    return send_from_directory('frontend', 'vendors.html')

@vendor_bp.route('/vendors/<int:vendor_id>')
def vendor_detail(vendor_id):
    """Vendor detail page with ledger and consignment tabs"""
    vendor = Vendor.query.get_or_404(vendor_id)
    return send_from_directory('frontend', 'vendor_detail.html')

@vendor_bp.route('/api/vendors', methods=['GET'])
@role_required(['admin', 'accountant'])
def get_vendors():
    """Get all vendors with optional search"""
    try:
        search_query = request.args.get('search', '').strip()
        
        query = Vendor.query
        
        if search_query:
            query = query.filter(
                db.or_(
                    Vendor.name.ilike(f'%{search_query}%'),
                    Vendor.company_name.ilike(f'%{search_query}%'),
                    Vendor.contact_person.ilike(f'%{search_query}%'),
                    Vendor.phone.ilike(f'%{search_query}%'),
                    Vendor.email.ilike(f'%{search_query}%')
                )
            )
        
        vendors = query.order_by(Vendor.created_at.desc()).all()
        
        return jsonify([vendor.to_dict() for vendor in vendors]), 200
        
    except Exception as e:
        logger.error(f"Error fetching vendors: {e}")
        return jsonify({'error': 'Failed to fetch vendors'}), 500

@vendor_bp.route('/api/vendors/<int:vendor_id>', methods=['GET'])
@role_required(['admin', 'accountant'])
def get_vendor(vendor_id):
    """Get specific vendor by ID"""
    try:
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return jsonify({'error': 'Vendor not found'}), 404
        
        return jsonify(vendor.to_dict()), 200
        
    except Exception as e:
        logger.error(f"Error fetching vendor {vendor_id}: {e}")
        return jsonify({'error': 'Failed to fetch vendor'}), 500

@vendor_bp.route('/api/vendors', methods=['POST'])
@role_required(['admin', 'accountant'])
def create_vendor():
    """Create a new vendor"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['name', 'company_name', 'contact_person', 'phone', 'address']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check for duplicate vendor (same name + company + phone)
        existing_vendor = Vendor.query.filter_by(
            name=data['name'],
            company_name=data['company_name'],
            phone=data['phone']
        ).first()
        
        if existing_vendor:
            return jsonify({
                'error': 'Vendor already exists',
                'details': f'A vendor with the same name ({data["name"]}), company ({data["company_name"]}), and phone ({data["phone"]}) already exists.',
                'existing_vendor_id': existing_vendor.id
            }), 409
        
        # Create new vendor
        vendor = Vendor(
            name=data['name'],
            company_name=data['company_name'],
            contact_person=data['contact_person'],
            phone=data['phone'],
            email=data.get('email'),
            address=data['address'],
            cnic=data.get('cnic')
        )
        
        db.session.add(vendor)
        db.session.commit()
        
        logger.info(f"Vendor created successfully: ID {vendor.id}")
        
        return jsonify({
            'message': 'Vendor created successfully',
            'vendor': vendor.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating vendor: {e}")
        return jsonify({'error': 'Failed to create vendor'}), 500

@vendor_bp.route('/api/vendors/<int:vendor_id>', methods=['PUT'])
@role_required(['admin', 'accountant'])
def update_vendor(vendor_id):
    """Update an existing vendor"""
    try:
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return jsonify({'error': 'Vendor not found'}), 404
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Update fields
        vendor.name = data.get('name', vendor.name)
        vendor.company_name = data.get('company_name', vendor.company_name)
        vendor.contact_person = data.get('contact_person', vendor.contact_person)
        vendor.phone = data.get('phone', vendor.phone)
        vendor.email = data.get('email', vendor.email)
        vendor.address = data.get('address', vendor.address)
        vendor.cnic = data.get('cnic', vendor.cnic)
        vendor.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        logger.info(f"Vendor updated successfully: ID {vendor.id}")
        
        return jsonify({
            'message': 'Vendor updated successfully',
            'vendor': vendor.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating vendor {vendor_id}: {e}")
        return jsonify({'error': 'Failed to update vendor'}), 500

@vendor_bp.route('/api/vendors/<int:vendor_id>', methods=['DELETE'])
@role_required(['admin', 'accountant'])
def delete_vendor(vendor_id):
    """Delete a vendor"""
    try:
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return jsonify({'error': 'Vendor not found'}), 404
        
        # Delete associated ledger entries and consignments (cascade should handle this)
        db.session.delete(vendor)
        db.session.commit()
        
        logger.info(f"Vendor deleted successfully: ID {vendor.id}")
        
        return jsonify({'message': 'Vendor deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting vendor {vendor_id}: {e}")
        return jsonify({'error': 'Failed to delete vendor'}), 500

# ===== VENDOR LEDGER ROUTES =====

@vendor_bp.route('/api/vendors/<int:vendor_id>/ledger', methods=['GET'])
@role_required(['admin', 'accountant'])
def get_vendor_ledger(vendor_id):
    """Get ledger entries for a specific vendor"""
    try:
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return jsonify({'error': 'Vendor not found'}), 404
        
        # Get date range filters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        query = VendorLedger.query.filter_by(vendor_id=vendor_id)
        
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(VendorLedger.date >= start_date_obj)
            except ValueError:
                return jsonify({'error': 'Invalid start_date format. Use YYYY-MM-DD'}), 400
        
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(VendorLedger.date <= end_date_obj)
            except ValueError:
                return jsonify({'error': 'Invalid end_date format. Use YYYY-MM-DD'}), 400
        
        ledger_entries = query.order_by(VendorLedger.date.desc(), VendorLedger.id.desc()).all()
        
        return jsonify([entry.to_dict() for entry in ledger_entries]), 200
        
    except Exception as e:
        logger.error(f"Error fetching vendor ledger {vendor_id}: {e}")
        return jsonify({'error': 'Failed to fetch vendor ledger'}), 500

@vendor_bp.route('/api/ledger/add', methods=['POST'])
@role_required(['admin', 'accountant'])
def add_ledger_entry():
    """Add a new ledger entry"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['vendor_id', 'date', 'description', 'debit', 'credit']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Validate vendor exists
        vendor = Vendor.query.get(data['vendor_id'])
        if not vendor:
            return jsonify({'error': 'Vendor not found'}), 404
        
        # Parse date
        try:
            entry_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        # Convert amounts to decimal
        debit = float(data['debit']) if data['debit'] else 0.0
        credit = float(data['credit']) if data['credit'] else 0.0
        
        # Get the last balance for this vendor
        last_entry = VendorLedger.query.filter_by(vendor_id=data['vendor_id'])\
            .order_by(VendorLedger.date.desc(), VendorLedger.id.desc()).first()
        
        last_balance = float(last_entry.balance) if last_entry else 0.0
        
        # Calculate new balance
        new_balance = last_balance + debit - credit
        
        # Create ledger entry
        ledger_entry = VendorLedger(
            vendor_id=data['vendor_id'],
            date=entry_date,
            description=data['description'],
            folio=data.get('folio'),
            debit=debit,
            credit=credit,
            balance=new_balance
        )
        
        db.session.add(ledger_entry)
        db.session.commit()
        
        logger.info(f"Ledger entry created successfully for vendor {data['vendor_id']}")
        
        return jsonify({
            'message': 'Ledger entry added successfully',
            'entry': ledger_entry.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding ledger entry: {e}")
        return jsonify({'error': 'Failed to add ledger entry'}), 500

@vendor_bp.route('/api/ledger/<int:ledger_id>', methods=['DELETE'])
@role_required(['admin', 'accountant'])
def delete_ledger_entry(ledger_id):
    """Delete a ledger entry"""
    try:
        ledger_entry = VendorLedger.query.get(ledger_id)
        if not ledger_entry:
            return jsonify({'error': 'Ledger entry not found'}), 404
        
        vendor_id = ledger_entry.vendor_id
        
        # Delete the ledger entry
        db.session.delete(ledger_entry)
        db.session.commit()
        
        logger.info(f"Ledger entry {ledger_id} deleted successfully")
        
        return jsonify({'message': 'Ledger entry deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting ledger entry: {e}")
        return jsonify({'error': 'Failed to delete ledger entry'}), 500

# ===== VENDOR CONSIGNMENT ROUTES =====

@vendor_bp.route('/api/vendors/<int:vendor_id>/consignments', methods=['GET'])
@role_required(['admin', 'accountant'])
def get_vendor_consignments(vendor_id):
    """Get consignment records for a specific vendor"""
    try:
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return jsonify({'error': 'Vendor not found'}), 404
        
        # Get filters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        invoice_no = request.args.get('invoice_no')
        
        query = VendorConsignment.query.filter_by(vendor_id=vendor_id)
        
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(VendorConsignment.date >= start_date_obj)
            except ValueError:
                return jsonify({'error': 'Invalid start_date format. Use YYYY-MM-DD'}), 400
        
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(VendorConsignment.date <= end_date_obj)
            except ValueError:
                return jsonify({'error': 'Invalid end_date format. Use YYYY-MM-DD'}), 400
        
        if invoice_no:
            query = query.filter(VendorConsignment.invoice_no.ilike(f'%{invoice_no}%'))
        
        consignments = query.order_by(VendorConsignment.date.desc(), VendorConsignment.id.desc()).all()
        
        return jsonify([consignment.to_dict() for consignment in consignments]), 200
        
    except Exception as e:
        logger.error(f"Error fetching vendor consignments {vendor_id}: {e}")
        return jsonify({'error': 'Failed to fetch vendor consignments'}), 500

@vendor_bp.route('/api/consignments/add', methods=['POST'])
@role_required(['admin', 'accountant'])
def add_consignment():
    """Add a new consignment record"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['vendor_id', 'date', 'invoice_no', 'item_name', 'quantity', 'rate']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Validate vendor exists
        vendor = Vendor.query.get(data['vendor_id'])
        if not vendor:
            return jsonify({'error': 'Vendor not found'}), 404
        
        # Parse date
        try:
            consignment_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        # Calculate amount
        quantity = int(data['quantity'])
        rate = float(data['rate'])
        amount = quantity * rate
        
        # Create consignment record
        consignment = VendorConsignment(
            vendor_id=data['vendor_id'],
            date=consignment_date,
            invoice_no=data['invoice_no'],
            item_name=data['item_name'],
            quantity=quantity,
            rate=rate,
            amount=amount,
            remarks=data.get('remarks')
        )
        
        db.session.add(consignment)
        db.session.commit()
        
        logger.info(f"Consignment record created successfully for vendor {data['vendor_id']}")
        
        return jsonify({
            'message': 'Consignment record added successfully',
            'consignment': consignment.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding consignment record: {e}")
        return jsonify({'error': 'Failed to add consignment record'}), 500

@vendor_bp.route('/api/consignments/<int:consignment_id>', methods=['DELETE'])
@role_required(['admin', 'accountant'])
def delete_consignment(consignment_id):
    """Delete a consignment record"""
    try:
        consignment = VendorConsignment.query.get(consignment_id)
        if not consignment:
            return jsonify({'error': 'Consignment record not found'}), 404
        
        db.session.delete(consignment)
        db.session.commit()
        
        logger.info(f"Consignment record deleted successfully: ID {consignment_id}")
        
        return jsonify({'message': 'Consignment record deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting consignment {consignment_id}: {e}")
        return jsonify({'error': 'Failed to delete consignment record'}), 500
