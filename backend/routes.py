from flask import Blueprint, request, jsonify, session
from models import db, Invoice, InvoiceItem, InvoiceLabour, WhatsAppNotification, User
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
import logging
import re
from datetime import datetime, timedelta
from functools import wraps
from whatsapp_notifications import whatsapp_notifier

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bp = Blueprint('invoice', __name__)

def calculate_totals(items, labours):
    """Calculate total from items and labours"""
    try:
        items_total = sum(float(item.get('price', 0)) * int(item.get('quantity', 0)) for item in items)
        labours_total = sum(float(labour.get('price', 0)) for labour in labours)
        return round(items_total + labours_total, 2)
    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating totals: {e}")
        return 0.0

# Inventory deduction functionality has been removed
# This function is kept for compatibility but does nothing
def update_inventory_quantities(items):
    """Inventory deduction has been disabled - this function does nothing"""
    logger.info("Inventory deduction is disabled - no inventory quantities will be updated")
    return True

def validate_phone_number(phone):
    """Validate phone number format"""
    if not phone:
        return False
    # More flexible phone number validation - allow various formats
    pattern = r'^(\+92\s?\d{3}\s?\d{7}|\d{11}|\d{4}\s?\d{7})$'
    return bool(re.match(pattern, phone))

def validate_invoice_data(data):
    """Validate invoice data"""
    errors = []
    
    # Customer and car fields are now optional - only validate if provided and not "N/A"
    customer_fields = ['customer_name', 'customer_address', 'customer_phone', 
                      'customer_reg_no', 'customer_made', 'customer_mileage']
    
    for field in customer_fields:
        value = data.get(field)
        # Field is optional, but if provided and not "N/A", it should be valid
        if value and value != "N/A" and not str(value).strip():
            errors.append(f"{field.replace('_', ' ').title()} must be a valid string if provided")
    
    # Validate phone number only if provided and not "N/A"
    phone = data.get('customer_phone')
    if phone and phone != "N/A" and not validate_phone_number(phone):
        errors.append("Phone number must be in format: +92 xxx xxxxxxx")
    
    # Validate numeric fields
    try:
        advance = float(data.get('advance', 0))
        if advance < 0:
            errors.append("Advance amount cannot be negative")
    except (ValueError, TypeError):
        errors.append("Advance amount must be a valid number")
    
    # Validate items and labours
    items = data.get('items', [])
    labours = data.get('labours', [])
    
    if not items and not labours:
        errors.append("At least one item or labour is required")
    
    # Validate items
    for i, item in enumerate(items):
        if not item.get('product_name') or not str(item.get('product_name')).strip():
            errors.append(f"Item {i+1}: Product name is required")
        try:
            quantity = int(item.get('quantity', 0))
            price = float(item.get('price', 0))
            if quantity <= 0:
                errors.append(f"Item {i+1}: Quantity must be greater than 0")
            if price < 0:
                errors.append(f"Item {i+1}: Price cannot be negative")
        except (ValueError, TypeError):
            errors.append(f"Item {i+1}: Quantity and price must be valid numbers")
    
    # Validate labours
    for i, labour in enumerate(labours):
        if not labour.get('description') or not str(labour.get('description')).strip():
            errors.append(f"Labour {i+1}: Description is required")
        try:
            price = float(labour.get('price', 0))
            if price < 0:
                errors.append(f"Labour {i+1}: Price cannot be negative")
        except (ValueError, TypeError):
            errors.append(f"Labour {i+1}: Price must be a valid number")
    
    return errors

