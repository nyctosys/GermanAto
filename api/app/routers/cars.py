"""FastAPI router ported from Flask. Preserves URL paths and JSON shapes."""
from __future__ import annotations

import json
import logging
import os
import re as _re
from datetime import datetime, timedelta, date
from functools import wraps
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Body, File, UploadFile, Form
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from sqlalchemy import desc, or_, and_, func, text, extract
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.deps import get_current_user, require_roles
from app.models import *  # noqa: F403,F401
from app.invoice_math import *
from app.log_utils import log_action, document_log_entries, save_uploaded_file
from app.petty_cash import wants_till, till_expenses, till_receipts
from app.period_lock import (
    guard_period, guard_both, body_date, record_date, check_period_editable, is_period_open,
)
from app.document_links import apply_links, resolve_customer, resolve_car
from app.search_suggestions import suggestions_for
from app.inventory_utils import find_inventory_item_by_name as _inv_find_by_name
from app.inventory_transaction_utils import (
    log_inventory_transaction, log_issue_out, log_received, log_adjustment, get_inventory_transactions,
)
from app.repair_order_inventory_utils import (
    deduct_inventory_quantity, process_repair_order_parts,
    handle_repair_order_edit_inventory, restore_inventory_for_deleted_repair_order,
    calculate_inventory_changes, find_inventory_item_by_part_number, find_inventory_item_by_name,
)
from app.payroll import preview as payroll_preview, run_payroll, compute_salary
from app.whatsapp_notifications import whatsapp_notifier

logger = logging.getLogger(__name__)
router = APIRouter()


def _json(data: Any = None, status: int = 200):
    return JSONResponse(content=data, status_code=status)


def _get_or_404(db: Session, model, pk):
    obj = db.get(model, pk)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found")
    return obj

from sqlalchemy.exc import SQLAlchemyError
import logging

