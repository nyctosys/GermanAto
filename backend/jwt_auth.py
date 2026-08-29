"""
Centralized JWT Authentication Utilities
This module provides consistent JWT authentication decorators and utilities
for all route files in the application.
"""

from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from models import db, User
from functools import wraps
from inspect import Parameter, signature
import logging
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

ADMIN_PERMISSIONS = [
    'home', 'invoice', 'search', 'inventory', 'car', 'reports',
    'admin', 'daily-expenses', 'major-expenses', 'vendors',
    'vendor-detail', 'hr', 'worker-detail', 'repair-order',
    'repair-orders-management', 'settings', 'logs'
]

DEFAULT_ROLE_PERMISSIONS = {
    'admin': ADMIN_PERMISSIONS,
    'accountant': [
        'home', 'invoice', 'search', 'car', 'daily-expenses', 'vendors',
        'vendor-detail', 'hr', 'worker-detail', 'repair-order',
        'repair-orders-management', 'settings'
    ],
    'inventory_manager': [
        'home', 'inventory', 'repair-order', 'repair-orders-management',
        'settings'
    ],
}

PATH_PERMISSIONS = (
    ('/api/admin/app-logs', 'logs'),
    ('/api/reports', 'reports'),
    ('/api/settings', 'settings'),
    ('/api/inventory', 'inventory'),
    ('/api/customers', 'car'),
    ('/api/cars', 'car'),
    ('/api/expenses/major', 'major-expenses'),
    ('/api/expenses', 'daily-expenses'),
    ('/api/cash-received', 'daily-expenses'),
    ('/api/vendors', 'vendors'),
    ('/api/ledger', 'vendors'),
    ('/api/purchase-orders', 'vendors'),
    ('/api/consignments', 'vendors'),
    ('/api/workers', 'hr'),
    ('/api/salaries', 'hr'),
    ('/api/salary', 'hr'),
    ('/api/attendance', 'hr'),
    ('/api/zkteco', 'hr'),
    ('/api/repair-orders', 'repair-order'),
    ('/api/invoice', 'invoice'),
    ('/api/quotes', 'invoice'),
    ('/api/add', 'invoice'),
    ('/api/search', 'invoice'),
)


def _accepts_current_user(f):
    try:
        params = signature(f).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(
        p.name == 'current_user' or p.kind == Parameter.VAR_KEYWORD
        for p in params
    )


def _call_route(f, user, *args, **kwargs):
    if _accepts_current_user(f) and 'current_user' not in kwargs:
        kwargs['current_user'] = user
    return f(*args, **kwargs)


def get_permission_for_path(path):
    for prefix, permission in PATH_PERMISSIONS:
        if path.startswith(prefix):
            return permission
    return None


def has_configured_permission(user, permission, fallback_roles):
    if user.role == 'admin':
        return True

    roles_list = [fallback_roles] if isinstance(fallback_roles, str) else fallback_roles
    fallback_allowed = user.role in roles_list

    if not permission:
        return fallback_allowed

    try:
        from models import RolePermission

        if RolePermission.query.first() is None:
            return fallback_allowed

        return RolePermission.query.filter_by(
            role=user.role,
            permission=permission
        ).first() is not None
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.warning(f"Role permission lookup failed, using route fallback: {e}")
        return fallback_allowed

def login_required(f):
    """
    Decorator to require JWT authentication for a route.
    Validates the JWT token and ensures the user is active.
    """
    @wraps(f)
    @jwt_required()
    def decorated_function(*args, **kwargs):
        try:
            current_user_id = get_jwt_identity()
            if not current_user_id:
                return jsonify({'error': 'Invalid token'}), 401
            
            user = User.query.get(int(current_user_id))
            
            if not user or not user.is_active:
                return jsonify({'error': 'User not found or inactive'}), 401
            
            return _call_route(f, user, *args, **kwargs)
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid user ID format: {e}")
            return jsonify({'error': 'Invalid user ID format'}), 401
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return jsonify({'error': 'Authentication error'}), 500
    return decorated_function

def role_required(required_roles):
    """
    Decorator to require specific roles for accessing a route.
    
    Args:
        required_roles: String or list of strings representing required roles
    """
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            try:
                current_user_id = get_jwt_identity()
                if not current_user_id:
                    return jsonify({'error': 'Invalid token'}), 401
                
                user = User.query.get(int(current_user_id))
                
                if not user or not user.is_active:
                    return jsonify({'error': 'User not found or inactive'}), 401
                
                permission_needed = get_permission_for_path(request.path)
                if not has_configured_permission(user, permission_needed, required_roles):
                    return jsonify({'error': 'Insufficient permissions'}), 403

                return _call_route(f, user, *args, **kwargs)
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid user ID format: {e}")
                return jsonify({'error': 'Invalid user ID format'}), 401
            except Exception as e:
                logger.error(f"Authentication error: {e}")
                return jsonify({'error': 'Authentication error'}), 500
        return decorated_function
    return decorator

def admin_required(f):
    """
    Decorator to require admin role for accessing a route.
    Shorthand for role_required('admin').
    """
    return role_required('admin')(f)

def get_current_user():
    """
    Helper function to get the current authenticated user.
    Should be called within a JWT-protected route.
    """
    try:
        current_user_id = get_jwt_identity()
        if not current_user_id:
            return None
        
        user = User.query.get(int(current_user_id))
        return user if user and user.is_active else None
    except (ValueError, TypeError):
        return None
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        return None

def check_user_permissions(user, required_roles):
    """
    Helper function to check if a user has the required permissions.
    
    Args:
        user: User object
        required_roles: String or list of strings representing required roles
    
    Returns:
        bool: True if user has required permissions, False otherwise
    """
    if not user or not user.is_active:
        return False
    
    roles_list = [required_roles] if isinstance(required_roles, str) else required_roles
    return user.role in roles_list

def get_user_from_token():
    """
    Helper function to get user from JWT token.
    Returns user object or None if invalid.
    """
    try:
        current_user_id = get_jwt_identity()
        if not current_user_id:
            return None
        
        user = User.query.get(int(current_user_id))
        return user if user and user.is_active else None
    except Exception as e:
        logger.error(f"Error getting user from token: {e}")
        return None
