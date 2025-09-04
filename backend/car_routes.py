from flask import Blueprint, request, jsonify
from models import db, Car, Customer
from sqlalchemy.exc import SQLAlchemyError
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

car_bp = Blueprint('car', __name__)

def validate_car_data(data):
    """Validate car data"""
    errors = []
    
    # All fields are now optional, but if provided, they must be valid
    # Make field
    if 'make' in data and data['make'] is not None and data['make'] != "N/A":
        if not str(data.get('make')).strip():
            errors.append("Car make must be a valid string if provided")
    
    # Model field
    if 'model' in data and data['model'] is not None and data['model'] != "N/A":
        if not str(data.get('model')).strip():
            errors.append("Car model must be a valid string if provided")
    
    # Plate number field
    if 'plate_no' in data and data['plate_no'] is not None and data['plate_no'] != "N/A":
        if not str(data.get('plate_no')).strip():
            errors.append("Plate number must be a valid string if provided")
    
    # Mileage field
    if 'mileage' in data and data['mileage'] is not None and data['mileage'] != "N/A":
        if not str(data.get('mileage')).strip():
            errors.append("Mileage must be a valid string if provided")
    
    # Customer ID field (optional)
    if 'customer_id' in data and data['customer_id'] is not None:
        try:
            int(data['customer_id'])
        except (ValueError, TypeError):
            errors.append("Customer ID must be a valid integer if provided")
    
    # Optional: color and chasis_no can be empty, but if present, must be string
    if 'color' in data and data['color'] is not None and data['color'] != "N/A" and not isinstance(data['color'], str):
        errors.append("Color must be a string")
    if 'chasis_no' in data and data['chasis_no'] is not None and data['chasis_no'] != "N/A" and not isinstance(data['chasis_no'], str):
        errors.append("Chasis number must be a string")
    
    return errors

def validate_customer_data(data):
    """Validate customer data"""
    errors = []
    
    # All fields are now optional, but if provided, they must be valid
    # Name field
    if 'name' in data and data['name'] is not None and data['name'] != "N/A":
        if not str(data.get('name')).strip():
            errors.append("Customer name must be a valid string if provided")
    
    # Phone field
    if 'phone' in data and data['phone'] is not None and data['phone'] != "N/A":
        if not str(data.get('phone')).strip():
            errors.append("Phone number must be a valid string if provided")
    
    # Address field
    if 'address' in data and data['address'] is not None and data['address'] != "N/A":
        if not str(data.get('address')).strip():
            errors.append("Address must be a valid string if provided")
    
    return errors

