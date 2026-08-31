from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import hashlib
import secrets

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')  # admin, accountant, inventory_manager
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    def set_password(self, password):
        # Use pbkdf2_sha256 instead of scrypt for better compatibility
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        try:
            return check_password_hash(self.password_hash, password)
        except AttributeError:
            # Fallback for scrypt compatibility issues
            return self._fallback_check_password(password)
    
    def _fallback_check_password(self, password):
        """Fallback password checking method for scrypt compatibility issues"""
        try:
            # Try to parse the hash format
            if self.password_hash.startswith('pbkdf2:sha256:'):
                # Extract salt and hash from the stored password
                parts = self.password_hash.split(':')
                if len(parts) == 4:
                    salt = parts[2]
                    stored_hash = parts[3]
                    
                    # Generate hash with the same salt
                    import hashlib
                    import base64
                    salt_bytes = base64.b64decode(salt)
                    password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt_bytes, 260000)
                    password_hash_b64 = base64.b64encode(password_hash).decode('ascii')
                    
                    return password_hash_b64 == stored_hash
        except Exception:
            pass
        
        # If all else fails, return False
        return False
    
    def has_permission(self, required_role):
        role_hierarchy = {
            'admin': ['admin', 'accountant', 'inventory_manager', 'repair_orders', 'repair-order', 'repair-orders-management'],
            'accountant': ['accountant', 'repair_orders', 'repair-order', 'repair-orders-management'],
            'inventory_manager': ['inventory_manager', 'repair_orders', 'repair-order', 'repair-orders-management']
        }
        return required_role in role_hierarchy.get(self.role, [])


class AppLog(db.Model):
    """Model for tracking all application actions and audit trails"""
    __tablename__ = 'app_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    username = db.Column(db.String(80), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    module = db.Column(db.String(50), nullable=False)
    reference_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'action': self.action,
            'module': self.module,
            'reference_id': self.reference_id,
            'details': self.details,
            'ip_address': self.ip_address,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }


