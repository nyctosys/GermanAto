"""
Settings API Routes
Handles settings management including departments, categories, and theme preferences
"""

from flask import Blueprint, request, jsonify
from models import db, Department, Category
from sqlalchemy import desc
from datetime import datetime
import logging
from jwt_auth import login_required, role_required, admin_required

logger = logging.getLogger(__name__)

settings_bp = Blueprint('settings', __name__)

# ===== DEPARTMENT ROUTES =====

@settings_bp.route('/settings/departments', methods=['GET'])
@login_required
def get_departments(current_user=None):
    """Get all departments from the central Department table"""
    try:
        departments = Department.query.order_by(Department.name).all()
        
        return jsonify({
            'departments': [dept.to_dict() for dept in departments],
            'count': len(departments)
        }), 200
    except Exception as e:
        logger.error(f"Error fetching departments: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@settings_bp.route('/settings/departments', methods=['POST'])
@role_required(['admin', 'accountant'])
def create_department(current_user=None):
    """Create a new department"""
    try:
        data = request.get_json()
        
        if not data or not data.get('name'):
            return jsonify({'error': 'Department name is required'}), 400
        
        name = data.get('name').strip()
        description = data.get('description', '').strip() if data.get('description') else None
        
        # Check if department already exists
        existing = Department.query.filter_by(name=name).first()
        if existing:
            return jsonify({'error': 'Department with this name already exists'}), 400
        
        new_department = Department(
            name=name,
            description=description,
            is_active=True
        )
        
        db.session.add(new_department)
        db.session.commit()
        
        return jsonify({
            'message': 'Department created successfully',
            'department': new_department.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating department: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@settings_bp.route('/settings/departments/<int:department_id>', methods=['PUT'])
@role_required(['admin', 'accountant'])
def update_department(current_user=None, department_id=None):
    """Update a department"""
    try:
        department = Department.query.get_or_404(department_id)
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        if 'name' in data:
            name = data.get('name').strip()
            if not name:
                return jsonify({'error': 'Department name cannot be empty'}), 400
            
            # Check if another department with this name exists
            existing = Department.query.filter_by(name=name).first()
            if existing and existing.id != department_id:
                return jsonify({'error': 'Department with this name already exists'}), 400
            
            department.name = name
        
        if 'description' in data:
            department.description = data.get('description').strip() if data.get('description') else None
        
        if 'is_active' in data:
            department.is_active = bool(data.get('is_active'))
        
        department.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Department updated successfully',
            'department': department.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating department: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@settings_bp.route('/settings/departments/<int:department_id>', methods=['DELETE'])
@role_required(['admin', 'accountant'])
def delete_department(current_user=None, department_id=None):
    """Delete a department permanently"""
    try:
        department = Department.query.get_or_404(department_id)
        
        # Permanently delete the department
        db.session.delete(department)
        db.session.commit()
        
        return jsonify({
            'message': 'Department deleted successfully'
        }), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting department: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# ===== CATEGORY ROUTES =====

@settings_bp.route('/settings/categories', methods=['GET'])
@login_required
def get_categories(current_user=None):
    """Get all categories from the central Category table"""
    try:
        categories = Category.query.order_by(Category.name).all()
        
        return jsonify({
            'categories': [cat.to_dict() for cat in categories],
            'count': len(categories)
        }), 200
    except Exception as e:
        logger.error(f"Error fetching categories: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@settings_bp.route('/settings/categories', methods=['POST'])
@role_required(['admin', 'inventory_manager'])
def create_category(current_user=None):
    """Create a new category"""
    try:
        data = request.get_json()
        
        if not data or not data.get('name'):
            return jsonify({'error': 'Category name is required'}), 400
        
        name = data.get('name').strip()
        description = data.get('description', '').strip() if data.get('description') else None
        
        # Check if category already exists
        existing = Category.query.filter_by(name=name).first()
        if existing:
            return jsonify({'error': 'Category with this name already exists'}), 400
        
        new_category = Category(
            name=name,
            description=description,
            is_active=True
        )
        
        db.session.add(new_category)
        db.session.commit()
        
        return jsonify({
            'message': 'Category created successfully',
            'category': new_category.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating category: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@settings_bp.route('/settings/categories/<int:category_id>', methods=['PUT'])
@role_required(['admin', 'inventory_manager'])
def update_category(current_user=None, category_id=None):
    """Update a category"""
    try:
        category = Category.query.get_or_404(category_id)
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        if 'name' in data:
            name = data.get('name').strip()
            if not name:
                return jsonify({'error': 'Category name cannot be empty'}), 400
            
            # Check if another category with this name exists
            existing = Category.query.filter_by(name=name).first()
            if existing and existing.id != category_id:
                return jsonify({'error': 'Category with this name already exists'}), 400
            
            category.name = name
        
        if 'description' in data:
            category.description = data.get('description').strip() if data.get('description') else None
        
        if 'is_active' in data:
            category.is_active = bool(data.get('is_active'))
        
        category.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Category updated successfully',
            'category': category.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating category: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@settings_bp.route('/settings/categories/<int:category_id>', methods=['DELETE'])
@role_required(['admin', 'inventory_manager'])
def delete_category(current_user=None, category_id=None):
    """Delete a category permanently"""
    try:
        category = Category.query.get_or_404(category_id)
        
        # Permanently delete the category
        db.session.delete(category)
        db.session.commit()
        
        return jsonify({
            'message': 'Category deleted successfully'
        }), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting category: {e}")
        return jsonify({'error': 'Internal server error'}), 500
