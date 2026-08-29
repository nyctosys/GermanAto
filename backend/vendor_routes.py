from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, send_from_directory
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Vendor, VendorLedger, PurchaseOrder, User
from datetime import datetime, date
from functools import wraps
from log_utils import log_action, save_uploaded_file
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
        
        current_user = None
        current_user_id = get_jwt_identity()
        if current_user_id:
            current_user = User.query.get(int(current_user_id))
            
        log_action(current_user, 'CREATE', 'vendors', vendor.id, f"Created vendor {vendor.name} ({vendor.company_name})")
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
        
        current_user = None
        current_user_id = get_jwt_identity()
        if current_user_id:
            current_user = User.query.get(int(current_user_id))
            
        log_action(current_user, 'UPDATE', 'vendors', vendor.id, f"Updated vendor details for {vendor.name}")
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
        current_user = None
        current_user_id = get_jwt_identity()
        if current_user_id:
            current_user = User.query.get(int(current_user_id))
            
        log_action(current_user, 'DELETE', 'vendors', vendor_id, f"Deleted vendor ID {vendor_id} ({vendor.name})")
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
        # Check if multipart/form-data or JSON
        data = {}
        attachment_file = None
        
        if request.content_type and 'multipart/form-data' in request.content_type:
            data = request.form
            if 'attachment' in request.files:
                attachment_file = request.files['attachment']
        else:
            data = request.get_json()
            
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['vendor_id', 'date', 'description', 'debit', 'credit']
        for field in required_fields:
            if field not in data or data.get(field) is None:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Parse vendor_id
        try:
            vendor_id = int(data['vendor_id'])
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid vendor_id'}), 400
            
        # Validate vendor exists
        vendor = Vendor.query.get(vendor_id)
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
        last_entry = VendorLedger.query.filter_by(vendor_id=vendor_id)\
            .order_by(VendorLedger.date.desc(), VendorLedger.id.desc()).first()
        
        last_balance = float(last_entry.balance) if last_entry else 0.0
        
        # Calculate new balance
        new_balance = last_balance + debit - credit
        
        # Save optional attachment
        attachment_path = None
        if attachment_file:
            attachment_path = save_uploaded_file(attachment_file)
            
        # Get current user
        current_user = None
        current_user_id = get_jwt_identity()
        if current_user_id:
            current_user = User.query.get(int(current_user_id))
            
        # Create ledger entry
        ledger_entry = VendorLedger(
            vendor_id=vendor_id,
            date=entry_date,
            description=data['description'],
            folio=data.get('folio'),
            debit=debit,
            credit=credit,
            balance=new_balance,
            created_by_user=current_user.username if current_user else None,
            payment_notes=data.get('payment_notes'),
            attachment_path=attachment_path
        )
        
        db.session.add(ledger_entry)
        
        log_action(current_user, 'CREATE_LEDGER', 'vendors', vendor_id, f"Added ledger entry: {data['description']} (Debit: {debit:.2f}, Credit: {credit:.2f})")
        db.session.commit()
        
        logger.info(f"Ledger entry created successfully for vendor {vendor_id}")
        
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
        current_user = None
        current_user_id = get_jwt_identity()
        if current_user_id:
            current_user = User.query.get(int(current_user_id))
            
        log_action(current_user, 'DELETE_LEDGER', 'vendors', vendor_id, f"Deleted ledger entry ID {ledger_id} ({ledger_entry.description})")
        db.session.delete(ledger_entry)
        db.session.commit()
        
        logger.info(f"Ledger entry {ledger_id} deleted successfully")
        
        return jsonify({'message': 'Ledger entry deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting ledger entry: {e}")
        return jsonify({'error': 'Failed to delete ledger entry'}), 500

# ===== PURCHASE ORDER ROUTES =====

@vendor_bp.route('/api/vendors/<int:vendor_id>/purchase-orders', methods=['GET'])
@vendor_bp.route('/api/vendors/<int:vendor_id>/consignments', methods=['GET'])
@role_required(['admin', 'accountant'])
def get_vendor_purchase_orders(vendor_id):
    """Get purchase order records for a specific vendor"""
    try:
        vendor = Vendor.query.get(vendor_id)
        if not vendor:
            return jsonify({'error': 'Vendor not found'}), 404
        
        # Get filters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        invoice_no = request.args.get('invoice_no')
        status = request.args.get('status')
        
        query = PurchaseOrder.query.filter_by(vendor_id=vendor_id)
        
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(PurchaseOrder.date >= start_date_obj)
            except ValueError:
                return jsonify({'error': 'Invalid start_date format. Use YYYY-MM-DD'}), 400
        
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(PurchaseOrder.date <= end_date_obj)
            except ValueError:
                return jsonify({'error': 'Invalid end_date format. Use YYYY-MM-DD'}), 400
        
        if invoice_no:
            query = query.filter(PurchaseOrder.invoice_no.ilike(f'%{invoice_no}%'))
            
        if status:
            query = query.filter(PurchaseOrder.status == status)
        
        purchase_orders = query.order_by(PurchaseOrder.date.desc(), PurchaseOrder.id.desc()).all()
        
        return jsonify([po.to_dict() for po in purchase_orders]), 200
        
    except Exception as e:
        logger.error(f"Error fetching vendor purchase orders {vendor_id}: {e}")
        return jsonify({'error': 'Failed to fetch purchase orders'}), 500

@vendor_bp.route('/api/purchase-orders/add', methods=['POST'])
@vendor_bp.route('/api/consignments/add', methods=['POST'])
@role_required(['admin', 'accountant'])
def add_purchase_order():
    """Add a new purchase order record"""
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
            po_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        # Calculate amount
        quantity = int(data['quantity'])
        rate = float(data['rate'])
        amount = quantity * rate
        
        current_user = None
        current_user_id = get_jwt_identity()
        if current_user_id:
            current_user = User.query.get(int(current_user_id))
            
        # Create purchase order record
        po = PurchaseOrder(
            vendor_id=data['vendor_id'],
            date=po_date,
            invoice_no=data['invoice_no'],
            item_name=data['item_name'],
            quantity=quantity,
            rate=rate,
            amount=amount,
            remarks=data.get('remarks'),
            status=data.get('status', 'ordered'),
            created_by_user=current_user.username if current_user else None
        )
        
        db.session.add(po)
        db.session.flush()
        
        log_action(current_user, 'CREATE_PO', 'vendors', po.vendor_id, f"Created Purchase Order {po.invoice_no}: {po.item_name} x{po.quantity} ({po.status})")
        db.session.commit()
        
        logger.info(f"Purchase order record created successfully for vendor {data['vendor_id']}")
        
        return jsonify({
            'message': 'Purchase order record added successfully',
            'consignment': po.to_dict()  # Keep key 'consignment' for frontend backwards compatibility
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding purchase order: {e}")
        return jsonify({'error': 'Failed to add purchase order record'}), 500

@vendor_bp.route('/api/purchase-orders/<int:po_id>', methods=['DELETE'])
@vendor_bp.route('/api/consignments/<int:consignment_id>', methods=['DELETE'])
@role_required(['admin', 'accountant'])
def delete_purchase_order(po_id=None, consignment_id=None):
    """Delete a purchase order record"""
    try:
        target_id = po_id if po_id is not None else consignment_id
        po = PurchaseOrder.query.get(target_id)
        if not po:
            return jsonify({'error': 'Purchase order record not found'}), 404
        
        current_user = None
        current_user_id = get_jwt_identity()
        if current_user_id:
            current_user = User.query.get(int(current_user_id))
            
        log_action(current_user, 'DELETE_PO', 'vendors', po.vendor_id, f"Deleted Purchase Order {po.invoice_no}: {po.item_name}")
        db.session.delete(po)
        db.session.commit()
        
        logger.info(f"Purchase order record deleted successfully: ID {target_id}")
        
        return jsonify({'message': 'Purchase order record deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting purchase order: {e}")
        return jsonify({'error': 'Failed to delete purchase order record'}), 500

@vendor_bp.route('/api/purchase-orders/<int:po_id>/status', methods=['PUT'])
@role_required(['admin', 'accountant'])
def update_purchase_order_status(po_id):
    """Update purchase order status"""
    try:
        po = PurchaseOrder.query.get(po_id)
        if not po:
            return jsonify({'error': 'Purchase order not found'}), 404
        
        data = request.get_json()
        new_status = data.get('status')
        if new_status not in ['ordered', 'in transit', 'received']:
            return jsonify({'error': 'Invalid status'}), 400
            
        old_status = po.status
        po.status = new_status
        po.updated_at = datetime.utcnow()
        
        # Log action
        current_user = None
        current_user_id = get_jwt_identity()
        if current_user_id:
            current_user = User.query.get(int(current_user_id))
            
        log_action(current_user, 'UPDATE_PO_STATUS', 'vendors', po.vendor_id, f"Updated Purchase Order {po.invoice_no} status from '{old_status}' to '{new_status}'")
        db.session.commit()
        
        return jsonify({'message': 'Status updated successfully', 'status': po.status}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating purchase order status: {e}")
        return jsonify({'error': 'Failed to update status'}), 500
