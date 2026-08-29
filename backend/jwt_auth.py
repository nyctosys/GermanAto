"""
Centralized JWT Authentication Utilities
This module provides consistent JWT authentication decorators and utilities
for all route files in the application.
"""

from flask import jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from models import User
from functools import wraps
import logging

logger = logging.getLogger(__name__)

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
            
            # Add user to kwargs for use in route functions
            kwargs['current_user'] = user
            
            return f(*args, **kwargs)
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
                
                # Convert to list if string
                roles_list = [required_roles] if isinstance(required_roles, str) else required_roles
                
                # Dynamic role permissions check
                from models import RolePermission
                from flask import request
                
                path = request.path
                permission_needed = None
                
                if '/api/invoice' in path or '/api/quotes' in path:
                    permission_needed = 'invoice'
                elif '/api/inventory' in path:
                    permission_needed = 'inventory'
                elif '/api/cars' in path:
                    permission_needed = 'car'
                elif '/api/expenses' in path or '/api/cash-received' in path:
                    if '/api/expenses/major' in path:
                        permission_needed = 'major-expenses'
                    else:
                        permission_needed = 'daily-expenses'
                elif '/api/vendors' in path or '/api/ledger' in path or '/api/purchase-orders' in path:
                    permission_needed = 'vendors'
                elif '/api/workers' in path or '/api/salaries' in path or '/api/attendance' in path:
                    permission_needed = 'hr'
                elif '/api/repair-orders' in path:
                    permission_needed = 'repair-order'
                elif '/api/admin' in path:
                    permission_needed = 'admin'

                # If user is admin, they always have access
                if user.role == 'admin':
                    pass
                else:
                    if permission_needed:
                        has_perm = RolePermission.query.filter_by(role=user.role, permission=permission_needed).first() is not None
                        if not has_perm:
                            return jsonify({'error': 'Insufficient permissions'}), 403
                    else:
                        if user.role not in roles_list:
                            return jsonify({'error': 'Insufficient permissions'}), 403
                
                # Add user to kwargs for use in route functions
                kwargs['current_user'] = user
                
                return f(*args, **kwargs)
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