# Configure logging
logger = logging.getLogger(__name__)


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
@router.get('/cars')
def get_cars(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get all cars with customer information"""
    try:
        cars = db.query(Car).join(Customer).all()
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
                'customer_code': car.customer.code,
                'customer_phone': car.customer.phone,
                'created_at': car.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                'updated_at': car.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        return _json(cars_data, 200)
        
    except Exception as e:
        logger.error(f"Error fetching cars: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.post('/cars')
def create_car(request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    """Create a new car"""
    try:
        data = body
        
        if not data:
            return _json({'error': 'No data provided'}, 400)
        
        # Validate input data
        validation_errors = validate_car_data(data)
        if validation_errors:
            return _json({'error': 'Validation failed', 'details': validation_errors}, 400)
        
        # Check if customer exists (if customer_id is provided)
        customer_id = data.get('customer_id')
        customer = None
        if customer_id and customer_id != "N/A":
            try:
                customer_id = int(customer_id)
                customer = db.get(Customer, customer_id)
                if not customer:
                    return _json({'error': 'Customer not found'}, 404)
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
        
        # Check for duplicate VIN if provided
        if vin:
            existing_car = db.query(Car).filter_by(vin=vin).first()
            if existing_car:
                return _json({
                    'error': 'Car with this VIN already exists',
                    'details': f'A car with VIN {vin} already exists.',
                    'existing_car_id': existing_car.id
                }, 409)
        
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
            db.add(car)
            db.commit()
            
            logger.info(f"Car created successfully: ID {car.id}")
            
            # Get customer info safely
            customer_name = customer.name if customer else "N/A"
            customer_phone = customer.phone if customer else "N/A"
            
            return _json({
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
            }, 201)
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error creating car: {e}")
            return _json({'error': 'Database error occurred'}, 500)
            
    except Exception as e:
        logger.error(f"Unexpected error creating car: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.get('/cars/customer/{customer_id:int}')
def get_cars_by_customer(customer_id, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get all cars for a specific customer"""
    try:
        if not customer_id or customer_id <= 0:
            return _json({'error': 'Invalid customer ID'}, 400)
        
        # Check if customer exists
        customer = db.get(Customer, customer_id)
        if not customer:
            return _json({'error': 'Customer not found'}, 404)
        
        cars = db.query(Car).filter_by(customer_id=customer_id).all()
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
        
        return _json({
            'customer': {
                'id': customer.id,
                'code': customer.code,
                'name': customer.name,
                'phone': customer.phone,
                'address': customer.address
            },
            'cars': cars_data,
            'count': len(cars_data)
        }, 200)
        
    except Exception as e:
        logger.error(f"Error fetching cars for customer {customer_id}: {e}")
        return _json({'error': 'Internal server error'}, 500)


@router.get('/cars/search')
def search_cars(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Search cars"""
    try:
        query = request.query_params.get('q', '').strip()
        
        if not query:
            return _json({'error': 'Search query is required'}, 400)
        
        # Search in make, model, plate_no, and customer name
        search_results = db.query(Car).join(Customer).filter(
            or_(
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
                'customer_code': car.customer.code,
                'customer_phone': car.customer.phone,
                'created_at': car.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                'updated_at': car.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        payload = {
            'query': query,
            'results': cars_data,
            'count': len(cars_data)
        }

        if query and not cars_data:
            corpus = [row[0] for row in db.query(Car.plate_no).distinct().all()]
            payload.update(suggestions_for(query, corpus))

        return _json(payload, 200)
        
    except Exception as e:
        logger.error(f"Error searching cars: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.get('/cars/{car_id:int}')
def get_car(car_id, request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get specific car by ID"""
    try:
        if not car_id or car_id <= 0:
            return _json({'error': 'Invalid car ID'}, 400)
        
        car = db.query(Car).join(Customer).filter(Car.id == car_id).first()
        if not car:
            return _json({'error': 'Car not found'}, 404)
        
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
            'customer_code': car.customer.code,
            'customer_phone': car.customer.phone,
            'created_at': car.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            'updated_at': car.updated_at.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        return _json(car_data, 200)
        
    except Exception as e:
        logger.error(f"Error fetching car {car_id}: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.put('/cars/{car_id:int}')
def update_car(car_id, request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    """Update an existing car"""
    try:
        if not car_id or car_id <= 0:
            return _json({'error': 'Invalid car ID'}, 400)
        
        data = body
        
        if not data:
            return _json({'error': 'No data provided'}, 400)
        
        # Validate input data
        validation_errors = validate_car_data(data)
        if validation_errors:
            return _json({'error': 'Validation failed', 'details': validation_errors}, 400)
        
        # Find the car
        car = db.get(Car, car_id)
        if not car:
            return _json({'error': 'Car not found'}, 404)
        
        # Check if customer exists (if customer_id is provided)
        customer_id = data.get('customer_id')
        customer = None
        if customer_id and customer_id != "N/A":
            try:
                customer_id = int(customer_id)
                customer = db.get(Customer, customer_id)
                if not customer:
                    return _json({'error': 'Customer not found'}, 404)
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
            
            db.commit()
            
            logger.info(f"Car updated successfully: ID {car.id}")
            
            # Get customer info safely
            customer_name = customer.name if customer else "N/A"
            customer_phone = customer.phone if customer else "N/A"
            
            return _json({
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
            }, 200)
        
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error updating car {car_id}: {e}")
            return _json({'error': 'Database error occurred'}, 500)
            
    except Exception as e:
        logger.error(f"Unexpected error updating car {car_id}: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.delete('/cars/{car_id:int}')
def delete_car(car_id, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Delete a car"""
    try:
        if not car_id or car_id <= 0:
            return _json({'error': 'Invalid car ID'}, 400)
        
        # Find the car
        car = db.get(Car, car_id)
        if not car:
            return _json({'error': 'Car not found'}, 404)
        
        # Delete car
        try:
            db.delete(car)
            db.commit()
            
            logger.info(f"Car deleted successfully: ID {car_id}")
            
            return _json({
                'message': 'Car deleted successfully',
                'deleted_car_id': car_id
            }, 200)
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error deleting car {car_id}: {e}")
            return _json({'error': 'Database error occurred'}, 500)
            
    except Exception as e:
        logger.error(f"Unexpected error deleting car {car_id}: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.get('/customers')
def get_customers(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get all customers"""
    try:
        customers = db.query(Customer).all()
        customers_data = []
        
        for customer in customers:
            customers_data.append({
                'id': customer.id,
                'code': customer.code,
                'name': customer.name,
                'phone': customer.phone,
                'address': customer.address,
                'created_at': customer.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                'updated_at': customer.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        return _json(customers_data, 200)
        
    except Exception as e:
        logger.error(f"Error fetching customers: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.post('/customers')
def create_customer(request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    """Create a new customer"""
    try:
        data = body
        
        if not data:
            return _json({'error': 'No data provided'}, 400)
        
        # Validate input data
        validation_errors = validate_customer_data(data)
        if validation_errors:
            return _json({'error': 'Validation failed', 'details': validation_errors}, 400)
        
        # Extract and clean data
        name = str(data.get('name')).strip()
        phone = str(data.get('phone')).strip()
        address = str(data.get('address')).strip()
        
        # Check for duplicate customer (same name + phone + address)
        existing_customer = db.query(Customer).filter_by(
            name=name,
            phone=phone,
            address=address
        ).first()
        
        if existing_customer:
            return _json({
                'error': 'Customer already exists',
                'details': f'A customer with the same name ({name}), phone ({phone}), and address ({address}) already exists.',
                'existing_customer_id': existing_customer.id
            }, 409)
        
        # Create customer
        try:
            customer = Customer(
                name=name,
                phone=phone,
                address=address
            )
            db.add(customer)
            db.commit()
            
            logger.info(f"Customer created successfully: ID {customer.id}")
            
            return _json({
                'message': 'Customer created successfully',
                'customer': {
                    'id': customer.id,
                    'code': customer.code,
                    'name': customer.name,
                    'phone': customer.phone,
                    'address': customer.address,
                    'created_at': customer.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    'updated_at': customer.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                }
            }, 201)
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error creating customer: {e}")
            return _json({'error': 'Database error occurred'}, 500)
            
    except Exception as e:
        logger.error(f"Unexpected error creating customer: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.get('/customers/search')
def search_customers(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Search customers"""
    try:
        query = request.query_params.get('q', '').strip()
        
        if not query:
            return _json({'error': 'Search query is required'}, 400)
        
        # Search in name, phone, and address
        search_results = db.query(Customer).filter(
            or_(
                Customer.name.ilike(f'%{query}%'),
                Customer.phone.ilike(f'%{query}%'),
                Customer.address.ilike(f'%{query}%')
            )
        ).all()
        
        customers_data = []
        for customer in search_results:
            customers_data.append({
                'id': customer.id,
                'code': customer.code,
                'name': customer.name,
                'phone': customer.phone,
                'address': customer.address,
                'created_at': customer.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                'updated_at': customer.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        payload = {
            'query': query,
            'results': customers_data,
            'count': len(customers_data)
        }

        if query and not customers_data:
            corpus = [row[0] for row in db.query(Customer.name).distinct().all()]
            payload.update(suggestions_for(query, corpus))

        return _json(payload, 200)
        
    except Exception as e:
        logger.error(f"Error searching customers: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.put('/customers/{customer_id:int}')
def update_customer(customer_id, request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'accountant', 'inventory_manager']))):
    """Update an existing customer"""
    try:
        if not customer_id or customer_id <= 0:
            return _json({'error': 'Invalid customer ID'}, 400)
        
        data = body
        
        if not data:
            return _json({'error': 'No data provided'}, 400)
        
        # Validate input data
        validation_errors = validate_customer_data(data)
        if validation_errors:
            return _json({'error': 'Validation failed', 'details': validation_errors}, 400)
        
        # Find the customer
        customer = db.get(Customer, customer_id)
        if not customer:
            return _json({'error': 'Customer not found'}, 404)
        
        # Extract and clean data
        name = str(data.get('name')).strip()
        phone = str(data.get('phone')).strip()
        address = str(data.get('address')).strip()
        
        # Update customer
        try:
            customer.name = name
            customer.phone = phone
            customer.address = address
            
            db.commit()
            
            logger.info(f"Customer updated successfully: ID {customer.id}")
            
            return _json({
                'message': 'Customer updated successfully',
                'customer': {
                    'id': customer.id,
                    'code': customer.code,
                    'name': customer.name,
                    'phone': customer.phone,
                    'address': customer.address,
                    'created_at': customer.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    'updated_at': customer.updated_at.strftime("%Y-%m-%d %H:%M:%S")
                }
            }, 200)
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error updating customer {customer_id}: {e}")
            return _json({'error': 'Database error occurred'}, 500)
            
    except Exception as e:
        logger.error(f"Unexpected error updating customer {customer_id}: {e}")
        return _json({'error': 'Internal server error'}, 500)

@router.delete('/customers/{customer_id:int}')
def delete_customer(customer_id, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Delete a customer"""
    try:
        if not customer_id or customer_id <= 0:
            return _json({'error': 'Invalid customer ID'}, 400)
        
        # Find the customer
        customer = db.get(Customer, customer_id)
        if not customer:
            return _json({'error': 'Customer not found'}, 404)
        
        # Delete customer (this will also delete associated cars due to cascade)
        try:
            db.delete(customer)
            db.commit()
            
            logger.info(f"Customer deleted successfully: ID {customer_id}")
            
            return _json({
                'message': 'Customer deleted successfully',
                'deleted_customer_id': customer_id
            }, 200)
            
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error deleting customer {customer_id}: {e}")
            return _json({'error': 'Database error occurred'}, 500)
            
    except Exception as e:
        logger.error(f"Unexpected error deleting customer {customer_id}: {e}")
        return _json({'error': 'Internal server error'}, 500)

# Car routes
