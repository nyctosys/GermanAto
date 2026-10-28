"""Users, roles and permissions."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import Actor, hash_password, require
from app.db import get_db, utcnow
from app.models import Branch, Role, RolePermission, User, UserBranch
from app.permissions import PERMISSIONS
from app.validators import Email, Name, Password, Phone, Text, Username

router = APIRouter(prefix="/api", tags=["admin"])
can_manage = require("users")


class RoleIn(BaseModel):
    name: Name
    description: Text = ""
    is_admin: bool = False
    permissions: list[str] = Field(default_factory=list)


class UserCreate(BaseModel):
    username: Username
    full_name: Name
    email: Email | None = None
    phone: Phone = ""
    password: Password
    role_id: uuid.UUID
    branch_ids: list[uuid.UUID] = Field(min_length=1)
    is_active: bool = True


class UserUpdate(BaseModel):
    full_name: Name | None = None
    email: Email | None = None
    phone: Phone | None = None
    password: Password | None = None
    role_id: uuid.UUID | None = None
    branch_ids: list[uuid.UUID] | None = Field(default=None, min_length=1)
    is_active: bool | None = None


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    full_name: str
    email: str | None
    phone: str
    role_id: uuid.UUID
    role_name: str
    branch_ids: list[uuid.UUID]
    is_active: bool
    last_login_at: datetime | None
    locked: bool


def user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id, username=u.username, full_name=u.full_name, email=u.email, phone=u.phone, role_id=u.role_id,
        role_name=u.role.name, branch_ids=[b.branch_id for b in u.branches], is_active=u.is_active,
        last_login_at=u.last_login_at, locked=bool(u.locked_until and u.locked_until > utcnow()),
    )


def role_out(r: Role) -> dict:
    return {"id": r.id, "name": r.name, "description": r.description, "is_admin": r.is_admin,
            "permissions": sorted(p.permission for p in r.permissions), "version": r.version}


def _check_permissions(perms: list[str]) -> list[str]:
    unknown = sorted(set(perms) - set(PERMISSIONS))
    if unknown:
        raise HTTPException(422, f"Unknown permission: {', '.join(unknown)}")
    return sorted(set(perms))


def _check_branches(db: Session, ids: list[uuid.UUID]) -> None:
    found = set(db.scalars(select(Branch.id).where(Branch.id.in_(ids))))
    if found != set(ids):
        raise HTTPException(422, "One of the selected branches doesn't exist")


def _get_role(db: Session, role_id: uuid.UUID) -> Role:
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(422, "That role doesn't exist")
    return role


@router.get("/permissions")
def list_permissions(_: Actor = Depends(can_manage)):
    return [{"key": k, "label": v} for k, v in PERMISSIONS.items()]


@router.get("/roles")
def list_roles(_: Actor = Depends(can_manage), db: Session = Depends(get_db)):
    return [role_out(r) for r in db.scalars(select(Role).order_by(Role.name))]


@router.post("/roles", status_code=201)
def create_role(body: RoleIn, _: Actor = Depends(can_manage), db: Session = Depends(get_db)):
    role = Role(name=body.name, description=body.description, is_admin=body.is_admin,
                permissions=[RolePermission(permission=p) for p in _check_permissions(body.permissions)])
    db.add(role)
    db.commit()
    return role_out(role)


@router.put("/roles/{role_id}")
def update_role(role_id: uuid.UUID, body: RoleIn, actor: Actor = Depends(can_manage), db: Session = Depends(get_db)):
    role = _get_role(db, role_id)
    if role.id == actor.user.role_id and role.is_admin and not body.is_admin:
        raise HTTPException(409, "You can't remove admin rights from your own role")
    perms = _check_permissions(body.permissions)
    role.name, role.description, role.is_admin = body.name, body.description, body.is_admin
    existing = {p.permission: p for p in role.permissions}
    role.permissions = [existing.get(p) or RolePermission(permission=p) for p in perms]
    db.commit()
    return role_out(role)


@router.get("/users", response_model=list[UserOut])
def list_users(_: Actor = Depends(can_manage), db: Session = Depends(get_db)):
    return [user_out(u) for u in db.scalars(select(User).order_by(User.full_name))]


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, _: Actor = Depends(can_manage), db: Session = Depends(get_db)):
    _get_role(db, body.role_id)
    _check_branches(db, body.branch_ids)
    if db.scalar(select(User.id).where(User.username == body.username)):
        raise HTTPException(409, f"The username {body.username!r} is taken")
    user = User(
        username=body.username, full_name=body.full_name, email=body.email or None, phone=body.phone,
        password_hash=hash_password(body.password), role_id=body.role_id, is_active=body.is_active,
        branches=[UserBranch(branch_id=b) for b in set(body.branch_ids)],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user_out(user)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: uuid.UUID, body: UserUpdate, actor: Actor = Depends(can_manage), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    data = body.model_dump(exclude_unset=True)
    if user.id == actor.user.id and (data.get("is_active") is False or
                                     ("role_id" in data and data["role_id"] != user.role_id)):
        raise HTTPException(409, "You can't disable your own account or change your own role")
    if "role_id" in data:
        _get_role(db, data["role_id"])
    if "branch_ids" in data:
        _check_branches(db, data["branch_ids"])
        current = {b.branch_id: b for b in user.branches}
        user.branches = [current.get(b) or UserBranch(branch_id=b) for b in set(data.pop("branch_ids"))]
    if "password" in data:
        user.password_hash = hash_password(data.pop("password"))
        user.failed_logins, user.locked_until = 0, None  # an admin reset also unlocks
    if "email" in data:
        data["email"] = data["email"] or None  # empty string means "no email", keeps the unique index clean
    for key, value in data.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user_out(user)
