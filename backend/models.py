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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    consignments = db.relationship('VendorConsignment', backref='vendor', lazy=True, cascade='all, delete-orphan')
    
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
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }


class VendorConsignment(db.Model):
    """Vendor consignment records for tracking goods received"""
    __tablename__ = 'vendor_consignments'
    
    id = db.Column(db.Integer, primary_key=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendors.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    invoice_no = db.Column(db.String(100), nullable=False)
    item_name = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    rate = db.Column(db.Numeric(10, 2), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    remarks = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<VendorConsignment {self.vendor_id} - {self.item_name}>'
    
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
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
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
