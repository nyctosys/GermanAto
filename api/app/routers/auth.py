import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, get_refresh_user, require_roles
from app.foundation.roles import (
    ADMIN_PERMISSIONS,
    DEFAULT_ROLE_PERMISSIONS,
    PERMISSION_ROLES,
    VALID_ROLES,
)
from app.models import RolePermission, User
from app.schemas import (
    LoginRequest,
    LoginResponse,
    MessageResponse,
    MyPermissions,
    RefreshResponse,
    RegisterRequest,
    RegisterResponse,
    UserListItem,
    UserMutationResponse,
    UserUpdate,
    VerifyResponse,
)
from app.security import create_access_token, create_refresh_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _error(message: str, status: int) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


def _auth_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
    }


def _registered_user(user: User) -> dict:
    body = _auth_user(user)
    body["is_active"] = user.is_active
    return body


@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    for field in ("username", "email", "password", "role"):
        if not getattr(data, field):
            return _error(f"{field} is required", 400)
    if data.role not in VALID_ROLES:
        return _error("Invalid role", 400)
    if db.scalar(select(User).where(User.username == data.username)):
        return _error("Username already exists", 400)
    if db.scalar(select(User).where(User.email == data.email)):
        return _error("Email already exists", 400)

    user = User(username=data.username, email=str(data.email), role=data.role)
    user.set_password(data.password)
    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        logger.exception("register failed")
        return _error("Failed to create user", 500)

    return {"message": "User created successfully", "user": _registered_user(user)}


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    if not data.username or not data.password:
        return _error("Username and password are required", 400)

    user = db.scalar(select(User).where(User.username == data.username))
    if not user or not user.check_password(data.password) or not user.is_active:
        return _error("Invalid username or password", 401)

    try:
        user.last_login = datetime.utcnow()
        db.commit()
        return {
            "message": "Login successful",
            "access_token": create_access_token(user.id),
            "refresh_token": create_refresh_token(user.id),
            "user": _auth_user(user),
        }
    except Exception:
        db.rollback()
        logger.exception("login failed")
        return _error("Login failed", 500)


@router.post("/refresh", response_model=RefreshResponse)
def refresh(user: User = Depends(get_refresh_user)):
    try:
        return {"access_token": create_access_token(user.id), "user": _auth_user(user)}
    except Exception:
        logger.exception("refresh failed")
        return _error("Token refresh failed", 500)


@router.get("/verify", response_model=VerifyResponse)
def verify(user: User = Depends(get_current_user)):
    return {"authenticated": True, "user": _auth_user(user)}


@router.post("/logout", response_model=MessageResponse)
def logout():
    return {"message": "Logout successful"}


@router.get("/users", response_model=list[UserListItem])
def get_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    from app.foundation.context import skip_branch_scope

    token = skip_branch_scope.set(True)
    try:
        users = db.scalars(select(User)).all()
    except Exception:
        logger.exception("list users failed")
        return _error("Failed to fetch users", 500)
    finally:
        skip_branch_scope.reset(token)

    return [
        {
            **_registered_user(user),
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "last_login": user.last_login.isoformat() if user.last_login else None,
        }
        for user in users
    ]


@router.put("/users/{user_id:int}", response_model=UserMutationResponse)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("admin")),
):
    user = db.get(User, user_id)
    if user is None:
        return _error("Not found", 404)
    if user.id == current.id:
        return _error("Cannot update your own account", 400)

    fields = data.model_dump(exclude_unset=True)
    try:
        if "username" in fields and fields["username"] != user.username:
            if not fields["username"]:
                return _error("username is required", 400)
            if db.scalar(select(User).where(User.username == fields["username"])):
                return _error("Username already exists", 400)
            user.username = fields["username"]

        if "email" in fields and fields["email"] != user.email:
            if not fields["email"]:
                return _error("email is required", 400)
            if db.scalar(select(User).where(User.email == str(fields["email"]))):
                return _error("Email already exists", 400)
            user.email = str(fields["email"])

        if "role" in fields:
            if fields["role"] not in VALID_ROLES:
                return _error("Invalid role", 400)
            user.role = fields["role"]

        if "is_active" in fields:
            user.is_active = fields["is_active"]

        if fields.get("password"):
            user.set_password(fields["password"])

        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        logger.exception("update user failed")
        return _error("Failed to update user", 500)

    return {"message": "User updated successfully", "user": _registered_user(user)}


@router.delete("/users/{user_id:int}", response_model=MessageResponse)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current: User = Depends(require_roles("admin")),
):
    user = db.get(User, user_id)
    if user is None:
        return _error("Not found", 404)
    if user.id == current.id:
        return _error("Cannot delete your own account", 400)
    try:
        db.delete(user)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("delete user failed")
        return _error("Failed to delete user", 500)
    return {"message": "User deleted successfully"}


@router.get("/roles-permissions")
def get_roles_permissions(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    try:
        rows = db.scalars(select(RolePermission)).all()
    except SQLAlchemyError:
        db.rollback()
        return {role: list(DEFAULT_ROLE_PERMISSIONS.get(role, [])) for role in PERMISSION_ROLES}
    except Exception as exc:
        logger.exception("read role permissions failed")
        return _error(str(exc), 500)

    if not rows:
        return {role: list(DEFAULT_ROLE_PERMISSIONS.get(role, [])) for role in PERMISSION_ROLES}
    return {role: [row.permission for row in rows if row.role == role] for role in PERMISSION_ROLES}


@router.put("/roles-permissions", response_model=MessageResponse)
def update_roles_permissions(
    data: dict[str, list[str]],
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    try:
        db.execute(delete(RolePermission).where(RolePermission.role.in_(PERMISSION_ROLES)))
        for role, permissions in data.items():
            if role not in PERMISSION_ROLES:
                continue
            for perm in permissions:
                db.add(RolePermission(role=role, permission=perm))
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("update role permissions failed")
        return _error(str(exc), 500)
    return {"message": "Permissions updated successfully"}


@router.get("/permissions/my", response_model=MyPermissions)
def get_my_permissions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role in ("admin", "owner"):
        return {"role": user.role, "permissions": ADMIN_PERMISSIONS}
    try:
        rows = db.scalars(select(RolePermission).where(RolePermission.role == user.role)).all()
        permissions = [row.permission for row in rows]
        if not permissions and db.scalar(select(RolePermission.id)) is None:
            permissions = DEFAULT_ROLE_PERMISSIONS.get(user.role, [])
    except SQLAlchemyError:
        db.rollback()
        permissions = DEFAULT_ROLE_PERMISSIONS.get(user.role, [])
    except Exception as exc:
        logger.exception("my permissions failed")
        return _error(str(exc), 500)
    return {"role": user.role, "permissions": permissions}
