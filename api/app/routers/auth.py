import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    LOCKOUT, MAX_FAILED_LOGINS, Actor, current_actor, end_session, start_session, user_branch_ids, verify_password,
)
from app.db import get_db, set_actor, utcnow
from app.events import log_action
from app.models import Branch, User

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str
    branch_id: uuid.UUID | None = None


class BranchOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str


def me_payload(db: Session, actor: Actor) -> dict:
    ids = user_branch_ids(db, actor.user)
    branches = db.scalars(select(Branch).where(Branch.id.in_(ids)).order_by(Branch.name)).all()
    return {
        "user": {"id": actor.user.id, "username": actor.user.username, "full_name": actor.user.full_name},
        "role": {"id": actor.user.role.id, "name": actor.user.role.name, "is_admin": actor.user.role.is_admin},
        "permissions": sorted(actor.permissions),
        "branch": BranchOut.model_validate(actor.branch, from_attributes=True),
        "branches": [BranchOut.model_validate(b, from_attributes=True) for b in branches],
    }


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    set_actor(db, ip=request.client.host if request.client else "")
    username = body.username.strip().lower()
    user = db.scalar(select(User).where(User.username == username))
    now = utcnow()

    if user and user.locked_until and user.locked_until > now:
        raise HTTPException(423, "Too many wrong passwords. Try again in a few minutes or ask an admin.")
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        if user:
            user.failed_logins += 1
            if user.failed_logins >= MAX_FAILED_LOGINS:
                user.locked_until, user.failed_logins = now + LOCKOUT, 0
        log_action(db, "login_failed", "users", user.id if user else None, {"username": username},
                   user_id=user.id if user else None)
        db.commit()
        raise HTTPException(401, "Wrong username or password")

    allowed = user_branch_ids(db, user)
    if not allowed:
        raise HTTPException(403, "No branch is assigned to this account. Ask an admin.")
    branch_id = body.branch_id if body.branch_id in allowed else allowed[0]

    set_actor(db, user.id, branch_id)
    user.failed_logins, user.locked_until, user.last_login_at = 0, None, now
    start_session(db, response, request, user, branch_id)
    log_action(db, "login", "users", user.id, user_id=user.id, branch_id=branch_id)
    db.commit()
    return {"ok": True}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    end_session(db, request, response)
    db.commit()
    return {"ok": True}


@router.get("/me")
def me(actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    return me_payload(db, actor)


class SwitchBranchIn(BaseModel):
    branch_id: uuid.UUID


@router.post("/switch-branch")
def switch_branch(body: SwitchBranchIn, actor: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    if body.branch_id not in user_branch_ids(db, actor.user):
        raise HTTPException(403, "You don't have access to that branch")
    actor.session.branch_id = body.branch_id
    log_action(db, "switch_branch", "branches", body.branch_id)
    db.commit()
    return {"ok": True}
