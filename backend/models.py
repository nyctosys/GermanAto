from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

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
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def has_permission(self, required_role):
        role_hierarchy = {
            'admin': ['admin', 'accountant', 'inventory_manager'],
            'accountant': ['accountant'],
            'inventory_manager': ['inventory_manager']
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
    worker_name = db.Column(db.String(255), nullable=True)
    current_status = db.Column(db.String(20), default='received', nullable=False)
    status_timeline = db.Column(db.Text, nullable=True)  # JSON string for timeline
    vehicle_condition = db.Column(db.Text, nullable=True)  # JSON string for vehicle condition
    parts_total = db.Column(db.Float, default=0.0, nullable=False)
    labour_total = db.Column(db.Float, default=0.0, nullable=False)
    tax_amount = db.Column(db.Float, default=0.0, nullable=False)
    total_estimate = db.Column(db.Float, default=0.0, nullable=False)
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
    price = db.Column(db.Float, default=0.0, nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, ordered, received, installed


class RepairOrderLabour(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    repair_order_id = db.Column(db.Integer, db.ForeignKey('repair_order.id'), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    rate = db.Column(db.Float, default=0.0, nullable=False)
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
