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

"""
Settings API Routes
Handles settings management including departments, categories, and theme preferences
"""

from sqlalchemy import desc
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# ===== DEPARTMENT ROUTES =====

@router.get('/settings/departments')
def get_departments(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get all departments from the central Department table"""
    try:
        departments = db.query(Department).order_by(Department.name).all()
        
        return _json({
            'departments': [dept.to_dict() for dept in departments],
            'count': len(departments)
        }, 200)
    except Exception as e:
        logger.error(f"Error fetching departments: {e}")
        return _json({'error': 'Internal server error'}, 500)


@router.post('/settings/departments')
def create_department(request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Create a new department"""
    try:
        data = body
        
        if not data or not data.get('name'):
            return _json({'error': 'Department name is required'}, 400)
        
        name = data.get('name').strip()
        description = data.get('description', '').strip() if data.get('description') else None
        
        # Check if department already exists
        existing = db.query(Department).filter_by(name=name).first()
        if existing:
            return _json({'error': 'Department with this name already exists'}, 400)
        
        new_department = Department(
            name=name,
            description=description,
            is_active=True
        )
        
        db.add(new_department)
        db.commit()
        
        return _json({
            'message': 'Department created successfully',
            'department': new_department.to_dict()
        }, 201)
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating department: {e}")
        return _json({'error': 'Internal server error'}, 500)


@router.put('/settings/departments/{department_id:int}')
def update_department(department_id: int, request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Update a department"""
    try:
        department = _get_or_404(db, Department, department_id)
        data = body
        
        if not data:
            return _json({'error': 'No data provided'}, 400)
        
        if 'name' in data:
            name = data.get('name').strip()
            if not name:
                return _json({'error': 'Department name cannot be empty'}, 400)
            
            # Check if another department with this name exists
            existing = db.query(Department).filter_by(name=name).first()
            if existing and existing.id != department_id:
                return _json({'error': 'Department with this name already exists'}, 400)
            
            department.name = name
        
        if 'description' in data:
            department.description = data.get('description').strip() if data.get('description') else None
        
        if 'is_active' in data:
            department.is_active = bool(data.get('is_active'))
        
        department.updated_at = datetime.utcnow()
        db.commit()
        
        return _json({
            'message': 'Department updated successfully',
            'department': department.to_dict()
        }, 200)
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating department: {e}")
        return _json({'error': 'Internal server error'}, 500)


@router.delete('/settings/departments/{department_id:int}')
def delete_department(department_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'accountant']))):
    """Delete a department permanently"""
    try:
        department = _get_or_404(db, Department, department_id)
        
        # Permanently delete the department
        db.delete(department)
        db.commit()
        
        return _json({
            'message': 'Department deleted successfully'
        }, 200)
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting department: {e}")
        return _json({'error': 'Internal server error'}, 500)


# ===== CATEGORY ROUTES =====

@router.get('/settings/categories')
def get_categories(request: Request, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Get all categories from the central Category table"""
    try:
        categories = db.query(Category).order_by(Category.name).all()
        
        return _json({
            'categories': [cat.to_dict() for cat in categories],
            'count': len(categories)
        }, 200)
    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        return _json({'error': 'Internal server error'}, 500)


@router.post('/settings/categories')
def create_category(request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'inventory_manager']))):
    """Create a new category"""
    try:
        data = body
        
        if not data or not data.get('name'):
            return _json({'error': 'Category name is required'}, 400)
        
        name = data.get('name').strip()
        description = data.get('description', '').strip() if data.get('description') else None
        
        # Check if category already exists
        existing = db.query(Category).filter_by(name=name).first()
        if existing:
            return _json({'error': 'Category with this name already exists'}, 400)
        
        new_category = Category(
            name=name,
            description=description,
            is_active=True
        )
        
        db.add(new_category)
        db.commit()
        
        return _json({
            'message': 'Category created successfully',
            'category': new_category.to_dict()
        }, 201)
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating category: {e}")
        return _json({'error': 'Internal server error'}, 500)


@router.put('/settings/categories/{category_id:int}')
def update_category(category_id: int, request: Request, db: Session = Depends(get_db), body: dict | None = Body(None), current_user=Depends(require_roles(['admin', 'inventory_manager']))):
    """Update a category"""
    try:
        category = _get_or_404(db, Category, category_id)
        data = body
        
        if not data:
            return _json({'error': 'No data provided'}, 400)
        
        if 'name' in data:
            name = data.get('name').strip()
            if not name:
                return _json({'error': 'Category name cannot be empty'}, 400)
            
            # Check if another category with this name exists
            existing = db.query(Category).filter_by(name=name).first()
            if existing and existing.id != category_id:
                return _json({'error': 'Category with this name already exists'}, 400)
            
            category.name = name
        
        if 'description' in data:
            category.description = data.get('description').strip() if data.get('description') else None
        
        if 'is_active' in data:
            category.is_active = bool(data.get('is_active'))
        
        category.updated_at = datetime.utcnow()
        db.commit()
        
        return _json({
            'message': 'Category updated successfully',
            'category': category.to_dict()
        }, 200)
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating category: {e}")
        return _json({'error': 'Internal server error'}, 500)


@router.delete('/settings/categories/{category_id:int}')
def delete_category(category_id: int, request: Request, db: Session = Depends(get_db), current_user=Depends(require_roles(['admin', 'inventory_manager']))):
    """Delete a category permanently"""
    try:
        category = _get_or_404(db, Category, category_id)
        
        # Permanently delete the category
        db.delete(category)
        db.commit()
        
        return _json({
            'message': 'Category deleted successfully'
        }, 200)
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting category: {e}")
        return _json({'error': 'Internal server error'}, 500)