# Decorator to check if user can edit invoice based on role and time
def can_edit_invoice(f):
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
        
        # For other roles, check if invoice is older than 1 day (only for invoices, not quotes)
        invoice_id = kwargs.get('invoice_id')
        if invoice_id:
            invoice = Invoice.query.get(invoice_id)
            if not invoice:
                return jsonify({'error': 'Invoice not found'}), 404
            
            # Only apply time restriction to invoices, not quotes
            if invoice.type_of.lower() == 'invoice':
                # Check if invoice is older than 1 day
                one_day_ago = datetime.utcnow() - timedelta(days=1)
                if invoice.created_at < one_day_ago:
                    return jsonify({'error': 'Cannot edit invoices older than 1 day'}), 403
        
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/add', methods=['POST'])
def create_invoice():
    """Create a new invoice"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate input data
        validation_errors = validate_invoice_data(data)
        if validation_errors:
            return jsonify({'error': 'Validation failed', 'details': validation_errors}), 400
        
        # Extract and clean data
        customer_name = str(data.get('customer_name')).strip()
        customer_address = str(data.get('customer_address')).strip()
        customer_phone = str(data.get('customer_phone')).strip()
        customer_reg_no = str(data.get('customer_reg_no')).strip()
        customer_made = str(data.get('customer_made')).strip()
        customer_mileage = str(data.get('customer_mileage')).strip()
        customer_vin = str(data.get('customer_vin', '')).strip() if data.get('customer_vin') else None
        customer_color = str(data.get('customer_color', '')).strip() if data.get('customer_color') else None
        customer_chasis = str(data.get('customer_chasis', '')).strip() if data.get('customer_chasis') else None
        advance = float(data.get('advance', 0))
        discount = float(data.get('discount', 0))
        type_of = str(data.get('type_of', 'invoice')).strip().lower()
        include_tax = bool(data.get('include_tax', False))
        tax_amount = float(data.get('tax_amount', 0))
        items_data = data.get('items', [])
        labours_data = data.get('labours', [])
        
        # Calculate totals
        total = calculate_totals(items_data, labours_data)
        
        # If tax is included, the net_total should be the base amount (without tax)
        # The total passed to the database should include tax if applicable
        if include_tax:
            net_total = total  # This is the base amount without tax
            total_with_tax = total + tax_amount
            balance = round(total_with_tax - discount - advance, 2)
        else:
            net_total = total
            balance = round(total - discount - advance, 2)
        
        # Create invoice with transaction
        try:
            # Set appropriate default status based on document type
            default_status = 'unpaid' if type_of == 'invoice' else 'pending'
            
            invoice = Invoice(
                customer_name=customer_name,
                customer_address=customer_address,
                customer_phone=customer_phone,
                customer_reg_no=customer_reg_no,
                customer_made=customer_made,
                customer_mileage=customer_mileage,
                customer_vin=customer_vin,
                customer_color=customer_color,
                customer_chasis=customer_chasis,
                balance=balance,
                advance=advance,
                net_total=net_total,
                discount=discount,
                type_of=type_of,
                include_tax=include_tax,
                tax_amount=tax_amount,
                status=default_status
            )
            db.session.add(invoice)
            db.session.flush()  # Get the ID without committing
            
            # Add items
            for item in items_data:
                invoice_item = InvoiceItem(
                    invoice_id=invoice.id,
                    product_name=str(item['product_name']).strip(),
                    part_number=str(item.get('part_number', '')).strip() if item.get('part_number') else None,
                    quantity=int(item['quantity']),
                    price=float(item['price'])
                )
                db.session.add(invoice_item)
            
            # Add labours
            for labour in labours_data:
                invoice_labour = InvoiceLabour(
                    invoice_id=invoice.id,
                    description=str(labour['description']).strip(),
                    price=float(labour['price'])
                )
                db.session.add(invoice_labour)
            
            # Update inventory quantities only for invoices (not quotes)
            # DISABLED: Inventory is no longer deducted when creating invoices
            # if type_of == 'invoice' and items_data:
            #     try:
            #         update_inventory_quantities(items_data)
            #     except ValueError as e:
            #         db.session.rollback()
            #         return jsonify({'error': str(e)}), 400
            #     except Exception as e:
            #         db.session.rollback()
            #         logger.error(f"Error updating inventory: {e}")
            #         return jsonify({'error': 'Failed to update inventory'}), 500
            
            db.session.commit()
            
            logger.info(f"Invoice created successfully: ID {invoice.id}")
            
            # Send WhatsApp notification to client
            try:
                # Prepare invoice data for notification
                invoice_data = {
                    'id': invoice.id,
                    'customer_name': customer_name,
                    'customer_phone': customer_phone,
                    'net_total': net_total,
                    'type_of': type_of
                }
                
                # Send WhatsApp notification
                notification_result = whatsapp_notifier.send_invoice_notification(invoice_data)
                
                # Log notification result
                if notification_result['success']:
                    logger.info(f"WhatsApp notification sent successfully for invoice {invoice.id}")
                    
                    # Save notification record to database
                    notification_record = WhatsAppNotification(
                        customer_name=customer_name,
                        customer_phone=customer_phone,
                        notification_type='invoice' if type_of == 'invoice' else 'quote',
                        message_content=whatsapp_notifier._create_invoice_message(customer_name, invoice.id, f"{float(net_total):,.2f} PKR") if type_of == 'invoice' else whatsapp_notifier._create_quote_message(customer_name, invoice.id, f"{float(net_total):,.2f} PKR"),
                        related_document_type='invoice',
                        related_document_id=invoice.id,
                        whatsapp_message_id=notification_result.get('message_id'),
                        status=notification_result.get('status', 'sent')
                    )
                    db.session.add(notification_record)
                    db.session.commit()
                    
                else:
                    logger.warning(f"WhatsApp notification failed for invoice {invoice.id}: {notification_result.get('error', 'Unknown error')}")
                    
                    # Save failed notification record
                    notification_record = WhatsAppNotification(
                        customer_name=customer_name,
                        customer_phone=customer_phone,
                        notification_type='invoice' if type_of == 'invoice' else 'quote',
                        message_content=whatsapp_notifier._create_invoice_message(customer_name, invoice.id, f"{float(net_total):,.2f} PKR") if type_of == 'invoice' else whatsapp_notifier._create_quote_message(customer_name, invoice.id, f"{float(net_total):,.2f} PKR"),
                        related_document_type='invoice',
                        related_document_id=invoice.id,
                        status='failed',
                        error_message=notification_result.get('error', 'Unknown error')
                    )
                    db.session.add(notification_record)
                    db.session.commit()
                    
            except Exception as e:
                logger.error(f"Error sending WhatsApp notification for invoice {invoice.id}: {e}")
                # Don't fail the invoice creation if notification fails
            
            return jsonify({
                'message': 'Invoice created successfully',
                'invoice_id': invoice.id,
                'customer_name': customer_name,
                'total': total,
                'balance': balance,
                'whatsapp_sent': notification_result.get('success', False) if 'notification_result' in locals() else False
            }), 201
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error creating invoice: {e}")
            return jsonify({'error': 'Database error occurred'}), 500
            
    except Exception as e:
        logger.error(f"Unexpected error creating invoice: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/invoice/<int:invoice_id>', methods=['GET'])
def get_invoice(invoice_id):
    """Get invoice by ID"""
    try:
        if not invoice_id or invoice_id <= 0:
            return jsonify({'error': 'Invalid invoice ID'}), 400
        invoice = Invoice.query.get(invoice_id)
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        invoice_data = {
            "id": invoice.id,
            "customer_name": invoice.customer_name,
            "customer_address": invoice.customer_address,
            "customer_phone": invoice.customer_phone,
            "customer_reg_no": invoice.customer_reg_no,
            "customer_made": invoice.customer_made,
            "customer_mileage": invoice.customer_mileage,
            "customer_vin": invoice.customer_vin,
            "customer_color": invoice.customer_color or "",
            "customer_chasis": invoice.customer_chasis or "",
            "created_at": invoice.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "balance": float(invoice.balance),
            "advance": float(invoice.advance),
            "net_total": float(invoice.net_total),
            "discount": float(invoice.discount),
            "type_of": invoice.type_of,
            "include_tax": invoice.include_tax,
            "tax_amount": float(invoice.tax_amount),
            "paid_amount": float(invoice.paid_amount or 0),
            "status": invoice.status,
            "items": [
                {
                    "id": item.id, 
                    "product_name": item.product_name, 
                    "part_number": item.part_number,
                    "quantity": item.quantity, 
                    "price": float(item.price)
                }
                for item in invoice.items
            ],
            "labours": [
                {
                    "id": labour.id, 
                    "description": labour.description, 
                    "price": float(labour.price)
                }
                for labour in invoice.labours
            ]
        }
        
        # If color or chassis is not saved, try to fetch from Car table
        if not invoice_data["customer_color"] or not invoice_data["customer_chasis"]:
            from models import Car
            car = None
            if invoice.customer_vin:
                car = Car.query.filter_by(vin=invoice.customer_vin).first()
            if not car and invoice.customer_reg_no:
                car = Car.query.filter_by(plate_no=invoice.customer_reg_no).first()
            if car:
                if not invoice_data["customer_color"]:
                    invoice_data["customer_color"] = car.color or ""
                if not invoice_data["customer_chasis"]:
                    invoice_data["customer_chasis"] = car.chasis_no or ""
        
        return jsonify(invoice_data), 200
    except Exception as e:
        logger.error(f"Error getting invoice {invoice_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/invoice/<int:invoice_id>/delete', methods=['DELETE'])
def delete_invoice(invoice_id):
    """Delete invoice by ID"""
    try:
        if not invoice_id or invoice_id <= 0:
            return jsonify({'error': 'Invalid invoice ID'}), 400
        
        invoice = Invoice.query.get(invoice_id)
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        try:
            # Delete related items and labours first
            InvoiceItem.query.filter_by(invoice_id=invoice_id).delete()
            InvoiceLabour.query.filter_by(invoice_id=invoice_id).delete()
            
            # Delete the invoice
            db.session.delete(invoice)
            db.session.commit()
            
            logger.info(f"Invoice deleted successfully: ID {invoice_id}")
            
            return jsonify({'message': 'Invoice deleted successfully'}), 200
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error deleting invoice {invoice_id}: {e}")
            return jsonify({'error': 'Database error occurred'}), 500
            
    except Exception as e:
        logger.error(f"Error deleting invoice {invoice_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/invoice/<int:invoice_id>/update', methods=['PUT'])
@can_edit_invoice
def update_invoice(invoice_id):
    """Update invoice by ID"""
    try:
        if not invoice_id or invoice_id <= 0:
            return jsonify({'error': 'Invalid invoice ID'}), 400
        
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        invoice = Invoice.query.get(invoice_id)
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        # Validate input data
        validation_errors = validate_invoice_data(data)
        if validation_errors:
            return jsonify({'error': 'Validation failed', 'details': validation_errors}), 400
        
        try:
            # Update invoice basic fields
            if 'customer_name' in data:
                invoice.customer_name = str(data['customer_name']).strip()
            if 'customer_address' in data:
                invoice.customer_address = str(data['customer_address']).strip()
            if 'customer_phone' in data:
                invoice.customer_phone = str(data['customer_phone']).strip()
            if 'customer_reg_no' in data:
                invoice.customer_reg_no = str(data['customer_reg_no']).strip()
            if 'customer_made' in data:
                invoice.customer_made = str(data['customer_made']).strip()
            if 'customer_mileage' in data:
                invoice.customer_mileage = str(data['customer_mileage']).strip()
            if 'customer_vin' in data:
                invoice.customer_vin = str(data['customer_vin']).strip() if data['customer_vin'] else None
            if 'customer_color' in data:
                invoice.customer_color = str(data['customer_color']).strip() if data['customer_color'] else None
            if 'customer_chasis' in data:
                invoice.customer_chasis = str(data['customer_chasis']).strip() if data['customer_chasis'] else None
            if 'type_of' in data:
                invoice.type_of = str(data['type_of']).strip().lower()
            if 'advance' in data:
                invoice.advance = float(data['advance'])
            if 'discount' in data:
                invoice.discount = float(data['discount'])
            if 'include_tax' in data:
                invoice.include_tax = bool(data['include_tax'])
            if 'tax_amount' in data:
                invoice.tax_amount = float(data['tax_amount'])
            
            items_data = data.get('items', [])
            labours_data = data.get('labours', [])
            
            # Delete old items and labours
            InvoiceItem.query.filter_by(invoice_id=invoice_id).delete()
            InvoiceLabour.query.filter_by(invoice_id=invoice_id).delete()
            
            # Add new items
            for item in items_data:
                new_item = InvoiceItem(
                    invoice_id=invoice.id,
                    product_name=str(item['product_name']).strip(),
                    part_number=str(item.get('part_number', '')).strip() if item.get('part_number') else None,
                    quantity=int(item['quantity']),
                    price=float(item['price'])
                )
                db.session.add(new_item)
            
            # Add new labours
            for labour in labours_data:
                new_labour = InvoiceLabour(
                    invoice_id=invoice.id,
                    description=str(labour['description']).strip(),
                    price=float(labour['price'])
                )
                db.session.add(new_labour)
            
            # Recalculate total
            total = calculate_totals(items_data, labours_data)
            invoice.net_total = total
            
            # Calculate balance considering tax and discount
            if invoice.include_tax and invoice.tax_amount > 0:
                total_with_tax = total + invoice.tax_amount
                invoice.balance = round(total_with_tax - invoice.discount - invoice.advance, 2)
            else:
                invoice.balance = round(total - invoice.discount - invoice.advance, 2)
            
            db.session.commit()
            
            logger.info(f"Invoice updated successfully: ID {invoice_id}")
            
            return jsonify({
                'message': 'Invoice updated successfully', 
                'invoice_id': invoice.id,
                'total': total,
                'balance': invoice.balance
            }), 200
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error updating invoice {invoice_id}: {e}")
            return jsonify({'error': 'Database error occurred'}), 500
            
    except Exception as e:
        logger.error(f"Error updating invoice {invoice_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/search', methods=['GET'])
def search_invoices():
    """Search invoices by various criteria"""
    try:
        query = request.args.get('q', '').strip()
        search_id = request.args.get('id', '').strip()
        status = request.args.get('status', '').strip()
        type_of = request.args.get('type', '').strip()
        
        # If no search criteria provided, return empty results
        if not query and not search_id and not status and not type_of:
            return jsonify([]), 200
        
        # Sanitize query to prevent SQL injection
        if len(query) > 100:  # Limit query length
            return jsonify({'error': 'Search query too long'}), 400
        
        # Build search conditions
        search_conditions = []
        
        # Add ID search if provided
        if search_id:
            try:
                query_id = int(search_id)
                search_conditions.append(Invoice.id == query_id)
            except ValueError:
                # Invalid ID format, ignore it
                pass
        
        # Add keyword search if provided
        if query:
            search_conditions.append(
                db.or_(
                    Invoice.customer_name.ilike(f'%{query}%'),
                    Invoice.customer_phone.ilike(f'%{query}%'),
                    Invoice.customer_reg_no.ilike(f'%{query}%'),
                    Invoice.type_of.ilike(f'%{query}%'),
                    db.cast(Invoice.id, db.String).ilike(f'%{query}%')
                )
            )
        
        # Add status filter if provided
        if status:
            search_conditions.append(Invoice.status == status)
        # Add type_of filter if provided
        if type_of:
            search_conditions.append(Invoice.type_of.ilike(type_of))
        
        # If no valid search conditions, return empty results
        if not search_conditions:
            return jsonify([]), 200
        
        # Combine conditions with AND
        final_condition = db.and_(*search_conditions)
        
        # Execute search
        results = Invoice.query.filter(final_condition).order_by(Invoice.created_at.desc()).limit(50).all()
        
        invoice_list = []
        for invoice in results:
            invoice_data = {
                "id": invoice.id,
                "customer_name": invoice.customer_name,
                "customer_phone": invoice.customer_phone,
                "customer_reg_no": invoice.customer_reg_no,
                "type_of": invoice.type_of,
                "created_at": invoice.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "balance": float(invoice.balance),
                "advance": float(invoice.advance),
                "total": float(invoice.net_total),
                "discount": float(invoice.discount),
                "include_tax": invoice.include_tax,
                "tax_amount": float(invoice.tax_amount),
                "paid_amount": float(invoice.paid_amount or 0),
                "status": invoice.status
            }
            invoice_list.append(invoice_data)
        
        # Separate quotes and invoices
        quotes = [item for item in invoice_list if item['type_of'].lower() == 'quote']
        invoices = [item for item in invoice_list if item['type_of'].lower() == 'invoice']
        
        return jsonify({
            'quotes': quotes,
            'invoices': invoices
        }), 200
        
    except Exception as e:
        logger.error(f"Error searching invoices: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection using text() for SQLAlchemy 2.0+
        db.session.execute(text('SELECT 1'))
        return jsonify({'status': 'healthy', 'database': 'connected'}), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

@bp.route('/invoice/<int:invoice_id>/convert', methods=['POST'])
def convert_quote_to_invoice(invoice_id):
    """Convert a quote to an invoice (in-place, same ID)"""
    try:
        invoice = Invoice.query.get(invoice_id)
        if not invoice:
            return jsonify({'error': 'Invoice/Quote not found'}), 404
        if invoice.type_of == 'invoice':
            return jsonify({'error': 'Already an invoice'}), 400

        # Update type and status
        invoice.type_of = 'invoice'
        invoice.status = 'unpaid'  # Set status to unpaid when converting to invoice

        # Deduct inventory for all items
        # DISABLED: Inventory is no longer deducted when converting quotes to invoices
        # items = InvoiceItem.query.filter_by(invoice_id=invoice_id).all()
        # items_data = [{'product_name': item.product_name, 'quantity': item.quantity} for item in items]
        # try:
        #     update_inventory_quantities(items_data)
        # except ValueError as e:
        #     db.session.rollback()
        #     return jsonify({'error': str(e)}), 400
        # except Exception as e:
        #     db.session.rollback()
        #     return jsonify({'error': 'Failed to update inventory'}), 500

        db.session.commit()
        return jsonify({'message': 'Quote converted to invoice successfully', 'invoice_id': invoice.id}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/invoice/<int:invoice_id>/status', methods=['PUT'])
def update_invoice_status(invoice_id):
    """Update the status of a quote/invoice"""
    try:
        data = request.get_json()
        if not data or 'status' not in data:
            return jsonify({'error': 'No status provided'}), 400
        invoice = Invoice.query.get(invoice_id)
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        invoice.status = data['status']
        db.session.commit()
        return jsonify({'message': 'Status updated', 'status': invoice.status}), 200
    except Exception as e:
        logger.error(f"Error updating invoice status {invoice_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/invoice/<int:invoice_id>/update-balance', methods=['PUT'])
def update_invoice_balance(invoice_id):
    """Add to the paid amount and update status of an invoice"""
    try:
        data = request.get_json()
        if not data or 'paid_amount' not in data:
            return jsonify({'error': 'No paid_amount provided'}), 400
        
        invoice = Invoice.query.get(invoice_id)
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        
        additional_amount = float(data['paid_amount'])
        if additional_amount < 0:
            return jsonify({'error': 'Additional amount cannot be negative'}), 400
        
        # Add to existing paid amount
        current_paid = invoice.paid_amount or 0
        invoice.paid_amount = current_paid + additional_amount
        
        # Calculate balance
        balance = invoice.net_total
        if invoice.include_tax and invoice.tax_amount:
            balance += invoice.tax_amount
        if invoice.discount:
            balance -= invoice.discount
        if invoice.advance:
            balance -= invoice.advance
        balance -= invoice.paid_amount
        
        # Update status based on total paid amount
        if invoice.paid_amount == 0:
            invoice.status = 'unpaid'
        elif balance <= 0:
            invoice.status = 'paid'
        else:
            invoice.status = 'partially_paid'
        
        db.session.commit()
        
        return jsonify({
            'message': f'Added {additional_amount:.2f} PKR to paid amount. Total paid: {invoice.paid_amount:.2f} PKR',
            'paid_amount': invoice.paid_amount,
            'balance': balance,
            'status': invoice.status
        }), 200
        
    except ValueError as e:
        return jsonify({'error': 'Invalid paid_amount value'}), 400
    except Exception as e:
        logger.error(f"Error updating invoice balance {invoice_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500
