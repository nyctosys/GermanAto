import re

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.foundation.branch import DEFAULT_BRANCH_ID
from app.foundation.context import set_reason, set_user
from app.models import User
from app.security import JWTError, decode_token

_bearer = HTTPBearer(auto_error=False)
_BRANCH_RE = re.compile(r"^[0-9a-f]{8}$")


def _user_from_token(token: str | None, db: Session, token_type: str) -> User:
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        payload = decode_token(token)
        if payload.get("type") != token_type:
            raise HTTPException(status_code=401, detail="Invalid token")
        user_id = int(payload["sub"])
    except (JWTError, KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token") from None

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def get_branch_id(
    request: Request,
    x_branch_id: str | None = Header(default=None, alias="X-Branch-Id"),
) -> str:
    """Resolve active branch: X-Branch-Id header, else default workshop branch."""
    candidate = (x_branch_id or request.headers.get("X-Branch-Id") or "").strip().lower()
    if candidate and _BRANCH_RE.match(candidate):
        return candidate
    return DEFAULT_BRANCH_ID


def get_audit_reason(
    x_audit_reason: str | None = Header(default=None, alias="X-Audit-Reason"),
) -> str | None:
    reason = (x_audit_reason or "").strip()
    return reason or None


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
    reason: str | None = Depends(get_audit_reason),
) -> User:
    token = credentials.credentials if credentials else None
    user = _user_from_token(token, db, "access")
    set_user(user)
    if reason:
        set_reason(reason)
    return user


def get_refresh_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials if credentials else None
    return _user_from_token(token, db, "refresh")


def require_roles(*roles):
    """Accept require_roles('admin') or require_roles(['admin', 'accountant']).

    Expands legacy allow-lists so owner/manager/store_keeper cover older route guards.
    """
    from app.foundation.roles import expand_allowed_roles

    if len(roles) == 1 and isinstance(roles[0], (list, tuple, set)):
        allowed = expand_allowed_roles(roles[0])
    else:
        allowed = expand_allowed_roles(roles)

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return checker
