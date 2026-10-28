import base64
import hashlib
import hmac
import os
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import COOKIE_SECURE, SESSION_DAYS
from app.db import get_db, set_actor, utcnow
from app.models import Branch, User, UserSession
from app.permissions import PERMISSIONS

COOKIE = "gat_session"
MAX_FAILED_LOGINS = 5
LOCKOUT = timedelta(minutes=15)

# scrypt from the standard library; parameters per OWASP (N=2^15, r=8, p=1).
_N, _R, _P = 2**15, 8, 1


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, maxmem=64 * 1024 * 1024)
    return f"scrypt${_N}${_R}${_P}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, digest = stored.split("$")
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p),
                                maxmem=64 * 1024 * 1024, dklen=len(expected))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(db: Session, response: Response, request: Request, user: User, branch_id: uuid.UUID) -> None:
    token = secrets.token_urlsafe(32)
    db.add(UserSession(
        token_hash=_token_hash(token), user_id=user.id, branch_id=branch_id,
        expires_at=utcnow() + timedelta(days=SESSION_DAYS),
        ip=request.client.host if request.client else "", user_agent=request.headers.get("user-agent", "")[:300],
    ))
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax", secure=COOKIE_SECURE,
                        max_age=SESSION_DAYS * 86400, path="/")


def end_session(db: Session, request: Request, response: Response) -> None:
    token = request.cookies.get(COOKIE)
    if token:
        db.execute(delete(UserSession).where(UserSession.token_hash == _token_hash(token)))
    response.delete_cookie(COOKIE, path="/")


@dataclass
class Actor:
    user: User
    branch: Branch
    session: UserSession
    permissions: frozenset[str]

    def can(self, permission: str) -> bool:
        return permission in self.permissions


def permissions_of(user: User) -> frozenset[str]:
    if user.role.is_admin:
        return frozenset(PERMISSIONS)
    return frozenset(p.permission for p in user.role.permissions)


def current_actor(request: Request, db: Session = Depends(get_db)) -> Actor:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "Not signed in")
    sess = db.get(UserSession, _token_hash(token))
    if not sess or sess.expires_at <= utcnow():
        raise HTTPException(401, "Your session has ended. Sign in again.")
    user = db.get(User, sess.user_id)
    branch = db.get(Branch, sess.branch_id)
    if not user or not user.is_active or not branch or not branch.is_active:
        raise HTTPException(401, "This account is disabled")
    set_actor(db, user.id, branch.id, request.client.host if request.client else "")
    return Actor(user, branch, sess, permissions_of(user))


def require(permission: str):
    if permission not in PERMISSIONS:
        raise ValueError(f"Unknown permission {permission!r}")

    def check(actor: Actor = Depends(current_actor)) -> Actor:
        if not actor.can(permission):
            raise HTTPException(403, "You don't have permission to do this")
        return actor

    return check


def user_branch_ids(db: Session, user: User) -> list[uuid.UUID]:
    if user.role.is_admin:
        return list(db.scalars(select(Branch.id).where(Branch.is_active)))
    return [ub.branch_id for ub in user.branches]


if __name__ == "__main__":
    h = hash_password("correct horse")
    assert verify_password("correct horse", h) and not verify_password("wrong", h)
    assert not verify_password("x", "garbage")
    print("ok")
