from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token, 
    create_refresh_token, 
    jwt_required, 
    get_jwt_identity,
    get_jwt
)
from models import db, User
from datetime import datetime
from functools import wraps
from sqlalchemy.exc import SQLAlchemyError
from jwt_auth import ADMIN_PERMISSIONS, DEFAULT_ROLE_PERMISSIONS

auth_bp = Blueprint('auth', __name__)

# Role-based access decorator
def role_required(required_roles):
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
                
                if user.role not in roles_list:
                    return jsonify({'error': 'Insufficient permissions'}), 403
                
                return f(*args, **kwargs)
            except (ValueError, TypeError) as e:
                return jsonify({'error': 'Invalid user ID format'}), 401
            except Exception as e:
                return jsonify({'error': 'Authentication error'}), 500
        return decorated_function
    return decorator

# Login required decorator (simpler version)
def login_required(f):
    @wraps(f)
    @jwt_required()
    def decorated_function(*args, **kwargs):
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))
        
        if not user or not user.is_active:
            return jsonify({'error': 'User not found or inactive'}), 401
        
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/register', methods=['POST'])
@role_required('admin')
def register():
    """Register a new user (admin only)"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Validate required fields
    required_fields = ['username', 'email', 'password', 'role']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400
    
    # Check if user already exists
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 400
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 400
    
    # Validate role
    valid_roles = ['admin', 'accountant', 'inventory_manager']
    if data['role'] not in valid_roles:
        return jsonify({'error': 'Invalid role'}), 400
    
    try:
        # Create new user
        user = User(
            username=data['username'],
            email=data['email'],
            role=data['role']
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        return jsonify({
            'message': 'User created successfully',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'is_active': user.is_active
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create user'}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user and return JWT tokens"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
    
    # Find user
    user = User.query.filter_by(username=username).first()
    
    if not user or not user.check_password(password) or not user.is_active:
        return jsonify({'error': 'Invalid username or password'}), 401
    
    try:
        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Create tokens
        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))
        
        return jsonify({
            'message': 'Login successful',
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role
            }
        })
        
    except Exception as e:
        return jsonify({'error': 'Login failed'}), 500

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token using refresh token"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))
        
        if not user or not user.is_active:
            return jsonify({'error': 'User not found or inactive'}), 401
        
        # Create new access token
        new_access_token = create_access_token(identity=str(current_user_id))
        
        return jsonify({
            'access_token': new_access_token,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role
            }
        })
        
    except Exception as e:
        return jsonify({'error': 'Token refresh failed'}), 500

@auth_bp.route('/verify', methods=['GET'])
@jwt_required()
def verify():
    """Verify token and return current user info"""
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))
        
        if not user or not user.is_active:
            return jsonify({'error': 'User not found or inactive'}), 401
        
        return jsonify({
            'authenticated': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role
            }
        })
        
    except Exception as e:
        return jsonify({'error': 'Token verification failed'}), 500

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Logout user (client should clear tokens)"""
    # Note: JWT validation removed to allow logout even with expired tokens
    # In a more advanced setup, you could blacklist the token here
    return jsonify({'message': 'Logout successful'})

@auth_bp.route('/users', methods=['GET'])
@role_required('admin')
def get_users():
    """Get all users (admin only)"""
    try:
        users = User.query.all()
        return jsonify([{
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'is_active': user.is_active,
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'last_login': user.last_login.isoformat() if user.last_login else None
        } for user in users])
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch users'}), 500

@auth_bp.route('/users/<int:user_id>', methods=['PUT'])
@role_required('admin')
def update_user(user_id):
    """Update user (admin only)"""
    try:
        user = User.query.get_or_404(user_id)
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Prevent admin from updating themselves
        current_user_id = get_jwt_identity()
        if user.id == int(current_user_id):
            return jsonify({'error': 'Cannot update your own account'}), 400
        
        # Update fields
        if 'username' in data and data['username'] != user.username:
            if User.query.filter_by(username=data['username']).first():
                return jsonify({'error': 'Username already exists'}), 400
            user.username = data['username']
        
        if 'email' in data and data['email'] != user.email:
            if User.query.filter_by(email=data['email']).first():
                return jsonify({'error': 'Email already exists'}), 400
            user.email = data['email']
        
        if 'role' in data:
            valid_roles = ['admin', 'accountant', 'inventory_manager']
            if data['role'] not in valid_roles:
                return jsonify({'error': 'Invalid role'}), 400
            user.role = data['role']
        
        if 'is_active' in data:
            user.is_active = data['is_active']
        
        if 'password' in data and data['password']:
            user.set_password(data['password'])
        
        db.session.commit()
        
        return jsonify({
            'message': 'User updated successfully',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'is_active': user.is_active
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update user'}), 500

@auth_bp.route('/users/<int:user_id>', methods=['DELETE'])
@role_required('admin')
def delete_user(user_id):
    """Delete user (admin only)"""
    try:
        user = User.query.get_or_404(user_id)
        
        # Prevent admin from deleting themselves
        current_user_id = get_jwt_identity()
        if user.id == int(current_user_id):
            return jsonify({'error': 'Cannot delete your own account'}), 400
        
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({'message': 'User deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to delete user'}), 500

@auth_bp.route('/roles-permissions', methods=['GET'])
@role_required('admin')
def get_roles_permissions():
    """Get all role permissions (admin only)"""
    from models import RolePermission
    try:
        roles = ['accountant', 'inventory_manager']
        all_perms = RolePermission.query.all()
        
        result = {}
        for r in roles:
            result[r] = [p.permission for p in all_perms if p.role == r]
            
        return jsonify(result), 200
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({
            'accountant': DEFAULT_ROLE_PERMISSIONS['accountant'],
            'inventory_manager': DEFAULT_ROLE_PERMISSIONS['inventory_manager'],
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/roles-permissions', methods=['PUT'])
@role_required('admin')
def update_roles_permissions():
    """Update role permissions (admin only)"""
    from models import RolePermission
    try:
        data = request.get_json() or {}
        valid_roles = ['accountant', 'inventory_manager']
        
        # Clear existing permissions
        RolePermission.query.filter(RolePermission.role.in_(valid_roles)).delete(synchronize_session=False)
        
        # Insert new permissions
        for role, permissions in data.items():
            if role in valid_roles:
                for perm in permissions:
                    new_perm = RolePermission(role=role, permission=perm)
                    db.session.add(new_perm)
                    
        db.session.commit()
        return jsonify({'message': 'Permissions updated successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@auth_bp.route('/permissions/my', methods=['GET'])
@jwt_required()
def get_my_permissions():
    """Get permissions for current user's role"""
    from models import RolePermission
    try:
        current_user_id = get_jwt_identity()
        user = User.query.get(int(current_user_id))
        if not user:
            return jsonify({'error': 'User not found'}), 404
            
        if user.role == 'admin':
            return jsonify({'role': user.role, 'permissions': ADMIN_PERMISSIONS}), 200
            
        perms = RolePermission.query.filter_by(role=user.role).all()
        result = [p.permission for p in perms]
        if not result and RolePermission.query.first() is None:
            result = DEFAULT_ROLE_PERMISSIONS.get(user.role, [])
        
        return jsonify({'role': user.role, 'permissions': result}), 200
    except SQLAlchemyError:
        db.session.rollback()
        permissions = DEFAULT_ROLE_PERMISSIONS.get(user.role, []) if 'user' in locals() and user else []
        return jsonify({'role': user.role if 'user' in locals() and user else None, 'permissions': permissions}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