class Invoice(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    customer_name = db.Column(db.String(255), nullable=False)
    customer_address = db.Column(db.String(255), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    customer_reg_no = db.Column(db.String(50), nullable=False)
    customer_made = db.Column(db.String(100), nullable=False)
    customer_mileage = db.Column(db.String(100), nullable=False)
    customer_vin = db.Column(db.String(17), nullable=True)  # VIN can be up to 17 characters
    customer_color = db.Column(db.String(50), nullable=True)  # Car color
    customer_chasis = db.Column(db.String(50), nullable=True)  # Chassis number
    balance = db.Column(db.Float, nullable=False)
    advance = db.Column(db.Float, nullable=False)
    net_total = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, default=0.0, nullable=False)  # Add discount field
    type_of = db.Column(db.String(50), nullable=False)
    include_tax = db.Column(db.Boolean, default=False, nullable=False)
    tax_amount = db.Column(db.Float, default=0.0, nullable=False)
    paid_amount = db.Column(db.Float, default=0.0, nullable=True)  # Amount paid by customer
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending for quotes, unpaid for invoices
    
    # Audit trail and logs
    created_by_user = db.Column(db.String(80), nullable=True)
    updated_by_user = db.Column(db.String(80), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    payments_history = db.Column(db.Text, nullable=True)

    items = db.relationship('InvoiceItem', backref='invoice', cascade='all, delete-orphan', lazy=True)
    labours = db.relationship('InvoiceLabour', backref='invoice', cascade='all, delete-orphan', lazy=True)


class InvoiceItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
    product_name = db.Column(db.String(255), nullable=False)
    part_number = db.Column(db.String(100), nullable=True)  # Part number from inventory
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)


class InvoiceLabour(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Float, nullable=False)


class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    part_number = db.Column(db.String(20), unique=True, nullable=False)  # Auto-generated part number
    barcode = db.Column(db.String(100), unique=True, nullable=True)
    manufacturer_part_number = db.Column(db.String(100), unique=True, nullable=True)
    name = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    price = db.Column(db.Float, nullable=False, default=0.0)
    description = db.Column(db.Text)
    location = db.Column(db.String(255))
    reorder_level = db.Column(db.Integer, default=5, nullable=False)  # Minimum stock level before reorder
    reorder_quantity = db.Column(db.Integer, default=10, nullable=False)  # Quantity to reorder
    image_path = db.Column(db.String(255), nullable=True)  # Path to uploaded image
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __init__(self, **kwargs):
        super(Inventory, self).__init__(**kwargs)
        if not self.part_number:
            self.part_number = self.generate_part_number()
    
    def generate_part_number(self):
        """Generate a sequential part number"""
        from sqlalchemy import func
        # Get the highest part number
        max_part = db.session.query(func.max(Inventory.part_number)).scalar()
        
        if max_part:
            # Extract the number from the part number (e.g., "PN001" -> 1)
            try:
                current_num = int(max_part[2:])  # Remove "PN" prefix
                next_num = current_num + 1
            except (ValueError, IndexError):
                next_num = 1
        else:
            next_num = 1
        
        # Format as PN001, PN002, etc.
        return f"PN{next_num:03d}"


class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    cars = db.relationship('Car', backref='customer', cascade='all, delete-orphan', lazy=True)


class Car(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    make = db.Column(db.String(100), nullable=True)
    model = db.Column(db.String(100), nullable=True)
    plate_no = db.Column(db.String(20), nullable=True)
    mileage = db.Column(db.String(50), nullable=True)
    vin = db.Column(db.String(17), nullable=True)  # VIN can be up to 17 characters
    color = db.Column(db.String(50), nullable=True)  # New field for car color
    chasis_no = db.Column(db.String(50), nullable=True)  # New field for chassis number
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RepairOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(255), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    customer_address = db.Column(db.String(255), nullable=False)
    customer_reg_no = db.Column(db.String(50), nullable=False)
    customer_made = db.Column(db.String(100), nullable=False)
    customer_mileage = db.Column(db.String(100), nullable=False)
    customer_vin = db.Column(db.String(17), nullable=True)
    customer_color = db.Column(db.String(50), nullable=True)
    customer_chasis = db.Column(db.String(50), nullable=True)
    problem_description = db.Column(db.Text, nullable=True)
    diagnosis_plan = db.Column(db.Text, nullable=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('workers.id'), nullable=True)
    worker_name = db.Column(db.String(255), nullable=True)
    current_status = db.Column(db.String(20), default='received', nullable=False)
    status_timeline = db.Column(db.Text, nullable=True)  # JSON string for timeline
    vehicle_condition = db.Column(db.Text, nullable=True)  # JSON string for vehicle condition
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Audit trail and multiple workers support
    created_by_user = db.Column(db.String(80), nullable=True)
    updated_by_user = db.Column(db.String(80), nullable=True)
    workers_json = db.Column(db.Text, nullable=True)
    
    parts = db.relationship('RepairOrderPart', backref='repair_order', cascade='all, delete-orphan', lazy=True)
    labour = db.relationship('RepairOrderLabour', backref='repair_order', cascade='all, delete-orphan', lazy=True)


class RepairOrderPart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    repair_order_id = db.Column(db.Integer, db.ForeignKey('repair_order.id'), nullable=False)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.id'), nullable=True)  # Link to inventory item
    description = db.Column(db.String(255), nullable=False)
    part_number = db.Column(db.String(100), nullable=True)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, ordered, received, installed


class RepairOrderLabour(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    repair_order_id = db.Column(db.Integer, db.ForeignKey('repair_order.id'), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, in_progress, completed


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CashReceived(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)  # Cash, Bank Transfer, Card, etc.
    notes = db.Column(db.Text, nullable=True)

    # Which invoice this money settles. Nullable on purpose: genuine non-invoice
    # income exists, and every receipt taken before this column was added has no
    # recoverable link - the description never recorded one.
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoice.id'), nullable=True, index=True)
    invoice = db.relationship('Invoice', backref='cash_receipts')

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'description': self.description,
            'amount': self.amount,
            'payment_method': self.payment_method,
            'notes': self.notes,
            'invoice_id': self.invoice_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class FinancialPeriod(db.Model):
    """A month of financial records, and whether it is still open for editing.

    Months roll closed on their own once they end, so nobody has to remember to
    do it. A row exists here only when someone has deliberately departed from
    that default - reopening a month to fix something, or closing the current
    month early.
    """
    __tablename__ = 'financial_periods'

    id = db.Column(db.Integer, primary_key=True)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)      # 1-12
    is_open = db.Column(db.Boolean, nullable=False, default=False)

    changed_by = db.Column(db.String(80), nullable=True)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)
    reason = db.Column(db.String(255), nullable=True)

    __table_args__ = (
        db.UniqueConstraint('year', 'month', name='uq_financial_period'),
    )

    def to_dict(self):
        return {
            'year': self.year,
            'month': self.month,
            'is_open': self.is_open,
            'changed_by': self.changed_by,
            'changed_at': self.changed_at.isoformat() if self.changed_at else None,
            'reason': self.reason,
        }


class WhatsAppNotification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    
    # Client information
    customer_name = db.Column(db.String(255), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    
    # Notification details
    notification_type = db.Column(db.String(50), nullable=False)  # invoice, quote, payment_reminder, repair_status
    message_content = db.Column(db.Text, nullable=False)
    
    # Related document
    related_document_type = db.Column(db.String(50), nullable=True)  # invoice, repair_order
    related_document_id = db.Column(db.Integer, nullable=True)
    
    # WhatsApp API response
    whatsapp_message_id = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, sent, delivered, failed
    error_message = db.Column(db.Text, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_at = db.Column(db.DateTime, nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        """The routes have always called this; it was never defined, so the
        WhatsApp notifications page returned a 500 on every load."""
        stamp = lambda v: v.isoformat() if v else None
        return {
            'id': self.id,
            'customer_name': self.customer_name,
            'customer_phone': self.customer_phone,
            'notification_type': self.notification_type,
            'message_content': self.message_content,
            'related_document_type': self.related_document_type,
            'related_document_id': self.related_document_id,
            'whatsapp_message_id': self.whatsapp_message_id,
            'status': self.status,
            'error_message': self.error_message,
            'created_at': stamp(self.created_at),
            'sent_at': stamp(self.sent_at),
            'delivered_at': stamp(self.delivered_at),
        }


# ===== VENDOR MANAGEMENT MODELS =====

class Vendor(db.Model):
    """Vendor model for managing suppliers and vendors"""
    __tablename__ = 'vendors'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    company_name = db.Column(db.String(255), nullable=False)
    contact_person = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    address = db.Column(db.Text, nullable=False)
    cnic = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    ledger_entries = db.relationship('VendorLedger', backref='vendor', lazy=True, cascade='all, delete-orphan')
    purchase_orders = db.relationship('PurchaseOrder', backref='vendor', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Vendor {self.name} - {self.company_name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'company_name': self.company_name,
            'contact_person': self.contact_person,
            'phone': self.phone,
            'email': self.email,
            'address': self.address,
            'cnic': self.cnic,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        }


class VendorLedger(db.Model):
    """Vendor ledger entries for tracking financial transactions"""
    __tablename__ = 'vendor_ledger'
    
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(500), nullable=False)
    folio = db.Column(db.String(100), nullable=True)
    debit = db.Column(db.Numeric(10, 2), default=0.00, nullable=False)
    credit = db.Column(db.Numeric(10, 2), default=0.00, nullable=False)
    balance = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Audit trail, payment notes and attachments
    created_by_user = db.Column(db.String(80), nullable=True)
    payment_notes = db.Column(db.Text, nullable=True)
    attachment_path = db.Column(db.String(255), nullable=True)
    
    def __repr__(self):
        return f'<VendorLedger {self.vendor_id} - {self.description}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'vendor_id': self.vendor_id,
            'date': self.date.strftime('%Y-%m-%d'),
            'description': self.description,
            'folio': self.folio,
            'debit': float(self.debit),
            'credit': float(self.credit),
            'balance': float(self.balance),
            'created_by_user': self.created_by_user,
            'payment_notes': self.payment_notes,
            'attachment_path': self.attachment_path,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }


class PurchaseOrder(db.Model):
    """Purchase order records for tracking goods received from vendors"""
    __tablename__ = 'purchase_orders'
    
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    invoice_no = db.Column(db.String(100), nullable=False)
    item_name = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    rate = db.Column(db.Numeric(10, 2), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    remarks = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default='ordered', nullable=False) # ordered, in transit, received
    created_by_user = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<PurchaseOrder {self.vendor_id} - {self.item_name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'vendor_id': self.vendor_id,
            'date': self.date.strftime('%Y-%m-%d'),
            'invoice_no': self.invoice_no,
            'item_name': self.item_name,
            'quantity': self.quantity,
            'rate': float(self.rate),
            'amount': float(self.amount),
            'remarks': self.remarks,
            'status': self.status,
            'created_by_user': self.created_by_user,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S') if self.updated_at else None
        }


# ===== HR MANAGEMENT MODELS =====

class Worker(db.Model):
    """Worker model for HR management"""
    __tablename__ = 'workers'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(20), unique=True, nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(20), nullable=False)
    address = db.Column(db.Text, nullable=False)
    cnic = db.Column(db.String(20), unique=True, nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    hire_date = db.Column(db.Date, nullable=False)
    position = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    salary = db.Column(db.Numeric(10, 2), nullable=True)
    status = db.Column(db.String(20), default='active', nullable=False)  # active, inactive, terminated
    emergency_contact_name = db.Column(db.String(100), nullable=True)
    emergency_contact_phone = db.Column(db.String(20), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Worker {self.employee_id} - {self.first_name} {self.last_name}>'

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.email,
            'phone': self.phone,
            'address': self.address,
            'cnic': self.cnic,
            'date_of_birth': self.date_of_birth.strftime('%Y-%m-%d') if self.date_of_birth else None,
            'hire_date': self.hire_date.strftime('%Y-%m-%d') if self.hire_date else None,
            'position': self.position,
            'department': self.department,
            'salary': float(self.salary) if self.salary else None,
            'status': self.status,
            'emergency_contact_name': self.emergency_contact_name,
            'emergency_contact_phone': self.emergency_contact_phone,
            'notes': self.notes,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        }


# ===== ATTENDANCE MODEL =====

class AttendanceRecord(db.Model):
    """Attendance record for a worker (check-in/check-out). Used for salary calculation."""
    __tablename__ = 'attendance_records'

    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('workers.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    check_in_time = db.Column(db.DateTime, nullable=True)
    check_out_time = db.Column(db.DateTime, nullable=True)
    work_hours = db.Column(db.Float, nullable=True)
    notes = db.Column(db.String(255), nullable=True)
    source = db.Column(db.String(50), nullable=True)  # e.g. 'manual', 'ZKTeco push'
    zkteco_device_id = db.Column(db.Integer, db.ForeignKey('zkteco_devices.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    worker = db.relationship('Worker', backref=db.backref('attendance_records', lazy='dynamic'))
    zkteco_device = db.relationship('ZKTecoDevice', backref=db.backref('attendance_records', lazy='dynamic'))

    def __repr__(self):
        return f'<AttendanceRecord worker_id={self.worker_id} date={self.date}>'

    def to_dict(self):
        return {
            'id': self.id,
            'worker_id': self.worker_id,
            'date': self.date.strftime('%Y-%m-%d') if self.date else None,
            'check_in_time': self.check_in_time.strftime('%H:%M') if self.check_in_time else None,
            'check_out_time': self.check_out_time.strftime('%H:%M') if self.check_out_time else None,
            'work_hours': round(self.work_hours, 2) if self.work_hours is not None else None,
            'notes': self.notes,
            'source': self.source,
            'zkteco_device_id': self.zkteco_device_id,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        }


# ===== ZKTECO DEVICE MODEL =====

class ZKTecoDevice(db.Model):
    """ZKTeco device that pushes attendance to this server (PUSH protocol). Identified by serial_number (SN)."""
    __tablename__ = 'zkteco_devices'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    serial_number = db.Column(db.String(64), unique=True, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    port = db.Column(db.Integer, default=4370, nullable=True)
    timeout = db.Column(db.Integer, default=30, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_sync = db.Column(db.DateTime, nullable=True)
    last_sync_status = db.Column(db.String(50), nullable=True)
    last_seen_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        addr = f"{self.ip_address}:{self.port}" if self.ip_address else (self.serial_number or "?")
        return f'<ZKTecoDevice {self.name} {addr}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'serial_number': self.serial_number,
            'ip_address': self.ip_address,
            'port': self.port,
            'timeout': self.timeout,
            'is_active': self.is_active,
            'last_sync': self.last_sync.strftime('%Y-%m-%d %H:%M:%S') if self.last_sync else None,
            'last_sync_status': self.last_sync_status,
            'last_seen_at': self.last_seen_at.strftime('%Y-%m-%d %H:%M:%S') if self.last_seen_at else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        }


# ===== SETTINGS MODELS =====

class Department(db.Model):
    """Department model for managing organizational departments"""
    __tablename__ = 'departments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Department {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'is_active': self.is_active,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        }


class Category(db.Model):
    """Category model for managing inventory categories"""
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Category {self.name}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'is_active': self.is_active,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        }


# ===== INVENTORY TRANSACTION HISTORY =====

class InventoryTransaction(db.Model):
    """Model for tracking all inventory movements"""
    __tablename__ = 'inventory_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.id'), nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # 'issue_out', 'received', 'adjustment'
    quantity = db.Column(db.Integer, nullable=False)  # positive for received, negative for issue out
    previous_quantity = db.Column(db.Integer, nullable=False)  # stock level before transaction
    new_quantity = db.Column(db.Integer, nullable=False)  # stock level after transaction
    repair_order_id = db.Column(db.Integer, db.ForeignKey('repair_order.id'), nullable=True)
    reference_description = db.Column(db.String(500), nullable=True)  # description of the transaction
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)
    
    # Relationships
    inventory = db.relationship('Inventory', backref=db.backref('transactions', lazy=True))
    repair_order = db.relationship('RepairOrder', backref=db.backref('inventory_transactions', lazy=True))
    user = db.relationship('User', backref=db.backref('inventory_transactions', lazy=True))
    
    def __repr__(self):
        return f'<InventoryTransaction {self.id} - {self.transaction_type} - {self.quantity}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'inventory_id': self.inventory_id,
            'inventory_name': self.inventory.name if self.inventory else None,
            'inventory_part_number': self.inventory.part_number if self.inventory else None,
            'transaction_type': self.transaction_type,
            'quantity': self.quantity,
            'previous_quantity': self.previous_quantity,
            'new_quantity': self.new_quantity,
            'repair_order_id': self.repair_order_id,
            'reference_description': self.reference_description,
            'created_by': self.created_by,
            'created_by_username': self.user.username if self.user else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'notes': self.notes
        }

class RolePermission(db.Model):
    __tablename__ = 'role_permissions'
    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.String(50), nullable=False)
    permission = db.Column(db.String(100), nullable=False)
    
    __table_args__ = (
        db.UniqueConstraint('role', 'permission', name='unique_role_permission'),
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'role': self.role,
            'permission': self.permission
        }