# Customer routes
@car_bp.route('/customers', methods=['GET'])
def get_customers():
    """Get all customers"""
    try:
        customers = Customer.query.all()
        customers_data = []
        
        for customer in customers:
            customers_data.append({
                'id': customer.id,
                'name': customer.name,
                'phone': customer.phone,
                'address': customer.address,
                'created_at': customer.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                'updated_at': customer.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        return jsonify(customers_data), 200
        
    except Exception as e:
        logger.error(f"Error fetching customers: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@car_bp.route('/customers', methods=['POST'])
def create_customer():
    """Create a new customer"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate input data
        validation_errors = validate_customer_data(data)
        if validation_errors:
            return jsonify({'error': 'Validation failed', 'details': validation_errors}), 400
        
        # Extract and clean data
        name = str(data.get('name')).strip()
        phone = str(data.get('phone')).strip()
        address = str(data.get('address')).strip()
        
        # Create customer
        try:
            customer = Customer(
                name=name,
                phone=phone,
                address=address
            )
            db.session.add(customer)
            db.session.commit()
            
            logger.info(f"Customer created successfully: ID {customer.id}")
            
            return jsonify({
                'message': 'Customer created successfully',
                'customer': {
                    'id': customer.id,
                    'name': customer.name,
                    'phone': customer.phone,
                    'address': customer.address,
                    'created_at': customer.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    'updated_at': customer.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                }
            }), 201
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error creating customer: {e}")
            return jsonify({'error': 'Database error occurred'}), 500
            
    except Exception as e:
        logger.error(f"Unexpected error creating customer: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@car_bp.route('/customers/<int:customer_id>', methods=['PUT'])
def update_customer(customer_id):
    """Update an existing customer"""
    try:
        if not customer_id or customer_id <= 0:
            return jsonify({'error': 'Invalid customer ID'}), 400
        
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate input data
        validation_errors = validate_customer_data(data)
        if validation_errors:
            return jsonify({'error': 'Validation failed', 'details': validation_errors}), 400
        
        # Find the customer
        customer = Customer.query.get(customer_id)
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        
        # Extract and clean data
        name = str(data.get('name')).strip()
        phone = str(data.get('phone')).strip()
        address = str(data.get('address')).strip()
        
        # Update customer
        try:
            customer.name = name
            customer.phone = phone
            customer.address = address
            
            db.session.commit()
            
            logger.info(f"Customer updated successfully: ID {customer.id}")
            
            return jsonify({
                'message': 'Customer updated successfully',
                'customer': {
                    'id': customer.id,
                    'name': customer.name,
                    'phone': customer.phone,
                    'address': customer.address,
                    'created_at': customer.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    'updated_at': customer.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                }
            }), 200
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error updating customer {customer_id}: {e}")
            return jsonify({'error': 'Database error occurred'}), 500
            
    except Exception as e:
        logger.error(f"Unexpected error updating customer {customer_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@car_bp.route('/customers/<int:customer_id>', methods=['DELETE'])
def delete_customer(customer_id):
    """Delete a customer"""
    try:
        if not customer_id or customer_id <= 0:
            return jsonify({'error': 'Invalid customer ID'}), 400
        
        # Find the customer
        customer = Customer.query.get(customer_id)
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        
        # Delete customer (this will also delete associated cars due to cascade)
        try:
            db.session.delete(customer)
            db.session.commit()
            
            logger.info(f"Customer deleted successfully: ID {customer_id}")
            
            return jsonify({
                'message': 'Customer deleted successfully',
                'deleted_customer_id': customer_id
            }), 200
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error deleting customer {customer_id}: {e}")
            return jsonify({'error': 'Database error occurred'}), 500
            
    except Exception as e:
        logger.error(f"Unexpected error deleting customer {customer_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# Car routes
@car_bp.route('/cars', methods=['GET'])
def get_cars():
    """Get all cars with customer information"""
    try:
        cars = Car.query.join(Customer).all()
        cars_data = []
        
        for car in cars:
            cars_data.append({
                'id': car.id,
                'make': car.make,
                'model': car.model,
                'plate_no': car.plate_no,
                'mileage': car.mileage,
                'vin': car.vin,
                'color': car.color,
                'chasis_no': car.chasis_no,
                'customer_id': car.customer_id,
                'customer_name': car.customer.name,
                'customer_phone': car.customer.phone,
                'created_at': car.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                'updated_at': car.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        return jsonify(cars_data), 200
        
    except Exception as e:
        logger.error(f"Error fetching cars: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@car_bp.route('/cars/<int:car_id>', methods=['GET'])
def get_car(car_id):
    """Get specific car by ID"""
    try:
        if not car_id or car_id <= 0:
            return jsonify({'error': 'Invalid car ID'}), 400
        
        car = Car.query.join(Customer).filter(Car.id == car_id).first()
        if not car:
            return jsonify({'error': 'Car not found'}), 404
        
        car_data = {
            'id': car.id,
            'make': car.make,
            'model': car.model,
            'plate_no': car.plate_no,
            'mileage': car.mileage,
            'vin': car.vin,
            'color': car.color,
            'chasis_no': car.chasis_no,
            'customer_id': car.customer_id,
            'customer_name': car.customer.name,
            'customer_phone': car.customer.phone,
            'created_at': car.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            'updated_at': car.updated_at.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return jsonify(car_data), 200
        
    except Exception as e:
        logger.error(f"Error fetching car {car_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@car_bp.route('/cars', methods=['POST'])
def create_car():
    """Create a new car"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate input data
        validation_errors = validate_car_data(data)
        if validation_errors:
            return jsonify({'error': 'Validation failed', 'details': validation_errors}), 400
        
        # Check if customer exists (if customer_id is provided)
        customer_id = data.get('customer_id')
        customer = None
        if customer_id and customer_id != "N/A":
            try:
                customer_id = int(customer_id)
                customer = Customer.query.get(customer_id)
                if not customer:
                    return jsonify({'error': 'Customer not found'}), 404
            except (ValueError, TypeError):
                customer_id = None
        
        # Get plate number (duplicate plate numbers are now allowed)
        plate_no = str(data.get('plate_no')).strip() if data.get('plate_no') else None
        
        # Extract and clean data
        make = str(data.get('make')).strip()
        model = str(data.get('model')).strip()
        mileage = str(data.get('mileage')).strip()
        vin = str(data.get('vin', '')).strip() if data.get('vin') else None
        color = str(data.get('color', '')).strip() if data.get('color') else None
        chasis_no = str(data.get('chasis_no', '')).strip() if data.get('chasis_no') else None
        
        # Create car
        try:
            car = Car(
                make=make,
                model=model,
                plate_no=plate_no,
                mileage=mileage,
                vin=vin,
                color=color,
                chasis_no=chasis_no,
                customer_id=customer_id
            )
            db.session.add(car)
            db.session.commit()
            
            logger.info(f"Car created successfully: ID {car.id}")
            
            # Get customer info safely
            customer_name = customer.name if customer else "N/A"
            customer_phone = customer.phone if customer else "N/A"
            
            return jsonify({
                'message': 'Car created successfully',
                'car': {
                    'id': car.id,
                    'make': car.make,
                    'model': car.model,
                    'plate_no': car.plate_no,
                    'mileage': car.mileage,
                    'vin': car.vin,
                    'color': car.color,
                    'chasis_no': car.chasis_no,
                    'customer_id': car.customer_id,
                    'customer_name': customer_name,
                    'customer_phone': customer_phone,
                    'created_at': car.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    'updated_at': car.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                }
            }), 201
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error creating car: {e}")
            return jsonify({'error': 'Database error occurred'}), 500
            
    except Exception as e:
        logger.error(f"Unexpected error creating car: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@car_bp.route('/cars/<int:car_id>', methods=['PUT'])
def update_car(car_id):
    """Update an existing car"""
    try:
        if not car_id or car_id <= 0:
            return jsonify({'error': 'Invalid car ID'}), 400
        
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate input data
        validation_errors = validate_car_data(data)
        if validation_errors:
            return jsonify({'error': 'Validation failed', 'details': validation_errors}), 400
        
        # Find the car
        car = Car.query.get(car_id)
        if not car:
            return jsonify({'error': 'Car not found'}), 404
        
        # Check if customer exists (if customer_id is provided)
        customer_id = data.get('customer_id')
        customer = None
        if customer_id and customer_id != "N/A":
            try:
                customer_id = int(customer_id)
                customer = Customer.query.get(customer_id)
                if not customer:
                    return jsonify({'error': 'Customer not found'}), 404
            except (ValueError, TypeError):
                customer_id = None
        
        # Get plate number (duplicate plate numbers are now allowed)
        plate_no = str(data.get('plate_no')).strip() if data.get('plate_no') else None
        
        # Extract and clean data
        make = str(data.get('make')).strip()
        model = str(data.get('model')).strip()
        mileage = str(data.get('mileage')).strip()
        vin = str(data.get('vin', '')).strip() if data.get('vin') else None
        color = str(data.get('color', '')).strip() if data.get('color') else None
        chasis_no = str(data.get('chasis_no', '')).strip() if data.get('chasis_no') else None
        
        # Update car
        try:
            car.make = make
            car.model = model
            car.plate_no = plate_no
            car.mileage = mileage
            car.vin = vin
            car.color = color
            car.chasis_no = chasis_no
            car.customer_id = customer_id
            
            db.session.commit()
            
            logger.info(f"Car updated successfully: ID {car.id}")
            
            # Get customer info safely
            customer_name = customer.name if customer else "N/A"
            customer_phone = customer.phone if customer else "N/A"
            
            return jsonify({
                'message': 'Car updated successfully',
                'car': {
                    'id': car.id,
                    'make': car.make,
                    'model': car.model,
                    'plate_no': car.plate_no,
                    'mileage': car.mileage,
                    'vin': car.vin,
                    'color': car.color,
                    'chasis_no': car.chasis_no,
                    'customer_id': car.customer_id,
                    'customer_name': customer_name,
                    'customer_phone': customer_phone,
                    'created_at': car.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    'updated_at': car.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                }
            }), 200
        
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error updating car {car_id}: {e}")
            return jsonify({'error': 'Database error occurred'}), 500
            
    except Exception as e:
        logger.error(f"Unexpected error updating car {car_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@car_bp.route('/cars/<int:car_id>', methods=['DELETE'])
def delete_car(car_id):
    """Delete a car"""
    try:
        if not car_id or car_id <= 0:
            return jsonify({'error': 'Invalid car ID'}), 400
        
        # Find the car
        car = Car.query.get(car_id)
        if not car:
            return jsonify({'error': 'Car not found'}), 404
        
        # Delete car
        try:
            db.session.delete(car)
            db.session.commit()
            
            logger.info(f"Car deleted successfully: ID {car_id}")
            
            return jsonify({
                'message': 'Car deleted successfully',
                'deleted_car_id': car_id
            }), 200
            
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Database error deleting car {car_id}: {e}")
            return jsonify({'error': 'Database error occurred'}), 500
            
    except Exception as e:
        logger.error(f"Unexpected error deleting car {car_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@car_bp.route('/cars/search', methods=['GET'])
def search_cars():
    """Search cars"""
    try:
        query = request.args.get('q', '').strip()
        
        if not query:
            return jsonify({'error': 'Search query is required'}), 400
        
        # Search in make, model, plate_no, and customer name
        search_results = Car.query.join(Customer).filter(
            db.or_(
                Car.make.ilike(f'%{query}%'),
                Car.model.ilike(f'%{query}%'),
                Car.plate_no.ilike(f'%{query}%'),
                Customer.name.ilike(f'%{query}%')
            )
        ).all()
        
        cars_data = []
        for car in search_results:
            cars_data.append({
                'id': car.id,
                'make': car.make,
                'model': car.model,
                'plate_no': car.plate_no,
                'mileage': car.mileage,
                'customer_id': car.customer_id,
                'customer_name': car.customer.name,
                'customer_phone': car.customer.phone,
                'created_at': car.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                'updated_at': car.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        return jsonify({
            'query': query,
            'results': cars_data,
            'count': len(cars_data)
        }), 200
        
    except Exception as e:
        logger.error(f"Error searching cars: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@car_bp.route('/cars/customer/<int:customer_id>', methods=['GET'])
def get_cars_by_customer(customer_id):
    """Get all cars for a specific customer"""
    try:
        if not customer_id or customer_id <= 0:
            return jsonify({'error': 'Invalid customer ID'}), 400
        
        # Check if customer exists
        customer = Customer.query.get(customer_id)
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
        
        cars = Car.query.filter_by(customer_id=customer_id).all()
        cars_data = []
        
        for car in cars:
            cars_data.append({
                'id': car.id,
                'make': car.make,
                'model': car.model,
                'plate_no': car.plate_no,
                'mileage': car.mileage,
                'customer_id': car.customer_id,
                'customer_name': customer.name,
                'customer_phone': customer.phone,
                'created_at': car.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                'updated_at': car.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        return jsonify({
            'customer': {
                'id': customer.id,
                'name': customer.name,
                'phone': customer.phone,
                'address': customer.address
            },
            'cars': cars_data,
            'count': len(cars_data)
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching cars for customer {customer_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500 